"""Environment check: what can run here, what is missing, how to fix it. Uploads nothing."""
from __future__ import annotations

import importlib
import os
import platform
import shutil
import sys

from . import __version__, ocr
from .net import Http
from .util import DATA_DIR, table

PROBES = [
    ("Nominatim (geocoding)", "https://nominatim.openstreetmap.org/search?q=Berlin&format=json&limit=1"),
    ("Photon (geocoding fallback)", "https://photon.komoot.io/api/?q=Berlin&limit=1"),
    ("Overpass (OSM queries)", "https://overpass-api.de/api/status"),
    ("Wikimedia Commons", "https://commons.wikimedia.org/w/api.php?action=query&meta=siteinfo&format=json"),
    ("Wikidata", "https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Louvre&language=en&format=json"),
    ("Wikidata Query Service (SPARQL)", "https://query.wikidata.org/sparql?format=json&query=ASK%7B%7D"),
    ("timeapi.io (time zones)", "https://timeapi.io/api/TimeZone/coordinate?latitude=48.85&longitude=2.35"),
    ("Open-Meteo (historical weather)", "https://archive-api.open-meteo.com/v1/archive?latitude=48.85&longitude=2.35"
                                        "&start_date=2024-01-01&end_date=2024-01-01&daily=weather_code"),
    ("Bluesky API (social search)", "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=hotel&limit=1"),
    ("Flickr public feeds (social search)", "https://www.flickr.com/services/feeds/photos_public.gne?tags=hotel"
                                            "&format=json&nojsoncallback=1"),
    ("Openverse API (CC images)", "https://api.openverse.org/v1/images/?q=hotel&page_size=1"),
    ("Mastodon API (hashtags)", "https://mastodon.social/api/v1/timelines/tag/hotel?limit=1"),
    ("Yandex Images (reverse search)", "https://yandex.com/images/"),
    ("TinEye (reverse search)", "https://tineye.com/"),
]


def run(network: bool = True) -> int:
    rows = [["python", platform.python_version(), "ok" if sys.version_info >= (3, 9) else "need >= 3.9"],
            ["indoor-geolocator", __version__, "ok"],
            ["data/countries.json", "present" if (DATA_DIR / "countries.json").exists() else "MISSING",
             "ok" if (DATA_DIR / "countries.json").exists() else "reinstall the skill"],
            ["data/gs1_prefixes.json", "present" if (DATA_DIR / "gs1_prefixes.json").exists() else "missing",
             "ok" if (DATA_DIR / "gs1_prefixes.json").exists() else "barcode prefix lookup disabled"]]
    for mod, pip, need in [("PIL", "pillow", "REQUIRED (all image work)"), ("numpy", "numpy", "QR/barcode, CLAHE"),
                           ("cv2", "opencv-python-headless", "QR codes and barcodes"),
                           ("phonenumbers", "phonenumbers", "offline phone-number geolocation"),
                           ("playwright", "playwright", "automated reverse image search (+ `playwright install chromium`)"),
                           ("pillow_heif", "pillow-heif", "HEIC/HEIF photos"),
                           ("rapidocr_onnxruntime", "rapidocr-onnxruntime", "OCR fallback without tesseract")]:
        try:
            m = importlib.import_module(mod)
            rows.append([mod, getattr(m, "__version__", "installed"), "ok"])
        except Exception:  # noqa: BLE001
            rows.append([mod, "missing", f"pip install {pip}  ({need})"])
    b = ocr.backends()
    if b["tesseract"]:
        langs = [l for l in b["tesseract_langs"] if l != "osd"]
        rows.append(["tesseract", f"{len(langs)} languages", ", ".join(langs[:24]) + (" ..." if len(langs) > 24 else "")])
    else:
        rows.append(["tesseract", "missing", "apt install tesseract-ocr tesseract-ocr-all | brew install tesseract "
                                             "tesseract-lang | winget install UB-Mannheim.TesseractOCR"])
    try:
        from zoneinfo import available_timezones
        nz = len(available_timezones())
    except Exception:  # noqa: BLE001
        nz = 0
    rows.append(["time-zone database", f"{nz} zones" if nz else "MISSING",
                 "ok" if nz else "pip install tzdata  (EXIF offset -> time zones, time-zone consistency check)"])
    rows.append(["exiftool", "present" if shutil.which("exiftool") else "missing (optional: richer metadata)", ""])
    wig = bool(os.environ.get("WIGLE_API_NAME") and os.environ.get("WIGLE_API_TOKEN"))
    rows.append(["WiGLE API key", "set" if wig else "not set",
                 "ok" if wig else "optional: Wi-Fi SSID lookup (`geo wigle`) with the user's free key"])
    print(table(rows, ["component", "state", "note / fix"], maxw=90))
    if network:
        http = Http(timeout=10, retries=0)
        out = []
        for name, url in PROBES:
            r = http.get(url, as_json=False, cache=False)
            st = r.get("status") or 0
            state = ("reachable" if r["ok"] else
                     f"RATE-LIMITED now ({r.get('error')}): retry later" if st == 429 else
                     f"BLOCKED ({r.get('error')})" if st in (401, 403) else
                     f"UNREACHABLE ({r.get('error')})" if not st else f"ERROR ({r.get('error')})")
            out.append([name, st or "-", state])
        print()
        print(table(out, ["service", "http", "state"], maxw=90))
        print("\nUnavailable services only disable the methods that need them - say so in the report and use the "
              "alternatives (references/sources-and-tools.md).")
    return 0
