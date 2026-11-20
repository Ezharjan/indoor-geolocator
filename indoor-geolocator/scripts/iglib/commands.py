"""Implementations of the igl.py subcommands. Each prints a compact, agent-readable summary."""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import shutil
from pathlib import Path

from . import codes, embed, geo, imaging, knowledge, metadata, ocr, report, revsearch, scoring, social, textmine
from .case import (ATTEMPT_STATUS, CORE_METHODS, DECISIVE, EXCLUDERS, GRADE, KINDS, LEVEL_HELP, LEVELS, OPTIONAL_METHODS,
                   RESOLVED, SOURCE_CAP, SOURCES, STATUS_CAP, Case)
from .common import _DRY, _attempt, _box_from, _http, _new_clue, _print_json, _save_json  # noqa: F401
from .util import IglError, haversine_m, parse_box, parse_latlon, redact, sha256_file, short, table, write_json
from .visual import cmd_compare, cmd_refs, cmd_revsearch, cmd_share, cmd_snapshot  # noqa: F401


# ----------------------------------------------------------------------------- init / scan / views
def cmd_init(a) -> int:
    case = Case.create(Path(a.image), out=Path(a.out) if a.out else None)
    img, info = imaging.open_image(case.image_path)
    meta = metadata.extract(case.image_path)
    thumb = meta.pop("_thumbnail_bytes", None)
    case.data["image"].update({"sha256": sha256_file(case.image_path), "bytes": case.image_path.stat().st_size,
                               "format": info["format"], "size": info["size"], "stored_size": info["stored_size"],
                               "orientation": info["orientation"], "frames": info["frames"]})
    spec = imaging.grid_spec(tuple(info["size"]))
    case.data["image"]["grid"] = spec
    eid, p = case.reserve_file("overview-grid", "jpg", "the photo with a labelled grid (use --cell C3 or C3:E5 to crop)",
                               pinned=True)
    imaging.draw_grid(img, spec).save(p, quality=90)
    write_json(case.root / "input" / "metadata.json", meta)
    created = [eid]
    if thumb and (meta.get("thumbnail") or {}).get("differs"):
        tid, tp = case.reserve_file("exif-thumbnail", "jpg", "embedded EXIF thumbnail - differs from the image "
                                                            "(possible original framing before crop/edit)", pinned=True)
        tp.write_bytes(thumb)
        created.append(tid)
    flags = meta.get("flags", [])
    case.data["auto"]["metadata_flags"] = flags
    auto_clues = []
    gps = meta.get("gps") or {}
    if gps.get("lat") is not None and gps.get("valid"):
        txt = f"EXIF GPS {gps['lat']:.6f}, {gps['lon']:.6f}" + (f", altitude {gps['alt_m']:.0f} m" if gps.get("alt_m")
                                                               is not None else "") + \
              (f", lens heading {gps['img_direction_deg']:.0f}°" if gps.get("img_direction_deg") is not None else "")
        auto_clues.append(_new_clue(case, txt, "metadata", "metadata", "metadata"))
    xf = (meta.get("xmp") or {}).get("fields", {})
    loc_bits = [f"{k}={xf[k]}" for k in ("photoshop:City", "photoshop:State", "photoshop:Country",
                                         "Iptc4xmpCore:Location", "Iptc4xmpCore:CountryCode") if k in xf]
    loc_bits += [f"IPTC {k}={meta['iptc'][k]}" for k in ("City", "Sublocation", "ProvinceState", "CountryName",
                                                        "CountryCode") if k in (meta.get("iptc") or {})]
    if loc_bits:
        auto_clues.append(_new_clue(case, "embedded location fields: " + "; ".join(str(b) for b in loc_bits)[:400],
                                    "metadata", "metadata", "metadata"))
    t = meta.get("time") or {}
    if t.get("offset"):
        zs = t.get("zones_with_offset") or []
        txt = (f"EXIF UTC offset {t['offset']} at {t.get('local')}: consistent with {len(zs)} zones, e.g. "
               f"{', '.join(zs[:10])}" if zs else
               f"EXIF UTC offset {t['offset']} at {t.get('local')} (zone list unavailable here: `pip install tzdata`)")
        auto_clues.append(_new_clue(case, txt, "light-time", "metadata", "metadata"))
    strong = bool(auto_clues)
    _attempt(case, "metadata", "results" if (strong or flags) else "no_results",
             "; ".join(flags)[:600] or "no metadata of note", files=[], save=False)
    net_state = None
    if not getattr(a, "no_probe", False):
        net_state = _probe_network()
        case.data["auto"]["network"] = net_state
    case.event("init", f"metadata read: {len(flags)} notable fields; overview grid {spec['cols']}x{spec['rows']}"
               + (f"; CLI network: {', '.join(net_state['reachable']) or 'none'} reachable" if net_state else ""))
    print(f"CASE   {case.root}")
    print(f"IMAGE  {case.data['image']['file']}  {info['size'][0]}x{info['size'][1]} {info['format']}"
          f"{' (EXIF-rotated)' if info['orientation'] not in (1, None) else ''}")
    print(f"VIEW   {p}  (grid {spec['cols']} cols A.. x {spec['rows']} rows 1..)")
    if len(created) > 1:
        print(f"THUMB  {case.file_path(created[1])}  <- embedded thumbnail differs: LOOK at it")
    print("\nMETADATA")
    for f in flags or ["(nothing notable)"]:
        print(f"  - {f}")
    if auto_clues:
        print("\nAUTO-RECORDED CLUES (link them once candidates exist): " + ", ".join(auto_clues))
    if net_state:
        print("\nNETWORK (what the CLI itself can reach from here, right now)")
        print(f"  reachable:    {', '.join(net_state['reachable']) or 'none'}")
        if net_state.get("limited"):
            print(f"  rate-limited: {', '.join(net_state['limited'])}  (shared address: these refuse requests at the "
                  "moment; the commands fall back or say so)")
        if net_state["unreachable"]:
            print(f"  unreachable:  {', '.join(net_state['unreachable'])}")
        print(f"  headless browser (revsearch, refs, snapshot): {net_state['browser']}")
        print(f"  similarity ordering of reference photos: {embed.state()['note']}")
        if not net_state["reachable"]:
            print("  => the CLI is OFFLINE here. Do every online step with YOUR OWN tools (web search, web fetch, browser),\n"
                  "     record what they return with note / cand / log, and use `geo ... --print-url` for API URLs.")
        else:
            print("  => use the CLI's online commands where they are reachable, and your own web search / fetch / browser "
                  "tools for everything else (Google Lens, maps photos, listings, social platforms).")
    missing = _missing_extras()
    if missing:
        print("\nMISSING EXTRAS that matter for accuracy (install once in this environment, then carry on):")
        for what, fix in missing:
            print(f"  - {what}: {fix}")
    print("\nNEXT  1) LOOK at the photo and the grid view, then record what you think BEFORE any tool output:\n"
          f"         igl.py note {case.root} \"Hypotheses: scene=...; 1) <place> because ...; 2) ...; 3) ...; would "
          "discriminate: ...\" --kind hypothesis --status inferred --source image\n"
          f"      2) igl.py scan {case.root}")
    return 0


def _missing_extras() -> list[tuple[str, str]]:
    """Optional packages without which the comparison tools or the online commands are blind."""
    import importlib.util
    out = []
    if importlib.util.find_spec("cv2") is None or importlib.util.find_spec("numpy") is None:
        out.append(("OpenCV + numpy (QR codes and barcodes; COPY / SAME SCENE tests in revsearch, refs, compare)",
                    "pip install opencv-python-headless numpy"))
    if importlib.util.find_spec("playwright") is None:
        out.append(("Playwright + Chromium (reverse image search, reference photos with `refs`, snapshots)",
                    "pip install playwright && playwright install chromium"))
    if importlib.util.find_spec("onnxruntime") is None or importlib.util.find_spec("numpy") is None:
        out.append(("onnxruntime + numpy (reference photos and search hits shown most-similar-first instead of in the "
                    "search engine's order)", "pip install onnxruntime numpy"))
    return out


NET_PROBES = {
    "nominatim": "https://nominatim.openstreetmap.org/status?format=json",
    "photon": "https://photon.komoot.io/api/?q=Berlin&limit=1",
    "overpass": "https://overpass-api.de/api/status",
    "commons": "https://commons.wikimedia.org/w/api.php?action=query&meta=siteinfo&format=json",
    "wikidata": "https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Louvre&language=en&format=json&limit=1",
    "yandex": "https://yandex.com/images/",
    "tineye": "https://tineye.com/",
    "baidu": "https://graph.baidu.com/pcpage/index?tpl_from=pc",
    "brave images (refs)": "https://search.brave.com/",
    "startpage images (refs)": "https://www.startpage.com/",
    "uguu (share)": "https://uguu.se/",
}


def _probe_network(timeout: float = 5.0) -> dict:
    from .net import probe
    res = probe(NET_PROBES, timeout=timeout)
    ok, why = revsearch.available()
    return {"checked": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "reachable": [k for k, v in res.items() if v["ok"]],
            "limited": [k for k, v in res.items() if v.get("state") == "rate_limited"],
            "unreachable": [f"{k} ({v['note']})" for k, v in res.items()
                            if not v["ok"] and v.get("state") != "rate_limited"],
            "browser": "available" if ok else f"unavailable - {why}"}


def cmd_scan(a) -> int:
    case = Case(Path(a.case))
    img, _ = imaging.open_image(case.image_path)
    out: dict = {}
    print("scanning (OCR multi-pass, QR/barcodes, text patterns, tiles) ...", flush=True)
    if not a.no_ocr:
        o = ocr.run(img, langs=a.langs.split("+") if a.langs else None, budget_s=a.budget, fast=a.fast)
        out["ocr"] = o
    else:
        out["ocr"] = {"backend": None, "lines": [], "notes": ["skipped (--no-ocr)"]}
    out["codes"] = codes.detect(img) if not a.no_codes else {"codes": [], "notes": ["skipped (--no-codes)"]}
    texts = [l["text"] for l in out["ocr"]["lines"]] + [c["display"] for c in out["codes"]["codes"]]
    out["text_signals"] = textmine.mine(texts, phone_regions=(a.regions.split(",") if a.regions else None))
    jid, jp = case.reserve_file("scan", "json", "machine scan: OCR lines (T#), decoded codes (Q#), text signals")
    write_json(jp, out)
    items = [(l["id"], tuple(l["box"])) for l in out["ocr"]["lines"]]
    for i, c in enumerate(out["codes"]["codes"], 1):
        c["id"] = f"Q{i}"
        items.append((c["id"], tuple(c["box"])))
    write_json(jp, out)
    aid, ap = case.reserve_file("scan-annotated", "jpg", "photo with OCR line boxes (T#) and code boxes (Q#)")
    imaging.annotate(img, items).save(ap, quality=88)
    text_sheet = None
    if out["ocr"]["lines"]:                           # the lines, cut out and enlarged: one look confirms or refutes them
        crops = []
        for l in sorted(out["ocr"]["lines"], key=lambda l: (-l["agree"], -l["conf"]))[:24]:
            try:
                crops.append((f"{l['id']} {short(l['text'], 34)}", imaging.view_of(imaging.crop(img, tuple(l["box"]), pad=0.35),
                                                                                  min_side=420)))
            except IglError:
                continue
        if crops:
            tid, tp_ = case.reserve_file("text-crops", "jpg", "enlarged crops of the OCR lines (T#): read them yourself")
            imaging.contact_sheet(crops, cols=4, cell=384).save(tp_, quality=88)
            text_sheet = (tid, tp_)
    tdir = case.work / "tiles"
    if tdir.exists():
        shutil.rmtree(tdir)
    tdir.mkdir(parents=True)
    tile_paths = []
    for label, box in imaging.tiles(img.size, a.grid_cols, a.grid_rows, overlap=0.15):
        v = imaging.view_of(img.crop(box), min_side=1200)
        tp = tdir / f"tile_{label}_{box[0]}-{box[1]}-{box[2]}-{box[3]}.jpg"
        v.save(tp, quality=90)
        tile_paths.append(tp)
    o = out["ocr"]
    st = "results" if o.get("lines") else ("no_results" if o.get("backend") else "unavailable")
    _attempt(case, "text_ocr", st, f"{o.get('backend') or 'no backend'}: {len(o.get('lines', []))} language-like "
                                   f"line(s) [{', '.join(short(l['text'], 30) for l in o.get('lines', [])[:8])}]"
                                   + (f"; {o.get('weak_count', 0)} noise fragment(s) set aside" if o.get("weak_count") else ""),
             engine=o.get("backend"), files=[jid, aid] + ([text_sheet[0]] if text_sheet else []), save=False)
    cd = out["codes"]
    st = "results" if cd["codes"] else ("unavailable" if cd.get("notes") and "OpenCV missing" in " ".join(cd["notes"])
                                        else "no_results")
    _attempt(case, "codes", st, f"{len(cd['codes'])} code(s): " + "; ".join(short(c['display'], 60) for c in cd["codes"]),
             files=[jid, aid] if cd["codes"] else [jid], save=False)
    case.data["auto"]["scan"] = {"ocr_backend": o.get("backend"), "ocr_lines": len(o.get("lines", [])),
                                 "codes": len(cd["codes"]), "scan_file": jid, "annotated": aid}
    case.event("scan", f"scan: {len(o.get('lines', []))} OCR lines, {len(cd['codes'])} codes, tiles {a.grid_cols}x{a.grid_rows}")
    print(f"\nTEXT the OCR engine is fairly sure of ({o.get('backend') or 'none'}; langs "
          f"{'+'.join(o.get('langs', [])) or '-'}; {o.get('elapsed_s', 0)} s) - still HINTS: confirm each on its crop "
          "before using it")
    lines = sorted(o.get("lines", []), key=lambda l: (-l["agree"], -l["conf"]))
    if lines:
        print(table([[l["id"], f"{l['conf']:.2f}", l["agree"], ",".join(l["passes"]), short(l["text"], 70),
                      ",".join(map(str, l["box"]))] for l in lines[:45]],
                    ["id", "conf", "agree", "passes", "text", "box"]))
        if len(lines) > 45:
            print(f"  ... {len(lines) - 45} more in {jp.name}")
        if text_sheet:
            print(f"  zoomed crops of these lines, one look to confirm them: {text_sheet[0]}  {text_sheet[1]}")
    else:
        print("  none" + (" (no OCR engine)" if not o.get("backend") else
                          ": the engine read no language-like text. That is common for rooms and proves nothing: read "
                          "the tiles yourself (small print, stylised logos, screens, labels, spines, plaques)"))
    if getattr(a, "all", False) and o.get("weak"):
        print("\n  fragments set aside by the precision filter (texture noise is the norm; NOT text signals):")
        print(table([[f"{w['conf']:.2f}", w["agree"], short(w["text"], 50), ",".join(map(str, w["box"]))]
                     for w in o["weak"][:30]], ["conf", "agree", "fragment", "box"]))
    for n in o.get("notes", []):
        print(f"  note: {n}")
    print("\nCODES")
    if cd["codes"]:
        for c in cd["codes"]:
            extra = {k: v for k, v in c.items() if k not in ("raw", "display", "box", "method", "type", "id", "secret")}
            print(f"  {c['id']} {c['type']} at {c['box']}: {short(c['display'], 120)}")
            print(f"      -> {json.dumps(extra, ensure_ascii=False)[:400]}")
    else:
        print("  none decoded" + ("".join(f" ({n})" for n in cd.get("notes", []))))
    ts = out["text_signals"]
    print("\nTEXT SIGNALS (patterns in the lines above and in decoded codes; machine hints)")
    if ts:
        for k, v in ts.items():
            print(f"  {k}: {short(json.dumps(v, ensure_ascii=False), 300)}")
    else:
        print("  none")
    if any(k != "LATIN" for k in (o.get("scripts") or {})):
        print("  a non-Latin script here comes from OCR alone: an ornament, a carpet or a tiled wall can produce it. "
              "Treat it as real only after you have read actual words on a crop.")
    if o.get("backend") == "tesseract" and ts:
        hinted, better = ocr.suggest_langs(ts, o.get("langs", []), ocr.backends()["tesseract_langs"])
        if better:
            print(f"\nSUGGESTION  text signals point to {', '.join(hinted[:6])}: re-read with the local language pack(s) "
                  f"(accents and letters like ß, ç, ł are lost otherwise):\n"
                  f"            igl.py scan {case.root} --langs {'+'.join(better + ['eng'])}")
    print(f"\nFILES  {jp}\n       {ap}")
    print("\nVISUAL SWEEP - open EVERY tile below (overlapping, upscaled): your own eyes are the primary reader here.\n"
          "Read all text yourself, name fixed fittings, note what could identify the venue (logos, unique art, the view).\n"
          "Crop what matters with `igl.py crop` (tiles are scratch and get deleted at finalize):")
    for tp in tile_paths:
        print(f"  {tp}")
    return 0


def cmd_crop(a) -> int:
    case = Case(Path(a.case))
    if getattr(a, "of", None):                      # zoom into another evidence image (a reference photo, a sheet)
        if a.cell:
            raise IglError("--cell refers to the grid of the case photo: with --of use --rel x0,y0,x1,y1 (0-1) or --box")
        src = case.resolve_files([a.of])[0]
        img, _ = imaging.open_image(case.file_path(src))
    else:
        src = None
        img, _ = imaging.open_image(case.image_path)
    box = _box_from(a, img.size, case)
    if not box:
        raise IglError("give --box x0,y0,x1,y1 (pixels), --cell C3[:E5] (grid view) or --rel x0,y0,x1,y1 (0-1)")
    part = imaging.crop(img, box, pad=a.pad)
    if a.enhance:
        part = imaging.enhance(part, a.enhance.split(","))
    if a.rotate:
        part = part.rotate(-a.rotate, expand=True, fillcolor=(255, 255, 255))
    if a.flip:
        from PIL import ImageOps
        part = ImageOps.mirror(part)
    view = imaging.view_of(part, scale=a.scale)
    what = a.what or (f"crop {box}" + (f" of {src}" if src else "") + (f" enhanced {a.enhance}" if a.enhance else "")
                      + (" mirrored" if a.flip else ""))
    eid, p = case.reserve_file(a.label or "crop", "jpg", what)
    view.save(p, quality=92)
    case.save()
    print(f"{eid}  {p}\n     box={','.join(map(str, box))} source px {part.size[0]}x{part.size[1]} -> view "
          f"{view.size[0]}x{view.size[1]}")
    return 0


def cmd_tiles(a) -> int:
    case = Case(Path(a.case))
    img, _ = imaging.open_image(case.image_path)
    cols, rows = (int(x) for x in a.grid.lower().split("x"))
    tdir = case.work / f"tiles_{cols}x{rows}"
    tdir.mkdir(parents=True, exist_ok=True)
    for label, box in imaging.tiles(img.size, cols, rows, overlap=a.overlap):
        tp = tdir / f"tile_{label}_{box[0]}-{box[1]}-{box[2]}-{box[3]}.jpg"
        imaging.view_of(img.crop(box), min_side=1200).save(tp, quality=90)
        print(tp)
    return 0


# ----------------------------------------------------------------------------- knowledge
def cmd_countries(a) -> int:
    rows = knowledge.filter_countries(
        plug_all=[p.upper() for p in a.plug] if a.plug else None,
        plug_any=[p.upper() for p in a.plug_any.split(",")] if a.plug_any else None,
        calling=a.calling, tld=a.tld, currency=a.currency, drive=a.drive, lang=a.lang, script=a.script,
        week=a.week, clock=a.clock, temp=a.temp, paper=a.paper, emergency=a.emergency, freq=a.freq,
        voltage=a.voltage, min_pct=a.min_pct, include_non_iso=a.all)
    print(f"{len(rows)} countries/territories match")
    print(table([[r["iso"], r["name"], r["why"]] for r in rows[:a.limit]], ["iso", "name", "matched"], maxw=80))
    if len(rows) > a.limit:
        print(f"... {len(rows) - a.limit} more (use --limit)")
    if a.case and a.clue:
        case = Case(Path(a.case))
        clue = case.clue(a.clue)
        cap = _lr_cap(clue)
        lr = min(a.lr or cap, cap)
        added, linked = 0, 0
        for r in rows:
            existing = [c for c in case.data["candidates"].values() if c["level"] == "country" and
                        (c.get("iso") == r["iso"] or c["name"].lower() == r["name"].lower())]
            if existing:
                cid = existing[0]["id"]
            else:
                cid = case.next_id("C")
                case.data["candidates"][cid] = {"id": cid, "name": r["name"], "level": "country", "parent": None,
                                                "iso": r["iso"], "lat": None, "lon": None, "status": "open",
                                                "files": [], "time": dt.datetime.now().astimezone().isoformat(
                                                    timespec="seconds"), "note": "added by countries filter"}
                added += 1
            _put_evidence(case, clue["id"], cid, lr, lr, f"matches {r['why']}", [])
            linked += 1
        case.event("link", f"countries filter via {clue['id']}: {linked} countries linked x{lr:g} ({added} new candidates)")
        print(f"\nlinked {clue['id']} to {linked} country candidates with LR {lr:g} ({added} added)")
    return 0


def cmd_lookup(a) -> int:
    kind, value = a.kind, " ".join(a.value)
    if kind == "phone":
        res = textmine.mine([value], phone_regions=[a.region] if a.region else None).get("phones", [])
        _print_json(res or {"result": "no valid phone number found (give +CC format or --region XX)"})
    elif kind == "barcode":
        from .codes import _ean_ok
        digits = "".join(ch for ch in value if ch.isdigit())
        _print_json({"digits": digits, "valid_checksum": _ean_ok(digits), "gs1": knowledge.gs1_lookup(digits),
                     "note": "GS1 prefix = registration country of the brand owner, not where it was sold"})
    elif kind == "country":
        iso, rec = knowledge.country(value)
        _print_json({"iso": iso, **rec})
    elif kind == "plug":
        for t in value.upper().replace(",", " ").split():
            isos = [r["iso"] for r in knowledge.filter_countries(plug_any=[t])]
            print(f"Type {t}: {knowledge.PLUG_SHAPES.get(t, '?')}\n  used in {len(isos)}: {', '.join(isos)}")
    elif kind == "plugs":
        for t, d in knowledge.PLUG_SHAPES.items():
            print(f"Type {t}: {d}")
    elif kind == "currency":
        isos = knowledge.currency_countries(value)
        former = knowledge.former_currency(value)
        _print_json({"current": isos, "former": [{"country": i, **c} for i, c in former]})
    elif kind == "tld":
        _print_json({"tld": value, "country": knowledge.tld_country(value)})
    elif kind == "text":
        _print_json(textmine.mine([value], phone_regions=[a.region] if a.region else None))
    return 0


# ----------------------------------------------------------------------------- geo
_STOP = {"the", "hotel", "hotels", "and", "&", "de", "la", "le", "der", "die", "das", "of", "by", "a"}


def _tokens(name: str) -> set[str]:
    import unicodedata
    t = unicodedata.normalize("NFKD", str(name).lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return {w for w in re.split(r"[\W_]+", t) if w and w not in _STOP}


def _same_place(c: dict, pl: dict, metres: float = 40.0) -> bool:
    """Same candidate if close together AND the names agree (equal, or most significant words shared):
    'The Fairmont Palliser' == 'Fairmont Palliser'; a cafe inside a hotel stays separate."""
    if c.get("lat") is None or pl.get("lat") is None:
        return False
    if haversine_m(c["lat"], c["lon"], pl["lat"], pl["lon"]) >= metres:
        return False
    a, b = _tokens(c["name"]), _tokens(pl.get("name", ""))
    if c["name"].lower() == str(pl.get("name", "")).lower():
        return True
    return bool(a and b) and len(a & b) / min(len(a), len(b)) >= 0.6


def _maybe_add(case: Case | None, places: list[dict], level: str | None, parent: str | None, note: str) -> list[str]:
    if not (case and level):
        return []
    if level not in LEVELS:
        raise IglError(f"--add must be one of {', '.join(LEVELS)}")
    par = case.cand(parent)["id"] if parent else None
    ids = []
    for pl in places:
        dup = [c for c in case.data["candidates"].values() if c["level"] == level and _same_place(c, pl)]
        if dup:
            if dup[0]["id"] not in ids:
                ids.append(dup[0]["id"])
            addr = pl.get("display") or (pl.get("address") if isinstance(pl.get("address"), str) else None)
            for k, v in (("address", addr), ("osm", pl.get("osm")), ("wikidata", pl.get("wikidata"))):
                if v and not dup[0].get(k):                 # enrich the existing candidate, never overwrite
                    dup[0][k] = v
            continue
        cid = case.next_id("C")
        case.data["candidates"][cid] = {"id": cid, "name": pl.get("name") or pl.get("display") or "?", "level": level,
                                        "parent": par, "lat": pl.get("lat"), "lon": pl.get("lon"),
                                        "address": pl.get("display") or (pl.get("address") if isinstance(
                                            pl.get("address"), str) else None), "osm": pl.get("osm"),
                                        "wikidata": pl.get("wikidata"), "status": "open", "files": [], "note": note,
                                        "time": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
        ids.append(cid)
    case.event("cand", f"{len(ids)} {level} candidates added from {note}: {', '.join(ids[:20])}")
    if level != "country" and not par and ids:
        print("note: added without --parent: attach them to their city or country (`cand <case> C# --parent C#`)")
    return ids


def cmd_geo(a) -> int:
    if getattr(a, "print_url", False):
        return _geo_print_urls(a)
    return _geo(a)


def _geo_print_urls(a) -> int:
    """Run the geo command with a recording HTTP client and print the URLs it would have requested."""
    import contextlib
    import io
    _DRY.clear()
    note = ""
    a.case, a.add, a.save = None, None, False            # nothing is written in this mode
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            _geo(a)
        except IglError as e:
            note = str(e)
    urls = [u for h in _DRY for u in h.printed]
    if not urls:
        raise IglError(f"no request to print{': ' + note if note else ''} (for `geo poi --area`, resolve the area "
                       "first with `geo search` and pass --bbox s,w,n,e)")
    print("Request URL(s), first choice first (open with your own web-fetch or browser tool; nothing was sent):")
    for u in urls:
        print(f"  {u}")
    if note:
        print(f"note: {note}")
    print("Record what they return with `igl.py cand` / `igl.py note`, and log the method.")
    return 0


def _geo(a) -> int:
    case = Case(Path(a.case)) if getattr(a, "case", None) else None
    dry = bool(getattr(a, "print_url", False))

    def _http(case_, service=None, timeout=25.0, retries=3):        # noqa: F811 - shadows the module helper
        return globals()["_http"](case_, service, timeout, retries, dry=dry)

    if a.geo_cmd == "search":
        http = _http(case, "Nominatim/Photon")
        near = parse_latlon(a.near) if a.near else None
        r = geo.geocode(http, a.query, country=a.country, limit=a.limit, near=near)
        print(f"{r['service']}: {len(r['results'])} result(s)" + ("" if r["ok"] else f" - {r.get('error')}"))
        print(table([[i, f"{x['lat']:.6f},{x['lon']:.6f}", f"{x['class']}/{x['type']}", short(x["display"], 90), x["osm"]]
                     for i, x in enumerate(r["results"], 1)], ["#", "lat,lon", "class/type", "address", "osm"]))
        ids = _maybe_add(case, r["results"], a.add, a.parent, f"geocode '{a.query}'")
        eid = _save_json(case, f"geocode-{a.query}", f"geocoder results for '{a.query}'", r) if a.save else None
        if ids:
            print("added candidates: " + ", ".join(ids))
        if eid:
            print(f"saved {eid}")
    elif a.geo_cmd == "reverse":
        lat, lon = parse_latlon(a.at)
        r = geo.reverse(_http(case, "Nominatim/Photon"), lat, lon)
        _print_json(r)
    elif a.geo_cmd == "poi":
        http = _http(case, "Overpass")
        if a.bbox:
            s, w, n, e = (float(x) for x in a.bbox.split(","))
            area = {"bbox": [s, w, n, e]}
        elif a.around:
            parts = a.around.split(",")
            area = {"around": [float(parts[0]), float(parts[1]), float(parts[2]) if len(parts) > 2 else 1000]}
        elif a.area:
            g = geo.geocode(_http(case, "Nominatim/Photon"), a.area, country=a.country, limit=1)
            if not g["results"] or not g["results"][0].get("bbox"):
                raise IglError(f"could not resolve area {a.area!r} to a bounding box")
            bb = g["results"][0]["bbox"]
            area = {"bbox": [bb[0], bb[2], bb[1], bb[3]]}
            print(f"area '{a.area}' -> bbox {area['bbox']} ({g['results'][0]['display']})")
        else:
            raise IglError("give --area NAME, --bbox s,w,n,e or --around lat,lon,radius_m")
        ql = geo.build_poi_ql(a.tag or [], a.name, a.brand, area, near=a.near_tag, limit=a.limit)
        r = geo.overpass(http, ql)
        places = geo.elements_to_places(r["elements"])
        print(f"Overpass: {len(places)} feature(s)" + (f" via {r.get('server')}" if r["ok"] else f" - UNAVAILABLE: {r.get('error')}")
              + (f"  WARNING {r['warning']}" if r.get("warning") else ""))
        if not r["ok"] and not dry:                 # Overpass is often unreachable from cloud networks: partial fallback
            fb = geo.photon_poi(_http(case, "Nominatim/Photon"), a.tag or [], a.name, a.brand, area, limit=a.limit)
            if fb["ok"] and fb["places"]:
                places = fb["places"]
                r = {**r, "fallback": fb["service"]}
                print(f"FALLBACK {fb['service']}: {len(places)} feature(s). This is a PARTIAL list (name and tag search "
                      "in the box, at most 50): complete it with your web search (\"<type> in <area>\", booking and map "
                      "listings) before treating it as the whole category" +
                      ("; --near-tag co-location was NOT applied" if a.near_tag else ""))
            else:
                print(f"fallback {fb['service']}: {fb.get('error') or 'nothing found'}")
        print(table([[i, short(p["name"], 40), f"{p['lat']:.6f},{p['lon']:.6f}", short(p["address"], 50),
                      short(json.dumps(p["tags"], ensure_ascii=False), 70), p["osm"]] for i, p in enumerate(places, 1)][:a.limit],
                    ["#", "name", "lat,lon", "address", "tags", "osm"]))
        if not r["ok"] and not r.get("fallback"):
            print("query was:\n" + ql)
            print("other routes: your own web search (\"<type or brand> in <area>\"), `igl.py geo search \"<brand or "
                  "name> <area>\" --limit 40`, `igl.py geo sparql` (Wikidata), the brand's own location list, or "
                  "overpass-turbo.eu in a browser. Log candidate_enum as unavailable only if every route fails.")
        ids = _maybe_add(case, places, a.add, a.parent, "Overpass query")
        eid = _save_json(case, "overpass", "Overpass query and results", {"query": ql, **r, "places": places}) \
            if (a.save and case) else None
        if ids:
            print("added candidates: " + ", ".join(ids))
        if eid:
            print(f"saved {eid}")
    elif a.geo_cmd == "photos":
        http = _http(case, "Wikimedia Commons")
        if a.at:
            lat, lon = parse_latlon(a.at)
            r = geo.commons_geosearch(http, lat, lon, a.radius, a.limit)
        elif a.category:
            r = geo.commons_category(http, a.category, a.limit)
        elif a.text:
            r = geo.commons_search(http, a.text, a.limit)
        else:
            raise IglError("give --at lat,lon, --category NAME or --text WORDS")
        files = r.get("files", [])
        print(f"Commons: {len(files)} file(s)" + ("" if r["ok"] else f" - UNAVAILABLE: {r.get('error')}"))
        print(table([[i, short(f["title"].replace("File:", ""), 60), f.get("dist_m", ""), short(f.get("date", ""), 19),
                      short(f.get("description", ""), 60)] for i, f in enumerate(files, 1)],
                    ["#", "title", "dist m", "date", "description"]))
        if a.sheet and case and files:
            imgs = []
            tdir = case.work / "commons"
            tdir.mkdir(exist_ok=True)
            from PIL import Image
            for i, f in enumerate(files[:a.sheet], 1):
                if not f.get("thumb"):
                    continue
                dest = tdir / f"{i:02d}.jpg"
                if http.download(f["thumb"], dest):
                    try:
                        imgs.append((f"{i}. {f['title'].replace('File:', '')}", Image.open(dest).convert("RGB")))
                    except Exception:  # noqa: BLE001
                        pass
            if imgs:
                sid, sp = case.reserve_file("commons-sheet", "jpg", f"contact sheet of {len(imgs)} Commons photos "
                                            f"({a.at or a.category or a.text})")
                imaging.contact_sheet(imgs).save(sp, quality=85)
                jid = _save_json(case, "commons", "Commons file list for the contact sheet", r)
                print(f"sheet {sid} {sp}  (list {jid})")
    elif a.geo_cmd == "wikidata":
        http = _http(case, "Wikidata")
        if a.query.upper().startswith("Q") and a.query[1:].isdigit():
            _print_json(geo.wikidata_entity(http, a.query.upper(), a.lang))
        else:
            r = geo.wikidata_search(http, a.query, a.lang, a.limit)
            print(table([[x["qid"], x["label"], short(x.get("description") or "", 80)] for x in r["results"]],
                        ["qid", "label", "description"]) if r["ok"] else f"UNAVAILABLE: {r.get('error')}")
            if r["ok"] and r["results"] and a.details:
                _print_json(geo.wikidata_entity(http, r["results"][0]["qid"], a.lang))
    elif a.geo_cmd == "sparql":
        q = a.query
        if q.startswith("@"):
            q = Path(q[1:]).read_text(encoding="utf-8")
        r = geo.wikidata_sparql(_http(case, "Wikidata Query Service", timeout=70, retries=0), q)
        if not r["ok"]:
            print(f"Wikidata Query Service UNAVAILABLE: {r.get('error')}")
            return 0
        print(f"{len(r['rows'])} row(s)")
        print(table([[short(str(row.get(v, "")).replace("http://www.wikidata.org/entity/", ""), 48) for v in r["vars"]]
                     for row in r["rows"][:a.limit]], r["vars"]))
        if len(r["rows"]) > a.limit:
            print(f"... {len(r['rows']) - a.limit} more row(s) (--limit)")
        places = geo.sparql_places(r)
        ids = _maybe_add(case, places, a.add, a.parent, "Wikidata SPARQL")
        if a.add and not places:
            print("nothing added: select an item (?item), its label (?itemLabel) and coordinates (?coord, P625)")
        eid = _save_json(case, "sparql", "Wikidata SPARQL query and results", {"query": q, **r}) if (a.save and case) else None
        if ids:
            print("added candidates: " + ", ".join(ids))
        if eid:
            print(f"saved {eid}")
    elif a.geo_cmd == "wigle":
        r = geo.wigle_ssid(_http(case, "WiGLE (user key)", retries=1), a.ssid, parse_latlon(a.near) if a.near else None,
                           a.box, a.like)
        if not r["ok"]:
            print(("UNAVAILABLE: " if r.get("unavailable") else "FAILED: ") + str(r.get("error")))
            return 0
        print(f"WiGLE: {r.get('total')} network(s) named {a.ssid!r}" + (" (pattern)" if a.like else ""))
        print(table([[i, short(x["ssid"] or "", 32), f"{x['lat']:.5f},{x['lon']:.5f}", short(x["address"], 60),
                      short(str(x.get("last_seen") or ""), 10)] for i, x in enumerate(r["results"][:a.limit], 1)],
                    ["#", "ssid", "lat,lon", "where", "last seen"]))
        ids = _maybe_add(case, r["results"][:a.limit], a.add, a.parent, f"WiGLE SSID '{a.ssid}'")
        if ids:
            print("added candidates: " + ", ".join(ids))
        print("SSIDs repeat (chains, ISP defaults): treat a hit as `reported` until the place is confirmed. A home "
              "network name points at a private residence (hard rule 11).")
    elif a.geo_cmd == "weather":
        lat, lon = parse_latlon(a.at)
        day, hour = a.date, None
        if a.time:
            t = dt.datetime.fromisoformat(a.time.replace("Z", ""))
            day, hour = day or t.date().isoformat(), t.hour
        if not day and case:
            local = (json.loads((case.root / "input" / "metadata.json").read_text(encoding="utf-8")).get("time") or {}).get("local")
            if local:
                t = dt.datetime.fromisoformat(local.replace("Z", ""))
                day, hour = t.date().isoformat(), t.hour
        if not day:
            raise IglError("give --date YYYY-MM-DD or --time ISO (or --case with an EXIF capture time)")
        r = geo.weather_at(_http(case, "Open-Meteo"), lat, lon, day, hour)
        _print_json(r)
        if r.get("ok"):
            print("reanalysis grid ~10-25 km: regional weather, not the street. Use it as `reported`, and only for "
                  "consistency with what the photo shows (snow, rain, sun, darkness).")
    elif a.geo_cmd == "timezone":
        lat, lon = parse_latlon(a.at)
        when = a.time
        if not when and case:
            meta_t = (json.loads((case.root / "input" / "metadata.json").read_text(encoding="utf-8")).get("time") or {})
            when = meta_t.get("local")
        r = geo.timezone_at(_http(case, "timeapi.io"), lat, lon, when)
        _print_json(r)
        if r.get("ok") and when and not r.get("offset_at_time"):
            print("note: could not compute the offset at capture time (no zone database: `pip install tzdata`)")
        if case and r.get("offset_at_time"):
            off = (json.loads((case.root / "input" / "metadata.json").read_text(encoding="utf-8")).get("time") or {}).get("offset")
            if off:
                print(f"EXIF offset {off} vs zone offset at capture {r['offset_at_time']}: "
                      f"{'CONSISTENT' if off == r['offset_at_time'] else 'INCONSISTENT'}")
    return 0


def cmd_sun(a) -> int:
    lat, lon = parse_latlon(a.at)
    t = dt.datetime.fromisoformat(a.time.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise IglError("--time needs an offset, e.g. 2024-05-01T15:30+02:00 (EXIF local time + OffsetTimeOriginal)")
    az, el = geo.sun_position(lat, lon, t)
    print(json.dumps({"azimuth_deg": az, "elevation_deg": el, "compass": geo.compass(az),
                      "meaning": "sunlight travels FROM azimuth; a sunlit patch on the floor lies on the opposite side of "
                                 "the window; elevation < 0 sunset/night, < -6 dark (civil twilight over)"}, indent=1))
    return 0


def cmd_bearing(a) -> int:
    lat1, lon1 = parse_latlon(a.frm)
    if a.to.strip().lower() == "qibla":
        lat2, lon2 = geo.KAABA
        target = "the Kaaba, Mecca (qibla)"
    else:
        lat2, lon2 = parse_latlon(a.to)
        target = f"{lat2:.6f},{lon2:.6f}"
    b = geo.bearing_deg(lat1, lon1, lat2, lon2)
    back = geo.bearing_deg(lat2, lon2, lat1, lon1)
    out = {"from": [lat1, lon1], "to": target, "distance_m": round(haversine_m(lat1, lon1, lat2, lon2)),
           "bearing_deg": b, "compass": geo.compass(b), "back_bearing_deg": back}
    if a.facing is not None:
        diff = (b - a.facing + 540) % 360 - 180
        out["angle_off_facing_deg"] = round(diff, 1)
        out["in_view"] = ("yes, near the centre of the view" if abs(diff) <= 30 else
                          "possibly, at the side of the view" if abs(diff) <= 70 else
                          "no: behind or beside the facade" if abs(diff) > 90 else "barely, only at a steep angle")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


# ----------------------------------------------------------------------------- social media (place-focused)
SOCIAL_SERVICE = {"bluesky": "Bluesky API", "mastodon": "Mastodon API", "flickr": "Flickr public feeds",
                  "lemmy": "Lemmy API", "openverse": "Openverse API"}


def cmd_social(a) -> int:
    case = Case(Path(a.case)) if getattr(a, "case", None) else None
    if a.social_cmd == "links":
        rows = social.links(a.query, tag=a.tag, at=parse_latlon(a.at) if a.at else None,
                            only=a.only.split(",") if a.only else None)
        for kind, title in (("engine", "Public index, no login (search engines and open search pages):"),
                            ("native", "Platform search - open in a browser tool (many need the user's own login):")):
            sel = [r for r in rows if r["kind"] == kind]
            if sel:
                print(title)
                for r in sel:
                    print(f"  {r['platform']:<12} {r['note']}\n      {r['url']}")
        print("\nSearch the PLACE (names, strings, hashtags, objects, the photo itself) - never the people in it.\n"
              "Log each platform: igl.py log <case> social_search --status results|no_results|blocked "
              "--engine <platform> --query \"...\" --detail \"...\"")
        return 0
    sources = list(social.SOURCES) if a.sources == "all" else [s.strip().lower() for s in a.sources.split(",") if s.strip()]
    http = None
    for s in sources:
        http = _http(case, SOCIAL_SERVICE.get(s, s))
    res = social.search(http or _http(case), a.query, sources, tag=a.tag, limit=a.limit, instance=a.instance,
                        lang=a.lang)
    items: list[dict] = []
    for s in sources:
        r = res[s]
        its = [i for i in r["items"] if i["thumbs"] or not a.images_only]
        extra = f" (tag #{r['tag']})" if r.get("tag") else (f" (tags {r['tags']})" if r.get("tags") else "")
        print(f"{s}{extra}: " + (f"{len(its)} item(s)" if r["ok"] else f"UNAVAILABLE - {r.get('error')}"))
        items.extend(its)
        if case:
            status = ("results" if its else "no_results") if r["ok"] else \
                ("blocked" if any(c in str(r.get("error")) for c in ("403", "429")) else "unavailable")
            top = ", ".join(i["url"] for i in its[:3] if i.get("url"))
            _attempt(case, "social_search", status, f"{len(its)} item(s) via open API, relevance not yet judged"
                     + (f"; first: {top}" if top else "") + ("" if r["ok"] else f"; {r.get('error')}"),
                     engine=s, query=a.query, save=False)
    print()
    for n, it in enumerate(items, 1):
        print(f"[{n}] {it['source']} {it['date'][:10]} img:{len(it['thumbs'])}  {short(it['text'], 160)}\n      {it['url']}")
    sheet_id = list_id = None
    if case and a.sheet and items:
        from PIL import Image
        sdir = case.work / "social"
        sdir.mkdir(parents=True, exist_ok=True)
        imgs, shown = [], []
        for n, it in enumerate(items, 1):
            if len(imgs) >= a.sheet:
                break
            if not it["thumbs"]:
                continue
            dest = sdir / f"{n:03d}.img"
            if http.download(it["thumbs"][0], dest):
                try:
                    imgs.append((f"{n}. {it['source']} {it['date'][:10]}", Image.open(dest).convert("RGB")))
                    shown.append({"n": n, **it})
                except Exception:  # noqa: BLE001 - not an image (HTML error page etc.)
                    pass
        if imgs:
            sheet_id, sp = case.reserve_file("social-sheet", "jpg", f"contact sheet of {len(imgs)} social/community "
                                             f"images for '{a.query}'")
            imaging.contact_sheet(imgs).save(sp, quality=85)
            list_id = _save_json(case, "social", f"social search items behind {sheet_id} ('{a.query}')",
                                 {"query": a.query, "items": shown})
            print(f"\nsheet {sheet_id} {sp}  (item list {list_id})")
    if case and a.save and not list_id:
        list_id = _save_json(case, "social", f"social search results for '{a.query}'", {"query": a.query, "items": items})
        print(f"saved {list_id}")
    if case:
        case.save()
    print("\nOpen promising posts, read the caption, location tag and comments, and compare their photos with "
          "`igl.py compare`. A caption or tag is `reported` (source web), never a match by itself.")
    return 0


# ----------------------------------------------------------------------------- ledger
def cmd_note(a) -> int:
    case = Case(Path(a.case))
    if a.kind not in KINDS:
        raise IglError(f"--kind must be one of: {', '.join(KINDS)}")
    if a.status not in STATUS_CAP:
        raise IglError("--status must be one of: " + ", ".join(f"{k} ({v})" for k, v in STATUS_CAP.items()))
    if a.source not in SOURCES:
        raise IglError(f"--source must be one of: {', '.join(SOURCES)}")
    if (a.for_ or a.against) and not a.why:
        raise IglError("--for / --against need --why (one line: why this observation favours or disfavours them)")
    for spec in (a.for_ or []) + (a.against or []):          # fail before writing anything
        case.cand(spec.partition(":")[0])
    files = case.resolve_files(a.file, label=a.kind, what=f"evidence for: {short(a.text, 80)}")
    if a.status == "read" and not files:
        raise IglError("status 'read' needs --file (the zoomed crop that shows the text)")
    features = [f.strip() for f in (getattr(a, "features", None) or "").split(";") if f.strip()]
    if a.status == "matched":
        _require_match_basis(case, files, features, a.url)
    copy_on_file = _require_trace_basis(case, files, a.url) if a.status == "traced" else True
    resolves = [case.clue(r)["id"] for r in (a.resolves or [])]
    cid = _new_clue(case, redact(a.text), a.kind, a.status, a.source, files, parse_box(a.box) if a.box else None,
                    a.url, resolves)
    if features:
        case.data["clues"][cid]["features"] = [redact(f) for f in features]
    for r in resolves:
        case.data["clues"][r]["resolved"] = cid
    msgs = _link(case, case.data["clues"][cid], a.for_, a.against, a.why, []) if (a.for_ or a.against) else []
    case.save()
    cap = _lr_cap(case.data["clues"][cid])
    print(f"{cid}  [{a.status}, grade {GRADE[a.status]}, LR cap {cap:g}]  {short(a.text, 100)}")
    if a.source == "engine" and cap < STATUS_CAP[a.status]:
        print("    source 'engine': a label or similar-image title is a lead (cap 3) until the place is verified another "
              "way; a verified comparison is recorded as --status matched --source reference")
    if not copy_on_file:
        print("    no COPY on file for this trace: let the tool confirm it is the same photograph "
              f"(`igl.py refs {case.root} --image <address of the picture on that page>`) and cite the sheet with --file")
    for m in msgs:
        print(f"    {m}")
    return 0


MATCH_TOOLS = ("compare", "refs", "revsearch")


def _require_match_basis(case: Case, files: list[str], features: list[str], url: str | None) -> None:
    """`matched` is the strongest status, so it must be auditable: the features are named, the comparison
    is on file (or the reference page is given), and it is not the photo compared with a copy of itself."""
    if len(features) < 3:
        raise IglError("status 'matched' needs --features with at least 3 SPECIFIC invariant features that agree, "
                       "separated by ';' (e.g. \"arched window pair with transoms; coffered ceiling 3x4 panels; green "
                       "marble fireplace left of the bed\"). Same style, same chain furniture or 'looks alike' are not "
                       "features: if you cannot name three, record the comparison as --status observed.")
    tooled = [f for f in files if case.data["files"][f].get("tool") in MATCH_TOOLS]
    if not tooled and not url:
        raise IglError("status 'matched' needs the comparison behind it: --file <sheet or JSON written by compare / "
                       "refs / revsearch>, or --url <page of the reference photo> when you compared it in a browser "
                       "tool and could not save it")
    for f in tooled:
        classes = (case.data["files"][f].get("meta") or {}).get("classes")
        if classes and all(c == "copy" for c in classes):
            raise IglError(f"{f} compares the photo with copies of itself (COPY / SAME PHOTOGRAPH). A copy is "
                           "provenance: record what its page says with --status traced --source web --url <page>, and "
                           "verify the place against an independent photo (another photographer, another date).")


def _require_trace_basis(case: Case, files: list[str], url: str | None) -> bool:
    """`traced` says: this very photograph is published on a page that tells where it was taken. It needs
    that page, and when a tool artefact is cited it must hold a COPY of the photo (a similar picture is not a
    trace). Returns whether a COPY is on file."""
    if not (url or "").startswith(("http://", "https://")):
        raise IglError("status 'traced' needs --url: the page that shows the same photograph and says where it was "
                       "taken (the venue's own page or listing, the photographer's post). What a page says about a "
                       "merely similar picture is --status reported.")
    tooled = [f for f in files if case.data["files"][f].get("tool") in MATCH_TOOLS]
    with_copy = [f for f in tooled if "copy" in ((case.data["files"][f].get("meta") or {}).get("classes") or [])]
    if tooled and not with_copy:
        raise IglError(f"{', '.join(tooled)} holds no COPY of the photo. `traced` is for the SAME photograph found "
                       "online; a similar picture is a lead (--status reported), and after a comparison that finds "
                       ">=3 specific fixed features it becomes --status matched.")
    return bool(with_copy)


def cmd_cand(a) -> int:
    case = Case(Path(a.case))
    existing = a.name.upper() if a.name.upper() in case.data["candidates"] else None
    if existing:
        c = case.data["candidates"][existing]
        for k in ("lat", "lon", "address", "osm", "url", "wikidata", "falsify", "note"):
            v = getattr(a, k, None)
            if v is not None:
                c[k] = v
        if a.at:
            c["lat"], c["lon"] = parse_latlon(a.at)
        if a.parent:
            par = case.cand(a.parent)
            if LEVELS.index(par["level"]) >= LEVELS.index(c["level"]):
                raise IglError(f"parent {par['id']} is a {par['level']}: it must be coarser than {c['level']}")
            c["parent"] = par["id"]
        if a.file:
            c["files"] = sorted(set(c.get("files", []) + case.resolve_files(a.file)))
        case.event("cand", f"{existing} updated ({c['name']})")
        print(f"{existing} updated: {c['name']} [{c['level']}]")
        return 0
    if not a.level:
        raise IglError(f"--level is required for a new candidate ({', '.join(LEVELS)})")
    if a.level not in LEVELS:
        raise IglError("--level must be one of: " + ", ".join(f"{k} ({v})" for k, v in LEVEL_HELP.items()))
    lat, lon = parse_latlon(a.at) if a.at else (a.lat, a.lon)
    if a.parent:
        par = case.cand(a.parent)
        if LEVELS.index(par["level"]) >= LEVELS.index(a.level):
            raise IglError(f"parent {par['id']} ({par['name']}) is a {par['level']}: a parent must be coarser than "
                           f"a {a.level}")
    iso = None
    if a.level == "country":
        try:
            iso = knowledge.country(a.name)[0]
        except IglError:
            iso = None
        dup = [c for c in case.data["candidates"].values() if c["level"] == "country" and
               ((iso and c.get("iso") == iso) or c["name"].lower() == a.name.lower())]
        if dup:
            raise IglError(f"{dup[0]['id']} {dup[0]['name']} is already on the board (update it by id)")
    cid = case.next_id("C")
    case.data["candidates"][cid] = {"id": cid, "name": a.name, "level": a.level,
                                    "parent": case.cand(a.parent)["id"] if a.parent else None,
                                    "lat": lat, "lon": lon, "address": a.address, "osm": a.osm, "url": a.url,
                                    "wikidata": a.wikidata, "falsify": a.falsify, "note": a.note, "status": "open",
                                    "files": case.resolve_files(a.file) if a.file else [],
                                    "time": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    if iso:
        case.data["candidates"][cid]["iso"] = iso
    elif a.level == "country":
        print(f"note: {a.name!r} is not a country name in data/countries.json; use the official or common name "
              "(e.g. 'Germany', 'South Korea') so tables and the 'other countries' block stay consistent")
    case.event("cand", f"{cid} {a.level}: {a.name}" + (f" @ {lat:.5f},{lon:.5f}" if lat is not None else ""))
    print(f"{cid}  {a.level}: {a.name}" + (f"  parent {case.data['candidates'][cid]['parent']}" if a.parent else ""))
    if a.level != "country" and not a.parent:
        print(f"      no parent: attach it to its {'country' if a.level == 'region' else 'city or country'} "
              f"(`igl.py cand {case.root} {cid} --parent C#`) so the ranking knows where it is")
    return 0


def _put_evidence(case: Case, clue_id: str, cand_id: str, lr: float, requested: float, why: str, files: list[str]) -> str:
    for e in case.data["evidence"]:
        if e["clue"] == clue_id and e["candidate"] == cand_id:
            e.update({"lr": lr, "requested": requested, "why": why, "files": files or e.get("files", [])})
            return e["id"]
    vid = case.next_id("V")
    case.data["evidence"].append({"id": vid, "clue": clue_id, "candidate": cand_id, "lr": lr, "requested": requested,
                                  "why": why, "files": files,
                                  "time": dt.datetime.now().astimezone().isoformat(timespec="seconds")})
    return vid


def _lr_cap(clue: dict) -> float:
    """Largest likelihood ratio a clue may carry: by how it was obtained, and lower for machine guesses."""
    cap = STATUS_CAP[clue["status"]]
    if clue["status"] in ("inferred", "observed", "reported", "traced"):
        cap = min(cap, SOURCE_CAP.get(clue.get("source"), cap))
    return cap


def _link(case: Case, clue: dict, for_specs: list[str] | None, against_specs: list[str] | None, why: str,
          files: list[str]) -> list[str]:
    """Link one clue to candidates (C#:LR). The clue's status (and source) caps the LR in both directions."""
    cap = _lr_cap(clue)
    msgs = []
    for spec, sign in [(s, 1) for s in (for_specs or [])] + [(s, -1) for s in (against_specs or [])]:
        cid_s, _, lr_s = spec.partition(":")
        cand = case.cand(cid_s)
        try:
            req = float(lr_s) if lr_s else (2.0 if sign > 0 else 0.5)
        except ValueError as e:
            raise IglError(f"bad LR in {spec!r}: use C#:LR, e.g. C3:6") from e
        if req <= 0:
            raise IglError(f"LR must be positive (got {spec!r})")
        if sign > 0:
            if req < 1:
                raise IglError(f"--for LR must be >= 1 (got {req}); use --against for evidence against")
            lr = min(req, cap)
        else:
            if req > 1:
                req = 1 / req
            lr = max(req, 1 / cap)
        if case.is_excluded(cand["id"]):
            msgs.append(f"note: {cand['id']} is excluded")
        _put_evidence(case, clue["id"], cand["id"], lr, req, why or "", files)
        msgs.append(f"{clue['id']} -> {cand['id']} {cand['name']}: LR {lr:g}" +
                    (f" (capped from {req:g}: status '{clue['status']}'"
                     + (f", source '{clue['source']}'" if cap < STATUS_CAP[clue["status"]] else "")
                     + f" max {cap:g})" if abs(lr - req) > 1e-9 else ""))
    if msgs:
        case.event("link", f"{clue['id']} linked: " + "; ".join(m for m in msgs if not m.startswith("note")))
    return msgs


def cmd_link(a) -> int:
    case = Case(Path(a.case))
    clue = case.clue(a.clue)
    if not (a.for_ or a.against):
        raise IglError("give --for C#:LR and/or --against C#:LR")
    files = case.resolve_files(a.file) if a.file else []
    print("\n".join(_link(case, clue, a.for_, a.against, a.why, files)))
    return 0


def cmd_exclude(a) -> int:
    case = Case(Path(a.case))
    cand = case.cand(a.candidate)
    clue = case.clue(a.by)
    if clue["status"] not in EXCLUDERS:
        raise IglError(f"{clue['id']} is '{clue['status']}': only read / computed / matched clues may exclude; "
                       "weaker evidence can only down-weight (`igl.py link --against`)")
    files = case.resolve_files(a.file) if a.file else []
    if not (files or clue.get("files")):
        raise IglError("an exclusion needs a file showing the decisive evidence (--file E##)")
    cand["status"] = "excluded"
    cand["excluded_by"] = clue["id"]
    case.data["exclusions"].append({"candidate": cand["id"], "clue": clue["id"], "why": a.why, "files": files or clue["files"],
                                    "time": dt.datetime.now().astimezone().isoformat(timespec="seconds")})
    case.event("exclude", f"{cand['id']} {cand['name']} excluded by {clue['id']}: {a.why}")
    kids = case.descendants(cand["id"])
    print(f"{cand['id']} {cand['name']} excluded" + (f" (with {len(kids)} descendant candidate(s))" if kids else ""))
    return 0


def cmd_log(a) -> int:
    case = Case(Path(a.case))
    methods = [m.strip() for m in a.method.split(",") if m.strip()]
    for m in methods:
        if m not in CORE_METHODS and m not in OPTIONAL_METHODS:
            raise IglError(f"method must be one of: {', '.join(list(CORE_METHODS) + list(OPTIONAL_METHODS))} (got {m!r})")
    if not methods:
        raise IglError("give a method (or a comma list of methods)")
    if a.status not in ATTEMPT_STATUS:
        raise IglError(f"--status must be one of: {', '.join(ATTEMPT_STATUS)}")
    if a.status in ("not_applicable", "skipped", "blocked", "unavailable") and not a.detail:
        raise IglError(f"status '{a.status}' needs --detail saying why")
    files = case.resolve_files(a.file) if a.file else []
    for m in methods:
        aid = _attempt(case, m, a.status, a.detail or "", engine=a.engine, query=a.query, url=a.url, files=files,
                       save=False)
        print(f"{aid}  {m}: {a.status}")
    case.save()
    return 0


def cmd_rank(a) -> int:
    case = Case(Path(a.case))
    allb = scoring.board(case)
    levels = [a.level] if a.level else [lv for lv in LEVELS if lv in allb]
    if not levels:
        print("no candidates yet: add them with `igl.py cand`, `igl.py countries --case --clue`, or `igl.py geo ... --add`")
    clues = case.data["clues"]

    def ev_text(e: dict) -> str:
        star = "*" if e["lr"] >= 10 and clues.get(e["clue"], {}).get("status") in DECISIVE else ""
        return f"{e['clue']}x{e['lr']:g}{star}" + (f"(via {e['via']})" if e.get("via") else "")

    starred = False
    tiers = scoring.assess_all(case)
    for lv in levels:
        rows = allb.get(lv, [])
        starred = starred or any(r.get("identified") for r in rows[:a.limit])
        print(f"\n[{lv}]  share = probability of the whole chain; within = among siblings under the same parent")
        print(table([[r["id"], short(r["name"], 40), f"{r['share']:.3f}",
                      "" if r.get("rest") or lv == "country" else f"{r['cond']:.2f}", len(r["ev"]),
                      "EXCLUDED" if r["excluded"] else ("-" if r.get("rest") else tiers[r["id"]]["tier"]),
                      short("; ".join(ev_text(e) for e in sorted(r["ev"], key=lambda e: -abs(math.log(e['lr'])))[:6]), 70)]
                     for r in rows[:a.limit]], ["id", "candidate", "share", "within", "n_ev", "cap", "strongest evidence"]))
    if starred:
        print("\n* decisive clue (read / computed / matched / metadata / traced, LR >= 10): it identifies the place, so "
              "its candidate is weighed against the whole field at that level, listed rivals and unlisted block together")
    return 0


def checks(case: Case) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    d = case.data
    state = case.method_state()
    for m, desc in CORE_METHODS.items():
        st = state.get(m)
        if not st:
            out.append(("FAIL", f"core method '{m}' not attempted ({desc}) - do it, or log not_applicable with a reason"))
        elif st["status"] not in RESOLVED:
            out.append(("WARN", f"core method '{m}' only {st['status']}: try an alternative route if one exists"))
    hyps = [c for c in d["clues"].values() if c["kind"] == "hypothesis"]
    if not hyps:
        out.append(("WARN", "no first-look hypotheses recorded (anchor defence): note the top 2-4 hypotheses with "
                            "--kind hypothesis before reading tool output"))
    attempts = d["attempts"]
    rev = [a for a in attempts if a["method"] == "reverse_search"]
    engines = {(a.get("engine") or "").lower() for a in rev if a["status"] in ("results", "no_results") and a.get("engine")}
    rs = state.get("reverse_search", {}).get("status")
    if rs in ("results", "no_results") and len(engines) < 2:
        out.append(("WARN", f"reverse search ran on {len(engines)} engine(s) ({', '.join(sorted(engines)) or 'unnamed'}): "
                            "indexes differ - use at least two (Lens via a browser tool and `share`, Yandex, Bing, "
                            "TinEye, Baidu) on the full frame and on crops"))
    closed = [a for a in rev if a["status"] in ("blocked", "unavailable")]
    if closed and not engines:
        out.append(("WARN", f"reverse image search never actually ran ({len(closed)} attempt(s), all blocked or "
                            "unavailable): that is not 'no results'. Open the Lens / Bing links from `share` in a "
                            "browser tool or ask the user to run Google Lens, and say in the answer that this route "
                            "stayed closed"))
    if rs in ("results", "no_results") and "lens" not in engines and "google" not in engines:
        out.append(("WARN", "Google Lens was not used: it has the largest index of interiors and listings. With any "
                            "browser tool, open the lens link from `igl.py share`; without one, say so under limits"))
    for cid, c in d["clues"].items():
        if c["status"] != "matched":
            continue
        if len(c.get("features") or []) < 3:
            out.append(("WARN", f"{cid} is `matched` without three named features (--features): a match must say "
                                "which specific fixed features agree"))
        areas = [e["candidate"] for e in d["evidence"] if e["clue"] == cid and e["lr"] > 1
                 and d["candidates"].get(e["candidate"], {}).get("level") not in ("site", "room")]
        if areas and len(case.sites_examined()) < 2:
            out.append(("WARN", f"{cid} records a match for an area or group ({', '.join(areas)}), not for one venue: "
                                "that is a design match, and it needs the reference photos of at least two venues "
                                "that share the design on file (`refs ... --for <each C#>`)"))
    ts = [a for a in attempts if a["method"] == "text_search" and a["status"] in ("results", "no_results")]
    if state.get("text_search", {}).get("status") in ("results", "no_results") and len(ts) < 2:
        out.append(("WARN", "only one text search logged: search distinctive strings and descriptions in the local "
                            "language(s) too, and log each query"))
    for x in d["exclusions"]:
        if not x.get("files"):
            out.append(("FAIL", f"exclusion of {x['candidate']} has no evidence file"))
    for cid, c in d["clues"].items():
        for f in c.get("files", []):
            if f not in d["files"] or not (case.root / d["files"][f]["path"]).exists():
                out.append(("FAIL", f"{cid} cites missing file {f}"))
    orphans = [c["id"] for c in d["candidates"].values() if c["level"] != "country" and not c.get("parent")
               and not case.is_excluded(c["id"])]
    if orphans:
        out.append(("WARN", f"candidates without a parent: {', '.join(orphans[:15])} - attach each site to its city and "
                            "each city to its country (`cand <case> C# --parent C#`), or its share ignores the "
                            "uncertainty above it"))
    linked = {e["clue"] for e in d["evidence"]} | {x["clue"] for x in d["exclusions"]}
    unused = [cid for cid, c in d["clues"].items() if cid not in linked and c["kind"] not in
              ("hypothesis", "context", "scene", "negative") and not c.get("resolved")]
    if unused:
        out.append(("WARN", f"clues not linked to any candidate: {', '.join(unused[:20])} (link them, or mark kind context)"))
    open_contra = [cid for cid, c in d["clues"].items() if c["kind"] == "contradiction" and not c.get("resolved")]
    if open_contra:
        out.append(("WARN", f"unresolved contradictions: {', '.join(open_contra)} (explain them or lower the confidence)"))
    ans = d.get("answer")
    if not ans:
        out.append(("FAIL", "no answer recorded (`igl.py answer <case> <candidate>`)"))
    else:
        cid = ans["candidate"]
        cand = d["candidates"].get(cid)
        if not cand:
            out.append(("FAIL", f"answer points at unknown candidate {cid}"))
        else:
            rows = scoring.rank(case, cand["level"])
            if rows and rows[0]["id"] != cid:
                what = ("the unlisted alternatives outweigh it: the evidence does not favour it over places not on "
                        "the board" if rows[0].get("rest") else f"top: {rows[0]['id']} {rows[0]['name']}")
                out.append(("WARN", f"answer {cid} is not top-ranked at {cand['level']} level ({what}) - add "
                                    "discriminating evidence or change the answer"))
            if case.is_excluded(cid):
                out.append(("FAIL", f"answer {cid} is excluded"))
            chain_rows = scoring.chain(case, cid)
            a_now = chain_rows[-1]
            cap = a_now["tier"]
            if scoring.TIERS.index(ans.get("confidence", "low")) > scoring.TIERS.index(cap):
                out.append(("FAIL", f"claimed confidence {ans.get('confidence')} exceeds the rules cap {cap}"))
            if cap == "low" and any(scoring.TIERS.index(r["tier"]) >= 2 for r in chain_rows[:-1]):
                out.append(("FAIL", f"answer {cid} is LOW while a coarser level is verified: answer at that level and "
                                    "pass this candidate as --lead"))
            listed = [c for c in d["candidates"].values() if c["level"] == cand["level"] and not case.is_excluded(c["id"])]
            if cand["level"] != "country" and len(listed) == 1 and not a_now.get("decisive"):
                out.append(("WARN", f"only one {cand['level']} on the board and no decisive clue: list the category "
                                    "(other branches of the chain, same-name venues, neighbouring cities) before "
                                    "choosing"))
            if cand["level"] in ("site", "room"):
                if not cand.get("falsify"):
                    out.append(("WARN", "site-level answer without a falsification test "
                                        "(`igl.py cand <case> C# --falsify ...`)"))
                if state.get("reference_match", {}).get("status") != "results" and not a_now.get("matched"):
                    out.append(("WARN", "site-level answer without a reference comparison: collect independent "
                                        "photos of the site (`refs \"<venue> <city> <room type>\" --for C#`) and "
                                        "compare them"))
                site_c = d["candidates"][cid] if cand["level"] == "site" else next(
                    (x for x in case.ancestors(cid) if x["level"] == "site"), cand)
                rivals = case.rivals_compared(cid)
                if (a_now.get("matched") or site_c.get("refs")) and not rivals:
                    out.append(("WARN", "no rival was put through the same comparison (negative control): run `refs` "
                                        "for the closest alternative venue (same brand, same street, same style) with "
                                        "--for <its C#>. If its photos 'match' as well, the features you counted are "
                                        "generic and the site is not established"))
                twins = [r for r in rivals if not case.is_excluded(r["id"])
                         and any((run.get("counts") or {}).get("same") for run in r.get("refs") or [])]
                if a_now.get("matched") and twins:
                    out.append(("WARN", "reference photos of " + ", ".join(f"{r['id']} {r['name']}" for r in twins[:4])
                                        + " were classed SAME SCENE too. Either these candidates are one place (keep "
                                        "one, exclude the duplicate) or the agreement is on a shared design: then record "
                                        "the match for the area or group that holds every venue with this design and "
                                        "keep the venues as leads"))
            lead = ans.get("lead")
            if lead and lead["candidate"] in d["candidates"] and case.is_excluded(lead["candidate"]):
                out.append(("FAIL", f"lead {lead['candidate']} has been excluded since the answer was recorded"))
            if ans.get("lat") is None:
                out.append(("WARN", "answer has no coordinates"))
            for anc in case.ancestors(cid):
                rows = scoring.rank(case, anc["level"])
                if rows and rows[0]["id"] != anc["id"]:
                    out.append(("WARN", f"answer's {anc['level']} ({anc['name']}) is not top-ranked at its level"))
    if not out:
        out.append(("PASS", "all checks passed"))
    return out


def cmd_check(a) -> int:
    case = Case(Path(a.case))
    res = checks(case)
    for lvl, msg in res:
        print(f"{lvl:4}  {msg}")
    state = case.method_state()
    done = sum(1 for m in CORE_METHODS if state.get(m, {}).get("status") in RESOLVED)
    print(f"\ncore method coverage: {done}/{len(CORE_METHODS)}")
    return 1 if any(l == "FAIL" for l, _ in res) else 0


def _coords_for(case: Case, cand: dict, no_network: bool, notes: list[str]) -> tuple:
    """(lat, lon, address, auto_radius) of a candidate: its own coordinates, else geocoded from its name and
    ancestors (coarse levels get a radius from the area's bounding box); a site without an address is
    reverse-geocoded."""
    lat, lon, address, auto_radius = cand.get("lat"), cand.get("lon"), cand.get("address"), None
    if lat is None and not no_network:
        q = ", ".join([cand["name"]] + [x["name"] for x in case.ancestors(cand["id"])])
        g = geo.geocode(_http(case, "Nominatim/Photon"), q, limit=1)
        if g.get("ok") and g["results"]:
            top = g["results"][0]
            lat, lon = top["lat"], top["lon"]
            address = address or top["display"]
            notes.append(f"coordinates of {cand['id']} from geocoding '{q}' ({g['service']}): {top['display']}")
            bb = top.get("bbox")
            if bb and cand["level"] in ("district", "city", "region", "country"):
                auto_radius = int(round(haversine_m(bb[0], bb[2], bb[1], bb[3]) / 2))
        else:
            notes.append(f"could not geocode '{q}': give --at lat,lon (and --radius)")
    if lat is not None and not address and not no_network and cand["level"] in ("site", "room"):
        r = geo.reverse(_http(case, "Nominatim/Photon"), lat, lon)
        if r.get("ok"):
            address = r.get("display")
    return lat, lon, address, auto_radius


def cmd_answer(a) -> int:
    case = Case(Path(a.case))
    cand = case.cand(a.candidate)
    if case.is_excluded(cand["id"]):
        raise IglError(f"{cand['id']} {cand['name']} is excluded: it cannot be the answer")
    rows = scoring.chain(case, cand["id"])
    here = rows[-1]
    cap = here["tier"]
    verified = [r for r in rows[:-1] if scoring.TIERS.index(r["tier"]) >= scoring.TIERS.index("medium")]
    if cap == "low" and verified:
        best = verified[-1]
        raise IglError(
            f"{cand['id']} {cand['name']} ({cand['level']}) is only LOW: it is a lead, not an answer.\n"
            f"  {'; '.join(here['reasons'])}\n"
            f"Answer at the finest level the evidence supports and keep this candidate as the lead:\n"
            f"  igl.py answer {case.root} {best['id']} --lead {cand['id']} --summary \"...\"   "
            f"({best['name']}, {best['level']}, {best['tier'].upper()})\n"
            f"or verify it first (reference photos + `compare`, decisive text, a second lineage).")
    want = a.confidence or cap
    if scoring.TIERS.index(want) > scoring.TIERS.index(cap):
        raise IglError(f"confidence '{want}' exceeds what the evidence supports (cap '{cap}'):\n  " +
                       "\n  ".join(here["reasons"]) + "\nAdd independent evidence (reference match, decisive text, "
                       "metadata) or report a lower confidence.")
    lead = None
    if a.lead:
        lc = case.cand(a.lead)
        if lc["id"] == cand["id"]:
            raise IglError("--lead must be a different candidate from the answer")
        if case.is_excluded(lc["id"]):
            raise IglError(f"lead {lc['id']} is excluded")
        if LEVELS.index(lc["level"]) <= LEVELS.index(cand["level"]):
            raise IglError(f"--lead must be finer than the answer's {cand['level']} level (got a {lc['level']})")
    notes: list[str] = []
    lat, lon, address, auto_radius = _coords_for(case, cand, a.no_network, notes)
    if a.at:
        lat, lon = parse_latlon(a.at)
    address = a.address or address
    if a.lead:
        la = scoring.assess(case, lc["id"])
        llat, llon, laddr, _ = _coords_for(case, lc, a.no_network, notes)
        lead = {"candidate": lc["id"], "name": lc["name"], "level": lc["level"], "lat": llat, "lon": llon,
                "address": laddr, "radius_m": report.DEFAULT_RADIUS.get(lc["level"], 100), "tier": la["tier"],
                "share": round(la["share"], 3), "reasons": la["reasons"], "falsify": lc.get("falsify") or "",
                "descendant": any(x["id"] == cand["id"] for x in case.ancestors(lc["id"]))}
        if not lead["descendant"]:
            notes.append(f"lead {lc['id']} does not lie under {cand['id']} on the board: check the hierarchy")
    radius = a.radius or auto_radius or report.DEFAULT_RADIUS.get(cand["level"], 100)
    # The pin: the single most likely point. A lead that has coordinates is a better point estimate than the
    # centroid of the area it lies in; what is VERIFIED stays the answer level with its radius.
    if lead and lead.get("lat") is not None:
        pin = {"basis": "lead", "candidate": lead["candidate"], "name": lead["name"], "address": lead.get("address"),
               "lat": lead["lat"], "lon": lead["lon"], "level": lead["level"], "tier": lead["tier"]}
    else:
        pin = {"basis": "answer", "candidate": cand["id"], "name": a.name or cand["name"], "address": address,
               "lat": lat, "lon": lon, "level": cand["level"], "tier": want}
    case.data["answer"] = {"candidate": cand["id"], "name": a.name or cand["name"], "address": address, "lat": lat,
                           "lon": lon, "radius_m": radius, "level": cand["level"], "confidence": want, "cap": cap,
                           "share": round(here["share"], 3), "summary": a.summary or "",
                           "open_questions": a.open_questions or "", "lead": lead, "best_estimate": pin,
                           "files": case.resolve_files(a.file) if a.file else [],
                           "time": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    case.event("answer", f"answer {cand['id']} {cand['name']} ({cand['level']}, confidence {want}, cap {cap})"
               + (f"; lead {lead['candidate']} {lead['name']} ({lead['tier']})" if lead else ""))
    print(f"ANSWER  {a.name or cand['name']}" + (f" — {address}" if address else ""))
    print("        " + (f"{lat}, {lon} ± {radius} m" if lat is not None else "no coordinates (give --at lat,lon)")
          + f" · level {cand['level']} · confidence {want} (cap {cap})")
    print("        " + "; ".join(here["reasons"]))
    if lead:
        print(f"LEAD    {lead['name']} ({lead['level']}, {lead['tier'].upper()}, share {lead['share']:.2f}) - "
              + (f"{lead['lat']}, {lead['lon']}" if lead["lat"] is not None else "no coordinates on file")
              + ": report it as the best unverified lead, never as the verified answer")
    if pin["lat"] is not None:
        print(f"PIN     {pin['lat']}, {pin['lon']}  = {pin['name']} "
              + ("(the unverified lead: the single most likely point; the verified statement is the ANSWER line)"
                 if pin["basis"] == "lead" else "(the answer itself)"))
    if cap == "low":
        print("        LOW everywhere: present this as a best guess, say what is missing, and keep searching if any "
              "route is still open")
    finer = [c for c in case.descendants(cand["id"]) if not case.is_excluded(c["id"])]
    if finer and not lead:
        done = scoring.assess_all(case)
        top = max(finer, key=lambda c: done[c["id"]]["share"])
        print(f"        note: finer candidates exist under {cand['id']} (e.g. {top['id']} {top['name']}): pass the best "
              "one as --lead so the report shows it")
    for n in notes:
        print(f"        note: {n}")
    if auto_radius and not a.radius:
        print("        radius = half the diagonal of the area's bounding box; give --radius if you know better")
    return 0


def cmd_report(a) -> int:
    case = Case(Path(a.case))
    md, js = report.write(case)
    case.event("report", "report written")
    print(f"{md}\n{js}")
    return 0


def cmd_finalize(a) -> int:
    case = Case(Path(a.case))
    res = checks(case)
    fails = [m for l, m in res if l == "FAIL"]
    for lvl, msg in res:
        print(f"{lvl:4}  {msg}")
    if fails and not a.force:
        print("\nnot finalized: fix the FAIL items (or --force to finalize with open issues, which the report will list)")
        return 1
    if fails:
        case.data.setdefault("answer", None)
        if case.data.get("answer") is not None:
            case.data["answer"]["open_questions"] = (case.data["answer"].get("open_questions", "") +
                                                     " Finalized with open issues: " + "; ".join(fails)).strip()
    work = case.root / ".work"
    if work.exists() and not a.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    removed = []
    if not a.keep_all:
        refs = case.referenced_files()
        for eid, f in list(case.data["files"].items()):
            if eid not in refs:
                p = case.root / f["path"]
                if p.exists():
                    p.unlink()
                removed.append(eid)
                del case.data["files"][eid]
        known = {(case.root / f["path"]).resolve() for f in case.data["files"].values()}
        for p in sorted(case.evidence_dir.iterdir()):     # orphans left by an interrupted command
            if p.is_file() and p.resolve() not in known:
                p.unlink()
                removed.append(p.name)
    case.event("finalize", f"finalized; pruned {len(removed)} unreferenced file(s)")
    report.write(case)
    print(f"\nfinalized {case.root}" + (f" (pruned unreferenced: {', '.join(removed)})" if removed else ""))
    for p in sorted(case.root.rglob("*")):
        if p.is_file():
            print(f"  {p.relative_to(case.root)}  ({p.stat().st_size // 1024} KB)")
    return 0


def cmd_status(a) -> int:
    case = Case(Path(a.case))
    d = case.data
    print(f"CASE {case.root}\nimage {d['image']['file']} {d['image'].get('size')}  updated {d['updated']}")
    print(f"clues {len(d['clues'])} · candidates {len(d['candidates'])} · links {len(d['evidence'])} · "
          f"exclusions {len(d['exclusions'])} · attempts {len(d['attempts'])} · files {len(d['files'])}")
    state = case.method_state()
    print("\nmethods: " + "  ".join(f"{m}={state.get(m, {}).get('status', 'PENDING')}" for m in CORE_METHODS))
    for lv in LEVELS:
        rows = scoring.rank(case, lv)
        if rows:
            top = rows[0]
            real = [r for r in rows if not r.get("rest")]
            print(f"{lv:8} top {top['id']} {short(top['name'], 50)} share {top['share']:.2f} "
                  f"({len([r for r in real if not r['excluded']])} open / {len(real)} on the board)")
    if d.get("answer"):
        x = d["answer"]
        print(f"\nanswer: {x['name']} ({x['level']}, {x['confidence']})")
    print("\nrecent: " + " | ".join(short(e["text"], 70) for e in d["timeline"][-5:]))
    return 0
