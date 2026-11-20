"""Polite HTTP for public, keyless services: identifying User-Agent, timeouts, bounded retries with
back-off (429/5xx, Retry-After honoured when short), per-host minimum spacing (Nominatim 1 req/s and
Wikimedia etiquette), and an optional per-case cache in .work/cache (deleted by `finalize`).

Every call returns a dict: {ok, status, data|text, error, cached, url}. `ok: False` with status 0 means
the service could not be reached (network/proxy) - an UNAVAILABLE source, never an observed absence.
Shared cloud addresses are rate-limited by many public services (HTTP 429): that is a temporary refusal,
reported as such, and never the same thing as "no results".
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import __version__

UA = os.environ.get("IGL_USER_AGENT") or (
    f"indoor-geolocator/{__version__} (OSINT agent skill; low volume; +https://github.com/topics/osint)")
# Image CDNs commonly refuse non-browser clients; images are fetched the way a browser would fetch them.
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/131.0.0.0 Safari/537.36")
IDENTIFY_TO = ("wikimedia.org", "wikipedia.org", "wikidata.org", "openstreetmap.org", "komoot.io")
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
    def __init__(self, cache_dir: Path | None = None, timeout: float = 25.0, retries: int = 3, dry: bool = False):
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.timeout = timeout
        self.retries = retries
        self.dry = dry                  # --print-url: record the requests instead of sending them
        self.printed: list[str] = []
        self.last_error = ""

    def _cache_path(self, key: str) -> Path | None:
        if not self.cache_dir:
            return None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".json")

    def get(self, url: str, params: dict | None = None, headers: dict | None = None, as_json: bool = True,
            data: bytes | None = None, method: str | None = None, cache: bool = True) -> dict:
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        if self.dry:
            shown = url
            if data and (headers or {}).get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
                shown = url + ("&" if "?" in url else "?") + data.decode("utf-8", "ignore")   # form POST -> GET
            if shown not in self.printed:
                self.printed.append(shown)
            return {"ok": False, "status": 0, "url": url, "cached": False, "dry": True,
                    "error": "not sent (--print-url)"}
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

    def download(self, url: str, dest: Path, headers: dict | None = None, max_bytes: int = 40_000_000,
                 retries: int = 2, timeout: float | None = None) -> bool:
        """Fetch one file (an image). Transient refusals (429, 5xx, resets: common from shared cloud
        addresses) are retried with a short jittered back-off; the reason of a failure is kept in
        `self.last_error`. Returns True when `dest` was written."""
        self.last_error = ""
        if self.dry:
            self.last_error = "not sent (--print-url)"
            return False
        if not url.startswith(("http://", "https://")):
            self.last_error = "not an http(s) URL"
            return False
        host = urllib.parse.urlparse(url).hostname or ""
        ua = UA if host.endswith(IDENTIFY_TO) else BROWSER_UA
        hdrs = {"User-Agent": ua, "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.8", **(headers or {})}
        for attempt in range(retries + 1):
            wait = MIN_INTERVAL.get(host, 0.0) - (time.time() - _last.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            _last[host] = time.time()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=hdrs),
                                            timeout=timeout or self.timeout) as r:
                    body = r.read(max_bytes + 1)
                if not body:
                    self.last_error = "empty reply"
                    return False
                if len(body) > max_bytes:
                    self.last_error = f"larger than {max_bytes // 1_000_000} MB"
                    return False
                dest.write_bytes(body)
                return True
            except urllib.error.HTTPError as e:
                self.last_error = f"HTTP {e.code}"
                if e.code not in (429, 500, 502, 503, 504) or attempt >= retries:
                    return False
            except Exception as e:  # noqa: BLE001 - reset, timeout, DNS, TLS, proxy
                self.last_error = f"{type(e).__name__}: {str(e)[:80]}"
                if attempt >= retries:
                    return False
            time.sleep(1.5 * (attempt + 1) + random.random())
        return False


def fetch_many(http: "Http", urls: list[str], dest_dir: Path, workers: int = 6, timeout: float = 12.0,
               retries: int = 1, referer: str | None = None, max_bytes: int = 15_000_000) -> dict[int, Path]:
    """Download several images in parallel (thumbnails of search results, gallery photos). Returns
    {index: path} for those that arrived; the others are simply missing (never an observed absence)."""
    from concurrent.futures import ThreadPoolExecutor
    dest_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    out: dict[int, Path] = {}

    def one(i: int, url: str) -> None:
        if not url:
            return
        client = Http(timeout=timeout, retries=0)
        dest = dest_dir / f"{i:03d}.img"
        hdrs = {"Referer": referer} if referer else None
        if client.download(url, dest, headers=hdrs, max_bytes=max_bytes, retries=retries, timeout=timeout):
            with lock:
                out[i] = dest

    if http is not None and getattr(http, "dry", False):
        return out
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(urls) or 1))) as ex:
        for i, u in enumerate(urls):
            ex.submit(one, i, u)
    return out


def probe(targets: dict[str, str], timeout: float = 5.0) -> dict[str, dict]:
    """State of several services at once (parallel, one short GET each, no retries, no cache). Returns
    {name: {ok, state, status, note}} with state ok | rate_limited | blocked | unreachable | error.
    `ok` is True only for a normal answer: a rate-limited service (HTTP 429) is reachable but will refuse
    requests right now, so its commands need their fallbacks."""
    from concurrent.futures import ThreadPoolExecutor

    def one(url: str) -> dict:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                r.read(512)
                return {"ok": True, "state": "ok", "status": r.status, "note": "reachable"}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                return {"ok": False, "state": "rate_limited", "status": 429, "note": "rate-limited now (HTTP 429)"}
            if e.code in (401, 403, 451):
                return {"ok": False, "state": "blocked", "status": e.code, "note": f"blocked (HTTP {e.code})"}
            return {"ok": e.code < 500, "state": "ok" if e.code < 500 else "error", "status": e.code,
                    "note": f"HTTP {e.code}"}
        except Exception as e:  # noqa: BLE001 - DNS, proxy refusal, timeout
            return {"ok": False, "state": "unreachable", "status": 0, "note": f"unreachable ({type(e).__name__})"}

    with ThreadPoolExecutor(max_workers=max(1, len(targets))) as ex:
        futs = {name: ex.submit(one, url) for name, url in targets.items()}
        return {name: f.result() for name, f in futs.items()}
