"""Small shared helpers: paths, JSON I/O, hashing, parsing, console tables."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
SKILL_DIR = SCRIPTS_DIR.parent
DATA_DIR = SKILL_DIR / "data"


class IglError(Exception):
    """An error with a message meant for the user/agent (printed without a traceback)."""


def utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            pass


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        if default is not None:
            return default
        raise


def write_json(path: Path, data, indent: int = 1) -> None:
    """Atomic write: a crash never leaves a half-written JSON file behind."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.write("\n")
        try:
            os.chmod(tmp, 0o644)       # mkstemp creates 0600; case files are ordinary user documents
        except OSError:
            pass
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(text: str, maxlen: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return (text[:maxlen].rstrip("-") or "item")


def parse_box(s: str) -> tuple[int, int, int, int]:
    try:
        x0, y0, x1, y1 = (float(v) for v in re.split(r"[ ,;]+", s.strip()))
    except ValueError as e:
        raise IglError(f"--box must be x0,y0,x1,y1 in pixels of the upright image (got {s!r})") from e
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))


def parse_latlon(s: str) -> tuple[float, float]:
    m = re.match(r"^\s*([-+]?\d+(?:\.\d*)?)\s*[, ]\s*([-+]?\d+(?:\.\d*)?)\s*$", s or "")
    if not m:
        raise IglError(f"expected 'lat,lon' in decimal degrees (got {s!r})")
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise IglError(f"coordinates out of range: {lat},{lon}")
    return lat, lon


def table(rows: list[list], headers: list[str] | None = None, maxw: int = 60) -> str:
    """Plain-text table for the console (the agent reads it)."""
    rows = [["" if c is None else str(c) for c in r] for r in rows]
    if headers:
        rows = [headers] + rows
    if not rows:
        return "(none)"
    widths = [min(maxw, max(len(r[i]) if i < len(r) else 0 for r in rows)) for i in range(max(len(r) for r in rows))]
    out = []
    for n, r in enumerate(rows):
        cells = []
        for i, w in enumerate(widths):
            c = r[i] if i < len(r) else ""
            if len(c) > w:
                c = c[: w - 1] + "…"
            cells.append(c.ljust(w))
        out.append("  ".join(cells).rstrip())
        if headers and n == 0:
            out.append("  ".join("-" * w for w in widths))
    return "\n".join(out)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def short(text: str, n: int = 90) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


_SECRETS = [
    (re.compile(r"(?i)(WIFI:[^\n]*?(?:^|;)P:)((?:\\;|[^;\n])*)"), r"\1<redacted>"),      # Wi-Fi QR password
    (re.compile(r"(?i)((?:^|;)P:)((?:\\;|[^;\n])*)(?=[^\n]*;S:|;;)"), r"\1<redacted>"),    # P: before S:
    (re.compile(r"(?i)\b(password|passwort|mot de passe|contraseña|senha|пароль|密码|密碼|パスワード|비밀번호)"
                r"(\s*[:：=]\s*)(\S+)"), r"\1\2<redacted>"),
    (re.compile(r"\b([A-Z]{2}\d{2})(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b"), r"\1****"),  # IBAN
]


def redact(text: str) -> str:
    """Remove secrets that engines and pages echo back (Wi-Fi passwords decoded from a QR code, written
    passwords, IBANs) before anything is printed or stored as evidence."""
    out = str(text or "")
    for pat, rep in _SECRETS:
        out = pat.sub(rep, out)
    return out
