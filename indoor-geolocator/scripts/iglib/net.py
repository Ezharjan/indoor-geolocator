"""Polite HTTP for public, keyless services: identifying User-Agent, timeouts, bounded retries with
back-off (429/5xx, Retry-After honoured when short), per-host minimum spacing (Nominatim 1 req/s and
Wikimedia etiquette), and an optional per-case cache in .work/cache (deleted by `finalize`).

Every call returns a dict: {ok, status, data|text, error, cached, url}. `ok: False` with status 0 means
the service could not be reached (network/proxy) - an UNAVAILABLE source, never an observed absence.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import __version__

UA = os.environ.get("IGL_USER_AGENT") or (
    f"indoor-geolocator/{__version__} (OSINT agent skill; low volume; +https://github.com/topics/osint)")
MIN_INTERVAL = {"nominatim.openstreetmap.org": 1.1, "commons.wikimedia.org": 1.0, "www.wikidata.org": 0.5,
                "query.wikidata.org": 1.0, "en.wikipedia.org": 1.0, "photon.komoot.io": 0.5,
                "timeapi.io": 0.5, "api.openverse.org": 1.0, "archive-api.open-meteo.com": 0.5,
                "api.open-meteo.com": 0.5}
_last: dict[str, float] = {}


def _reason(body: str) -> str:
    """Short server-given reason from an error body (JSON 'reason'/'message'/'error'), else ''."""
    try:
        j = json.loads(body)
    except (ValueError, TypeError):
        return ""
    if isinstance(j, dict):
        for k in ("reason", "message", "detail", "error"):
            if isinstance(j.get(k), str) and j[k].strip():
                return j[k].strip()[:160]
    return ""


class Http:
    def __init__(self, cache_dir: Path | None = None, timeout: float = 25.0, retries: int = 3):
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.timeout = timeout
        self.retries = retries

    def _cache_path(self, key: str) -> Path | None:
        if not self.cache_dir:
            return None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".json")

    def get(self, url: str, params: dict | None = None, headers: dict | None = None, as_json: bool = True,
            data: bytes | None = None, method: str | None = None, cache: bool = True) -> dict:
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        key = (method or ("POST" if data else "GET")) + " " + url + " " + (data or b"").decode("utf-8", "ignore")
        cp = self._cache_path(key) if cache else None
        if cp and cp.exists():
            try:
                hit = json.loads(cp.read_text(encoding="utf-8"))
                hit["cached"] = True
                return hit
            except Exception:  # noqa: BLE001
                pass
        host = urllib.parse.urlparse(url).hostname or ""
        hdrs = {"User-Agent": UA, "Accept-Language": "en", **(headers or {})}
        last_err, status = "", 0
        for attempt in range(self.retries + 1):
            wait = MIN_INTERVAL.get(host, 0.0) - (time.time() - _last.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            _last[host] = time.time()
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    status = r.status
                    body = r.read()
                txt = body.decode("utf-8", "replace")
                out = {"ok": True, "status": status, "url": url, "cached": False}
                if as_json:
                    try:
                        out["data"] = json.loads(txt)
                    except json.JSONDecodeError:
                        out = {"ok": False, "status": status, "url": url, "cached": False,
                               "error": "reply is not JSON (rate-limit page or outage?)", "text": txt[:300]}
                        last_err = out["error"]
                        if attempt < self.retries:
                            time.sleep(2 * (attempt + 1))
                            continue
                        return out
                else:
                    out["text"] = txt
                if cp:
                    cp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
                return out
            except urllib.error.HTTPError as e:
                status = e.code
                try:
                    body = e.read().decode("utf-8", "replace")[:600]
                except Exception:  # noqa: BLE001
                    body = ""
                why = _reason(body)
                last_err = f"HTTP {e.code}" + (f": {why}" if why else "")
                ra = e.headers.get("Retry-After") if e.headers else None
                # a long Retry-After (daily quota) means retrying now is pointless: report it at once
                long_wait = bool(ra and ra.isdigit() and float(ra) > 30)
                if e.code in (429, 500, 502, 503, 504) and attempt < self.retries and not long_wait:
                    delay = float(ra) if ra and ra.isdigit() else 3 * (attempt + 1) ** 2
                    time.sleep(delay)
                    continue
                if long_wait:
                    last_err += f" (retry after {int(float(ra))} s)"
                return {"ok": False, "status": status, "url": url, "cached": False, "error": last_err,
                        "text": body[:300]}
            except Exception as e:  # noqa: BLE001 - network, DNS, TLS, proxy
                last_err = f"{type(e).__name__}: {e}"
                if attempt < self.retries:
                    time.sleep(2 * (attempt + 1))
                    continue
        return {"ok": False, "status": status, "url": url, "cached": False, "error": last_err or "unreachable"}

    def download(self, url: str, dest: Path, headers: dict | None = None) -> bool:
        host = urllib.parse.urlparse(url).hostname or ""
        wait = MIN_INTERVAL.get(host, 0.0) - (time.time() - _last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                dest.write_bytes(r.read())
            return True
        except Exception:  # noqa: BLE001
            return False
