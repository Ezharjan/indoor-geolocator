"""Temporary public copies of the photo (or a crop) for reverse image search BY URL.

Google Lens and Bing refuse headless uploads, and many browser tools cannot attach a local file, but every
engine accepts an image URL (revsearch.by_url_links). This module uploads a metadata-free JPEG (callers
re-encode it, so no EXIF/GPS leaves the machine) to a keyless file host that deletes it after a few hours,
and returns the URL. Hosts are tried in order; each is tried once.

Privacy: the copy is reachable by anyone who has the (random, unlisted) URL until it expires. SKILL.md
says when not to use it (a photo the user marked private, identifiable private people: share a crop
without them). Every share is recorded in the case and listed in the report's data-handling section.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from .net import Http

HOSTS = {   # name: (upload endpoint, retention)
    "uguu": ("https://uguu.se/upload", "3 hours"),
    "litterbox": ("https://litterbox.catbox.moe/resources/internals/api.php", "1 hour"),
    "tmpfiles": ("https://tmpfiles.org/api/v1/upload", "60 minutes"),
}


def _multipart(fields: dict[str, str], file_field: str, path: Path) -> tuple[bytes, str]:
    boundary = "----igl" + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{path.name}"\r\n'
                 f"Content-Type: image/jpeg\r\n\r\n".encode() + path.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _post(http: Http, url: str, fields: dict[str, str], file_field: str, path: Path) -> dict:
    body, ctype = _multipart(fields, file_field, path)
    once = Http(timeout=60, retries=0)
    return once.get(url, data=body, headers={"Content-Type": ctype}, as_json=False, method="POST", cache=False)


def _uguu(http: Http, path: Path) -> str:
    r = _post(http, HOSTS["uguu"][0], {}, "files[]", path)
    if not r["ok"]:
        raise RuntimeError(r.get("error"))
    d = json.loads(r["text"])
    if not d.get("success") or not d.get("files"):
        raise RuntimeError(str(d.get("description") or d)[:160])
    return d["files"][0]["url"]


def _litterbox(http: Http, path: Path) -> str:
    r = _post(http, HOSTS["litterbox"][0], {"reqtype": "fileupload", "time": "1h"}, "fileToUpload", path)
    url = (r.get("text") or "").strip()
    if not r["ok"] or not url.startswith("https://"):
        raise RuntimeError(r.get("error") or url[:160])
    return url


def _tmpfiles(http: Http, path: Path) -> str:
    r = _post(http, HOSTS["tmpfiles"][0], {}, "file", path)
    if not r["ok"]:
        raise RuntimeError(r.get("error"))
    url = (json.loads(r["text"]).get("data") or {}).get("url", "")
    if "tmpfiles.org/" not in url:
        raise RuntimeError(f"unexpected reply: {r['text'][:160]}")
    return url.replace("http://", "https://").replace("tmpfiles.org/", "tmpfiles.org/dl/", 1)


UPLOADERS = {"uguu": _uguu, "litterbox": _litterbox, "tmpfiles": _tmpfiles}


def upload(http: Http, path: Path, host: str = "auto") -> dict:
    """{ok, url, host, expires} or {ok: False, error}."""
    order = list(UPLOADERS) if host == "auto" else [host]
    errors = []
    for name in order:
        if name not in UPLOADERS:
            return {"ok": False, "error": f"unknown host {name!r} (choose from auto, {', '.join(UPLOADERS)})"}
        try:
            url = UPLOADERS[name](http, Path(path))
            return {"ok": True, "url": url, "host": name, "expires": HOSTS[name][1]}
        except Exception as e:  # noqa: BLE001 - network refusal, host change, bad reply
            errors.append(f"{name}: {str(e)[:120] or type(e).__name__}")
    return {"ok": False, "error": "; ".join(errors)}
