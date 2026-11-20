#!/usr/bin/env python3
"""Rebuild docs/demo/ - the worked example shown on the project page - with the current skill version.

    python tools/make_demo.py            # rewrites docs/demo/ (REPORT.md, result.json, case.json, evidence/)
    python -m pytest tests/test_docs.py  # then: checks docs/index.html against the rebuilt case

The demo photo (docs/demo/input/larkspur-room.jpg) is a synthetic picture of a fictional hotel room, so the
run is offline: every online route is logged as not applicable, and the answer stops at city level with the
site left open. It shows the ledger, the confidence rules and the tidy case folder, not the online search.
The steps below are what an agent does by hand; they run in-process through igl.main().

The project page quotes this case (OCR boxes, the phone signal, shares, file names), so the build needs the
same optional tools that produced those: tesseract, OpenCV + numpy (the QR code) and phonenumbers (the
London area code). It stops with a message when one is missing, instead of publishing a thinner case.
"""
from __future__ import annotations

import importlib.util
import io
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "docs" / "demo"
PHOTO = DEMO / "input" / "larkspur-room.jpg"
sys.path.insert(0, str(REPO / "indoor-geolocator" / "scripts"))
os.environ.setdefault("IGL_NO_EMBED", "1")          # nothing here needs the similarity model or the network

import igl  # noqa: E402
from iglib import ocr  # noqa: E402
from iglib.util import read_json, write_json  # noqa: E402


def missing_tools() -> list[str]:
    out = [f"{pip} (pip install {pip})" for mod, pip in (("cv2", "opencv-python-headless"), ("numpy", "numpy"),
                                                         ("phonenumbers", "phonenumbers"))
           if importlib.util.find_spec(mod) is None]
    if not ocr.tesseract_exe():
        out.append("tesseract (apt install tesseract-ocr | brew install tesseract | winget install "
                   "UB-Mannheim.TesseractOCR)")
    return out


def run(*argv) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = igl.main([str(a) for a in argv])
    out = buf.getvalue()
    if code != 0:
        raise SystemExit(f"igl.py {' '.join(str(a) for a in argv[:3])} ... failed ({code}):\n{out}")
    return out


def first_id(out: str) -> str:
    return out.split()[0]


def main() -> int:
    if not PHOTO.exists():
        raise SystemExit(f"demo photo missing: {PHOTO}")
    missing = missing_tools()
    if missing:
        raise SystemExit("the demo case needs these tools, which are missing here:\n  " + "\n  ".join(missing))
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "demo"
        work.mkdir()
        photo = work / PHOTO.name
        shutil.copy2(PHOTO, photo)
        case = work / "case"
        run("init", photo, "--out", case, "--no-probe")
        ledger = read_json(case / "case.json")
        ledger["image"]["original_path"] = f"/demo/{PHOTO.name}"           # not this machine's temp folder
        write_json(case / "case.json", ledger)
        run("note", case, "Hypotheses: scene=hotel room desk. 1) United Kingdom: switched three-pin socket and £ prices; "
                          "2) another British Isles or Commonwealth territory sharing the socket and the £ (Isle of Man, "
                          "Channel Islands, Gibraltar); 3) a British-themed venue abroad (unlikely: fixed wall socket). "
                          "Would discriminate: the phone prefix and area code on the card",
            "--kind", "hypothesis", "--status", "inferred", "--source", "image")
        run("scan", case)
        socket = first_id(run("crop", case, "--cell", "F3:H3", "--label", "socket", "--what",
                              "double switched socket on the wall beside the desk"))
        card = first_id(run("crop", case, "--cell", "C3:F5", "--enhance", "auto", "--label", "tent-card", "--what",
                            "tent card on the desk: venue name, breakfast price, reception number"))
        n_socket = first_id(run("note", case, "Double switched socket: per outlet one vertical earth slot above two "
                                              "horizontal slots, rocker switch with red indicator = BS 1363 (Type G)",
                                "--kind", "standard", "--status", "observed", "--source", "image", "--file", socket))
        n_price = first_id(run("note", case, "'£14.50 per person incl. VAT' read on the tent card", "--kind", "text",
                               "--status", "read", "--source", "text", "--file", card))
        n_phone = first_id(run("note", case, "'+44 20 7946 0321' read on the tent card; libphonenumber: GB, London "
                                             "(area code 20)", "--kind", "text", "--status", "computed", "--source",
                               "text", "--file", card))
        n_lang = first_id(run("note", case, "English on every item, no other script", "--kind", "language", "--status",
                              "observed", "--source", "text", "--file", card))
        run("note", case, "Venue name 'THE LARKSPUR' and Wi-Fi SSID 'Larkspur-Guest' (password redacted by the decoder); "
                          "the demo venue is fictional, so it is not searched", "--kind", "context", "--status",
            "computed", "--source", "text", "--file", card)
        run("countries", "--plug", "G", "--case", case, "--clue", n_socket)
        run("countries", "--currency", "£", "--case", case, "--clue", n_price, "--lr", "20")
        run("countries", "--lang", "en", "--case", case, "--clue", n_lang, "--lr", "1.5")
        run("link", case, n_phone, "--for", "United Kingdom:30", "--why", "+44 20 is a UK (London) number")
        london = first_id(run("cand", case, "London", "--level", "city", "--parent", "United Kingdom", "--at",
                              "51.5072,-0.1276"))
        run("link", case, n_phone, "--for", f"{london}:30", "--why", "area code 20 = London")
        run("log", case, "visual_sweep", "--status", "results", "--detail",
            "9 tiles: tent card, Wi-Fi card, double socket, lamp, framed print; no window or reflection")
        run("log", case, "standards", "--status", "results", "--detail", "BS 1363 Type G socket; £ prices with VAT")
        run("log", case, "culture_style", "--status", "results", "--detail",
            "generic international hotel decor; English only; no cultural or religious markers")
        run("log", case, "consistency", "--status", "results", "--detail",
            "socket, currency, language and phone agree on GB/London; no EXIF time to test sun or time zone")
        why = "demo photo is synthetic and the venue fictional: online routes skipped on purpose"
        run("log", case, "reverse_search,text_search,social_search,candidate_enum,reference_match", "--status",
            "not_applicable", "--detail", why)
        run("log", case, "window_view", "--status", "not_applicable", "--detail", "no window, door or reflection in the frame")
        run("answer", case, london, "--no-network", "--radius", "25000", "--summary",
            "A '+44 20' phone number read on the tent card places the room in London (libphonenumber, decisive). "
            "Independent fixed standards agree on the UK: a BS 1363 Type G switched socket and £ prices with VAT. The "
            "venue named on the card is fictional, so no site candidate exists and the site level stays open.",
            "--open-questions", "Site level: the venue named on the card is fictional, so no reference imagery exists.")
        print(run("check", case))
        print(run("finalize", case))
        for name in ("REPORT.md", "result.json", "case.json"):
            shutil.copy2(case / name, DEMO / name)
        shutil.copy2(case / "input" / "metadata.json", DEMO / "input" / "metadata.json")
        shutil.rmtree(DEMO / "evidence", ignore_errors=True)
        shutil.copytree(case / "evidence", DEMO / "evidence")
    print(f"docs/demo rebuilt: {', '.join(sorted(p.name for p in (DEMO / 'evidence').iterdir()))}")
    print("now run `python -m pytest tests/test_docs.py`: it checks docs/index.html against the rebuilt case")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
