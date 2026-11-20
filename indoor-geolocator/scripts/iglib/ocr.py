"""Second reader for text in the photo: multi-pass OCR (full frame, enhanced frame, overlapping upscaled
tiles), script probing for non-Latin writing, merge with pass agreement.

Backends, best available first: tesseract (CLI, any language pack installed), RapidOCR
(`pip install rapidocr-onnxruntime`, Chinese/English models). Without either, the agent reads the
text itself from zoomed crops - OCR output is only ever a hint (status `reported`) until verified.

An OCR confidence is a glyph-shape score, not proof that text exists: stains and textures can score
0.99. Lines read in only one pass, or only after upscaling, are the most likely misreads.
"""
from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps

from . import imaging

LATIN_LANGS = ["eng", "fra", "deu", "spa", "ita", "por", "nld", "pol", "tur", "vie", "ind"]
SCRIPT_PROBES = [  # (label, tesseract languages, unicode script names that count as a hit)
    ("CJK", ["chi_sim", "chi_tra", "jpn", "kor"], ("CJK", "HIRAGANA", "KATAKANA", "HANGUL")),
    ("Cyrillic", ["rus", "ukr", "bul", "srp"], ("CYRILLIC",)),
    ("Arabic", ["ara", "fas", "urd"], ("ARABIC",)),
    ("Hebrew", ["heb"], ("HEBREW",)),
    ("Devanagari", ["hin", "mar", "nep"], ("DEVANAGARI",)),
    ("Thai", ["tha"], ("THAI",)),
    ("Greek", ["ell"], ("GREEK",)),
    ("Korean", ["kor"], ("HANGUL",)),
    ("Bengali", ["ben"], ("BENGALI",)),
    ("Tamil", ["tam"], ("TAMIL",)),
    ("Georgian", ["kat"], ("GEORGIAN",)),
    ("Armenian", ["hye"], ("ARMENIAN",)),
    ("Khmer", ["khm"], ("KHMER",)),
    ("Lao", ["lao"], ("LAO",)),
    ("Myanmar", ["mya"], ("MYANMAR",)),
    ("Sinhala", ["sin"], ("SINHALA",)),
    ("Ethiopic", ["amh"], ("ETHIOPIC",)),
]


# country -> tesseract language pack that reads its signage (used to suggest a better OCR re-run)
COUNTRY_LANG = {**{c: "deu" for c in ("DE", "AT", "CH", "LI", "LU")}, **{c: "fra" for c in ("FR", "BE", "MC")},
                **{c: "spa" for c in ("ES", "MX", "AR", "CO", "CL", "PE", "VE", "EC", "GT", "CU", "BO", "DO", "HN",
                                      "PY", "SV", "NI", "CR", "PA", "UY", "PR")},
                **{c: "por" for c in ("PT", "BR", "AO", "MZ")}, "IT": "ita", "SM": "ita", "NL": "nld", "PL": "pol",
                "TR": "tur", "CZ": "ces", "SK": "slk", "HU": "hun", "RO": "ron", "SE": "swe", "NO": "nor", "DK": "dan",
                "FI": "fin", "VN": "vie", "ID": "ind", "RU": "rus", "UA": "ukr", "BY": "bel", "BG": "bul", "RS": "srp",
                "HR": "hrv", "SI": "slv", "GR": "ell", "CY": "ell", "JP": "jpn", "KR": "kor", "CN": "chi_sim",
                "SG": "chi_sim", "TW": "chi_tra", "HK": "chi_tra", "MO": "chi_tra", "TH": "tha", "IL": "heb",
                "IN": "hin", "EG": "ara", "SA": "ara", "AE": "ara", "MA": "ara", "IR": "fas"}


def suggest_langs(signals: dict, used: list[str], installed: list[str]) -> tuple[list[str], list[str]]:
    """Countries hinted by phones / domains / postcodes / tax words -> language packs worth a re-run.
    Returns (countries, languages); languages already used or not installed are left out."""
    countries: list[str] = []
    for key in ("phones", "domains", "emails", "postcodes"):
        for item in signals.get(key, []):
            c = item.get("country")
            if c and c not in countries:
                countries.append(c)
    for item in signals.get("tax_words", []) + signals.get("address_words", []):
        for c in re.findall(r"\b[A-Z]{2}\b", item.get("suggests", "")):
            if c not in countries:
                countries.append(c)
    langs = []
    for c in countries:
        lang = COUNTRY_LANG.get(c)
        if lang and lang not in used and lang in installed and lang not in langs:
            langs.append(lang)
    return countries, langs


def tesseract_exe() -> str | None:
    exe = shutil.which("tesseract")
    if exe:
        return exe
    for p in (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
              "/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
        if os.path.exists(p):
            return p
    return None


def tesseract_langs(exe: str) -> list[str]:
    try:
        r = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=20)
        return [ln.strip() for ln in (r.stdout + r.stderr).splitlines()[1:] if ln.strip() and " " not in ln.strip()]
    except Exception:  # noqa: BLE001
        return []


def rapidocr_engine():
    for mod in ("rapidocr_onnxruntime", "rapidocr"):
        try:
            m = __import__(mod, fromlist=["RapidOCR"])
            return m.RapidOCR()
        except Exception:  # noqa: BLE001
            continue
    return None


def backends() -> dict:
    exe = tesseract_exe()
    out = {"tesseract": exe, "tesseract_langs": tesseract_langs(exe) if exe else [], "rapidocr": False}
    try:
        __import__("rapidocr_onnxruntime")
        out["rapidocr"] = True
    except Exception:  # noqa: BLE001
        try:
            __import__("rapidocr")
            out["rapidocr"] = True
        except Exception:  # noqa: BLE001
            pass
    return out


def scripts_in(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ch in text:
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        key = name.split(" ")[0] if name else "UNKNOWN"
        if key == "CJK":
            key = "CJK"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _tess(exe: str, im: Image.Image, langs: list[str], psm: int, timeout: int) -> list[dict]:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "in.png"
        im.save(p)
        cmd = [exe, str(p), "stdout", "-l", "+".join(langs), "--psm", str(psm), "tsv"]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return []
        if r.returncode != 0:
            return []
        rows = list(csv.DictReader(io.StringIO(r.stdout.decode("utf-8", "ignore")), delimiter="\t",
                                   quoting=csv.QUOTE_NONE))
    lines: dict[tuple, dict] = {}
    for row in rows:
        try:
            if int(row.get("level", 0)) != 5:
                continue
            conf = float(row.get("conf", -1))
        except (TypeError, ValueError):
            continue
        text = (row.get("text") or "").strip()
        if not text or conf < 0:
            continue
        key = (row["block_num"], row["par_num"], row["line_num"])
        x, y, w, h = (int(row[k]) for k in ("left", "top", "width", "height"))
        ln = lines.setdefault(key, {"words": [], "confs": [], "box": [x, y, x + w, y + h]})
        ln["words"].append(text)
        ln["confs"].append(conf)
        b = ln["box"]
        ln["box"] = [min(b[0], x), min(b[1], y), max(b[2], x + w), max(b[3], y + h)]
    out = []
    for ln in lines.values():
        out.append({"text": " ".join(ln["words"]), "conf": round(sum(ln["confs"]) / len(ln["confs"]) / 100, 3),
                    "box": ln["box"]})
    return out


def _rapid(engine, im: Image.Image) -> list[dict]:
    try:
        import numpy as np  # type: ignore
        res, _ = engine(np.array(im))
    except Exception:  # noqa: BLE001
        return []
    out = []
    for item in res or []:
        pts, text, score = item[0], item[1], float(item[2])
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        out.append({"text": str(text).strip(), "conf": round(score, 3),
                    "box": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]})
    return out


def _norm(t: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", "", t.lower())


def _iou(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def _alnum(t: str) -> int:
    return sum(ch.isalnum() for ch in t)


def run(img: Image.Image, langs: list[str] | None = None, budget_s: float = 150.0, fast: bool = False) -> dict:
    """OCR the upright image. Returns {backend, langs, passes, lines[], scripts, elapsed_s, notes[]}."""
    t0 = time.time()
    info = backends()
    notes: list[str] = []
    W, H = img.size
    full_scale = min(2.0, max(0.5, 2000 / max(W, H)))
    full = img.resize((round(W * full_scale), round(H * full_scale)), Image.LANCZOS) if full_scale != 1 else img
    raw: list[dict] = []          # each: text, conf, box (original px), pass, lang

    def add(lines, pass_name, scale, offset=(0, 0), lang=""):
        for ln in lines:
            b = ln["box"]
            raw.append({"text": ln["text"], "conf": ln["conf"], "pass": pass_name, "lang": lang,
                        "box": [int(b[0] / scale + offset[0]), int(b[1] / scale + offset[1]),
                                int(b[2] / scale + offset[0]), int(b[3] / scale + offset[1])]})

    def left() -> float:
        return budget_s - (time.time() - t0)

    backend = None
    used_langs: list[str] = []
    if info["tesseract"]:
        exe = info["tesseract"]
        installed = set(info["tesseract_langs"])
        backend = "tesseract"
        if langs:
            used_langs = [l for l in langs if l in installed] or ["eng"]
            missing = [l for l in langs if l not in installed]
            if missing:
                notes.append(f"tesseract language packs missing: {', '.join(missing)}")
        else:
            used_langs = ["eng"] if "eng" in installed else sorted(installed - {"osd"})[:1]
            add(_tess(exe, full, used_langs, 11, 90), "full", full_scale, lang="+".join(used_langs))
            probe = imaging.fit(img, 1600)
            ps = probe.width / W
            for label, cand, script_names in SCRIPT_PROBES:
                have = [l for l in cand if l in installed]
                if not have or left() < 20 or (fast and label not in ("CJK", "Cyrillic", "Arabic")):
                    continue
                lines = _tess(exe, probe, have, 11, 60)
                latin = [r for r in raw if r["conf"] >= 0.75 and _alnum(r["text"]) >= 3]
                good = []
                for ln in lines:
                    sc = scripts_in(ln["text"])
                    n_script = sum(v for k, v in sc.items() if k in script_names)
                    n_alpha = sum(sc.values())
                    if ln["conf"] < 0.75 or n_script < 2 or n_script < 0.6 * max(1, n_alpha):
                        continue
                    b = ln["box"]
                    ob = [int(b[0] / ps), int(b[1] / ps), int(b[2] / ps), int(b[3] / ps)]
                    # a foreign-script model "reading" text the Latin pass already read well is a misread
                    if any(_iou(ob, r["box"]) > 0.3 or _center_in(ob, r["box"]) for r in latin):
                        continue
                    good.append((ln, n_script))
                total = sum(n for _, n in good)
                strong = any(ln["conf"] >= 0.88 and n >= 4 for ln, n in good)
                # textures (curtains, carpets, tiles) make tesseract "read" exotic scripts: demand real volume
                if total >= 6 and (len(good) >= 2 or strong):
                    good = [ln for ln, _ in good]
                    used_langs += [l for l in have if l not in used_langs]
                    add(good, "probe", ps, lang="+".join(have))
                    notes.append(f"{label} script detected - added {'+'.join(have)}")
        if langs:
            add(_tess(exe, full, used_langs, 11, 120), "full", full_scale, lang="+".join(used_langs))
        if left() > 25:
            enh = ImageOps.autocontrast(ImageOps.grayscale(full), cutoff=2)
            add(_tess(exe, enh, used_langs, 11, 90), "enhanced", full_scale, lang="+".join(used_langs))
        grid = (2, 2) if fast else (3, 3)
        for label, box in imaging.tiles((W, H), *grid, overlap=0.15):
            if left() < 8:
                notes.append("time budget reached: remaining tiles skipped (re-run with --budget to extend)")
                break
            part = img.crop(box)
            s = min(3.0, max(1.0, 1800 / max(part.size)))
            part = part.resize((round(part.width * s), round(part.height * s)), Image.LANCZOS)
            add(_tess(exe, part, used_langs, 11, 90), "tile", s, offset=(box[0], box[1]), lang="+".join(used_langs))
    elif info["rapidocr"]:
        eng = rapidocr_engine()
        if eng is not None:
            backend = "rapidocr"
            used_langs = ["ch+en (RapidOCR default models)"]
            add(_rapid(eng, full), "full", full_scale)
            for label, box in imaging.tiles((W, H), 3, 3, overlap=0.15):
                if left() < 8:
                    notes.append("time budget reached: remaining tiles skipped")
                    break
                part = img.crop(box)
                s = min(3.0, max(1.0, 1600 / max(part.size)))
                part = part.resize((round(part.width * s), round(part.height * s)), Image.LANCZOS)
                add(_rapid(eng, part), "tile", s, offset=(box[0], box[1]))
    if backend is None:
        return {"backend": None, "lines": [], "langs": [], "elapsed_s": round(time.time() - t0, 1),
                "notes": ["no OCR backend: install tesseract (apt/brew/winget) or `pip install rapidocr-onnxruntime`; "
                          "until then read text yourself from zoomed crops (igl.py crop)"]}

    merged: list[dict] = []
    for r in sorted(raw, key=lambda x: -x["conf"]):
        if _alnum(r["text"]) < 2:
            continue
        nt = _norm(r["text"])
        hit = None
        for m in merged:
            if (_norm(m["text"]) == nt or (len(nt) > 3 and (nt in _norm(m["text"]) or _norm(m["text"]) in nt))) \
                    and (_iou(m["box"], r["box"]) > 0.15 or _center_in(r["box"], m["box"])):
                hit = m
                break
        if hit:
            hit["passes"].add(r["pass"])
            hit["conf"] = max(hit["conf"], r["conf"])
        else:
            merged.append({"text": r["text"], "conf": r["conf"], "box": r["box"], "passes": {r["pass"]},
                           "lang": r["lang"]})
    lines, rejected = [], 0
    for m in merged:
        agree = len(m["passes"])
        an = _alnum(m["text"])
        dense = an / max(1, len(m["text"].replace(" ", "")))
        if agree >= 2:
            keep = m["conf"] >= 0.45 and an >= 2
        else:   # single pass: the usual source of texture "text"
            keep = m["conf"] >= 0.6 and an >= 3 and dense >= 0.6 and (an >= 4 or m["conf"] >= 0.8)
        if not keep:
            rejected += 1
            continue
        lines.append({"text": m["text"], "conf": m["conf"], "box": m["box"], "passes": sorted(m["passes"]),
                      "agree": agree, "scripts": scripts_in(m["text"])})
    if rejected:
        notes.append(f"{rejected} low-quality fragment(s) dropped (single-pass, short or symbol-heavy: typical texture noise)")
    lines.sort(key=lambda l: (l["box"][1] // 40, l["box"][0]))
    for i, ln in enumerate(lines, 1):
        ln["id"] = f"T{i}"
    total_scripts: dict[str, int] = {}
    for ln in lines:
        for k, v in ln["scripts"].items():
            total_scripts[k] = total_scripts.get(k, 0) + v
    return {"backend": backend, "langs": used_langs, "lines": lines, "scripts": total_scripts,
            "elapsed_s": round(time.time() - t0, 1), "notes": notes}


def _center_in(a, b) -> bool:
    cx, cy = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    return b[0] <= cx <= b[2] and b[1] <= cy <= b[3]
