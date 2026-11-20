"""The image commands: `revsearch` (reverse image search, every hit compared with the photo), `refs`
(reference photos of a candidate or an area, ranked against the photo), `compare` (the photo against
chosen references, with inlier views), `share` (temporary public copy + by-URL links) and `snapshot`.

They share one idea: nothing an engine or a web page shows counts until the pixels have been compared.
The machine does the part it is reliable at (match.classify): COPY (the same photograph: provenance), SAME
SCENE (strong geometric agreement) and PARTIAL are trustworthy positives. Everything else is "unconfirmed":
feature matching misses real photos of the same room taken at another time or angle, so those are put on
a numbered contact sheet next to the photo for the agent to judge by eye: most similar first when the
similarity model is available (embed.py: it orders, it never confirms), else in the source's own order.
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from . import embed, imaging, match, refs, revsearch
from .case import Case
from .common import _attempt, _box_from, _http, _save_json
from .util import IglError, read_json, redact, short, write_json

KEEP = ("n", "kind", "title", "page", "image", "thumb", "site", "provider", "query", "from_page", "cls", "inliers",
        "h_inliers", "f_inliers", "matches", "spread", "sim", "mirrored", "query_box", "same_as", "refined", "size",
        "local", "verdict")


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _query_images(case: Case, a, img, rdir: Path, full_default: bool = True) -> list[tuple[str, Path]]:
    """The images a reverse search or share works on: --image evidence/files, a --cell/--box/--rel crop, the
    full frame (when nothing else is given, or with --full), and a mirrored copy of the first (--flip).
    Every copy is re-encoded without metadata (no EXIF GPS leaves the machine)."""
    from PIL import Image, ImageOps
    images: list[tuple[str, Path]] = []
    for ref in ([a.image] if isinstance(getattr(a, "image", None), str) else (getattr(a, "image", None) or [])):
        for eid in case.resolve_files([ref]):
            dst = rdir / f"{eid.lower()}.jpg"
            imaging.fit(imaging.flatten(Image.open(case.file_path(eid))), 1600).save(dst, quality=92)
            images.append((eid.lower(), dst))
    box = _box_from(a, img.size, case)
    if box:
        n = 1 + sum(1 for p in rdir.glob("crop*.jpg") if "-flip" not in p.name)
        label = "crop" if n == 1 else f"crop{n}"
        dst = rdir / f"{label}.jpg"
        imaging.fit(imaging.crop(img, box), 1600, min_side=500).save(dst, quality=92)
        images.append((label, dst))
    if not images or (full_default and getattr(a, "full", False)):
        dst = rdir / "full.jpg"
        imaging.fit(img, 1600).save(dst, quality=92)
        images.insert(0, ("full", dst))
    if getattr(a, "flip", False):
        src = images[0][1]
        dst = rdir / f"{images[0][0]}-flip.jpg"
        ImageOps.mirror(Image.open(src).convert("RGB")).save(dst, quality=92)
        images.append((f"{images[0][0]}-flip", dst))
    return images


def _query_view(case: Case, a, img):
    """The part of the photo that `compare` and `refs` test: an evidence crop (--query E##), a region
    (--cell / --box / --rel) or the whole frame. Returns (image, label)."""
    from PIL import Image
    if getattr(a, "query", None):
        eid = case.resolve_files([a.query])[0]
        return imaging.flatten(Image.open(case.file_path(eid))), f"query {eid}"
    box = _box_from(a, img.size, case)
    return (imaging.crop(img, box), "query (crop of the photo)") if box else (img, "query (the photo)")


def _rel(case: Case, path: str | None) -> str | None:
    if not path:
        return None
    try:
        return Path(path).resolve().relative_to(case.root).as_posix()
    except ValueError:
        return str(path)


def _slim(case: Case, it: dict) -> dict:
    out = {k: it[k] for k in KEEP if it.get(k) not in (None, "", [])}
    if out.get("local"):
        out["local"] = _rel(case, out["local"])
    return out


def _sharer(case: Case, paths: dict[str, Path], enabled: bool):
    """url_for(label): a temporary public copy of that query image, made on first request and recorded in
    the case (the report lists every copy). Returns None when sharing is off or no host accepts it."""
    from . import share
    made: dict[str, str | None] = {}

    def url_for(label: str) -> str | None:
        if not enabled:
            return None
        if label not in made:
            r = share.upload(_http(case, "temporary image host"), paths[label])
            made[label] = r.get("url") if r["ok"] else None
            if r["ok"]:
                case.data["auto"].setdefault("shared", []).append(
                    {"label": label, "ok": True, "host": r["host"], "url": r["url"], "expires": r["expires"],
                     "time": _now()})
                print(f"   (by-URL fallback: temporary copy of '{label}' on {r['host']}, deleted after {r['expires']})",
                      flush=True)
        return made[label]

    url_for.made = made
    return url_for


def _ranker_http(case: Case):
    """HTTP client for the pictures to compare. If the similarity model still has to be fetched, the case
    records that download too (the report lists every online service the tools used)."""
    if embed.state()["state"] == "download":
        _http(case, "huggingface.co (similarity model, one download)")
    return _http(case, "reference images")


def _hit_line(h: dict, width: int = 78) -> str:
    cls = match.LABEL.get(h.get("cls"), "-")
    inl = f"{h.get('inliers', 0):>4}" if h.get("cls") in ("same", "partial") else (
        f"{h['sim']:.2f}" if h.get("cls") == "none" and h.get("sim") is not None else "    ")
    where = h.get("page") or h.get("image") or ""
    return f"#{h['n']:<3} {cls:<10} {inl}  {short(h.get('title') or '(no title)', width)}  <{h.get('site', '')}>  {short(where, 110)}"


# ----------------------------------------------------------------------------- reverse image search
def cmd_revsearch(a) -> int:
    from PIL import Image
    case = Case(Path(a.case))
    img, _ = imaging.open_image(case.image_path)
    engines = list(revsearch.ENGINES) if a.engines == "all" else [e.strip().lower() for e in a.engines.split(",")
                                                                  if e.strip()]
    bad = [e for e in engines if e not in revsearch.ENGINES]
    if bad:
        raise IglError(f"unknown engine(s) {bad}; choose from {', '.join(revsearch.ENGINES)} or 'all'")
    rdir = case.work / "rev"
    rdir.mkdir(parents=True, exist_ok=True)
    run = f"{case.data['counters'].get('A', 0) + 1:03d}"
    images = _query_images(case, a, img, rdir)
    paths = dict(images)
    shots: dict[tuple, str] = {}

    def shot_for(engine, label):
        eid, path = case.reserve_file(f"rev-{engine}-{label}", "jpg", f"{engine} reverse-search result page for '{label}'",
                                      tool="revsearch")
        shots[(engine, label)] = eid
        return path

    url_for = _sharer(case, paths, enabled=not a.no_share)
    print(f"reverse search: {len(images)} image(s) x {', '.join(engines)} (headless browser) ...", flush=True)
    results = revsearch.search(images, engines, shot_for, url_for)
    if os.environ.get("SERPAPI_KEY"):                       # optional: Google Lens through the user's SerpApi key
        for label, _p in images:
            r = revsearch.lens_api(_http(case, "SerpApi (Google Lens)", retries=1), url_for(label))
            r.update({"engine": "lens", "image": label})
            r.setdefault("hits", [])
            r.setdefault("labels", [])
            results = [x for x in results if not (x["engine"] == "lens" and x["image"] == label)] + [r]
    for eid in list(shots.values()):                      # a screenshot that failed leaves no file: drop its entry
        if not case.file_path(eid).exists():
            del case.data["files"][eid]
    shots = {k: v for k, v in shots.items() if v in case.data["files"]}

    http = _ranker_http(case)
    sheets: dict[tuple, str] = {}
    counter = 0
    for r in results:
        hits = r.get("hits") or []
        if hits and a.triage:
            q = imaging.flatten(Image.open(paths[r["image"]]))
            for h in hits:
                h["prefer_full"] = h["kind"] in ("page", "copy")
            head, tail = hits[:a.triage], hits[a.triage:]
            print(f"   comparing {len(head)} {r['engine']} hit(s) for '{r['image']}' with the photo ...", flush=True)
            r["triage"] = refs.rank_against(q, head, rdir / f"tri-{run}-{r['engine']}-{r['image']}", http, refine=6,
                                            start=counter + 1)
            counter += len(head)
            for h in tail:
                counter += 1
                h["n"], h["cls"] = counter, "unchecked"
            r["hits"] = head + tail
            sh = refs.ranked_sheets(q, head, per_sheet=15, max_sheets=1)
            if sh:
                sid, sp = case.reserve_file(f"rev-{r['engine']}-{r['image']}-ranked", "jpg",
                                            f"{r['engine']} hits for '{r['image']}' in rank order (your photo first; "
                                            "green SAME SCENE, yellow PARTIAL, blue COPY, grey unconfirmed)", tool="revsearch")
                sh[0].save(sp, quality=85)
                sheets[(r["engine"], r["image"])] = sid
        else:
            for h in hits:
                counter += 1
                h["n"] = counter
                h.setdefault("cls", "unchecked")
    jid, jp = case.reserve_file("revsearch", "json", "reverse-search results: per engine and image, every hit with its "
                                                     "class against the photo", tool="revsearch")
    write_json(jp, [{**{k: v for k, v in r.items() if k != "hits"}, "hits": [_slim(case, h) for h in r.get("hits", [])]}
                    for r in results])
    seen: dict[tuple, list[str]] = {(r["engine"], r["image"]): sorted({h["cls"] for h in r.get("hits", []) if h.get("cls")})
                                    for r in results}
    for store in (shots, sheets):
        for key, eid in store.items():
            case.data["files"][eid]["meta"] = {"json": jid, "classes": seen.get(key, [])}
    case.data["files"][jid]["meta"] = {"json": jid, "classes": sorted({c for v in seen.values() for c in v})}

    totals = {"copy": 0, "same": 0, "partial": 0, "none": 0}
    for r in results:
        key = (r["engine"], r["image"])
        files = [x for x in (shots.get(key), sheets.get(key)) if x] + [jid]
        hits = r.get("hits", [])
        by = {c: [h for h in hits if h.get("cls") == c and not h.get("same_as")] for c in ("copy", "same", "partial", "none")}
        for c in totals:
            totals[c] += len(by[c])
        bits = [f"[{r['image']}]" + (f" via {r['route']}" if r.get("route") else "")]
        for c in ("copy", "same", "partial"):
            if by[c]:
                bits.append(f"{len(by[c])} {match.LABEL[c]} (" + "; ".join(
                    short(h.get("title") or h.get("site") or "", 46) + f" <{h.get('site', '')}> #{h['n']}" for h in by[c][:4]) + ")")
        if by["none"]:
            bits.append(f"{len(by['none'])} unconfirmed hit(s) (no automatic match: judged by eye on the ranked sheet)")
        if r.get("labels"):
            bits.append("engine labels (guesses): " + ", ".join(r["labels"][:6]))
        if "n_matches" in r:
            bits.append(f"n={r['n_matches']}")
        if r.get("note"):
            bits.append(r["note"])
        _attempt(case, "reverse_search", r["status"], redact(". ".join(bits)), engine=r["engine"], url=r.get("url"),
                 files=files, save=False)
    case.save()

    for r in results:
        key = (r["engine"], r["image"])
        route = f" via {r['route']}" if r.get("route") else ""
        print(f"\n== {r['engine']} [{r['image']}]: {r['status'].upper()}{route}  ({r.get('seconds', '?')} s)  {r.get('note', '')}")
        if r.get("labels"):
            print("   engine labels (machine guesses, never evidence): " + ", ".join(r["labels"][:10]))
        if "n_matches" in r:
            print(f"   copies found by the engine: {r['n_matches']}")
        hits = r.get("hits", [])
        if hits and r.get("triage"):
            print(f"   {len(hits)} hit(s); compared with your photo: {refs.summary_line(r['triage'])}")
            strong = [h for h in hits if h.get("cls") in ("copy", "same", "partial") and not h.get("same_as")]
            for h in strong[:a.top]:
                print("   " + _hit_line(h))
            weak = [h for h in hits if h.get("cls") == "none" and not h.get("same_as")]
            if weak:
                how = ("most similar first; `sim` orders, it does not confirm" if refs.by_similarity(weak)
                       else "in the engine's order")
                print(f"   unconfirmed ({len(weak)}, {how}): the feature test found nothing, which it "
                      "also does for real photos of the same room from another time or angle. OPEN THE RANKED SHEET "
                      "and compare each with your photo:")
                for h in weak[:a.top]:
                    print("   " + _hit_line(h))
        else:
            for h in hits[:a.top]:
                print(f"   #{h['n']:<3} {short(h.get('title', ''), 80)}  <{h.get('site', '')}>  "
                      f"{short(h.get('page') or h.get('image') or '', 100)}")
        if key in sheets:
            print(f"   ranked sheet: {sheets[key]}  {case.file_path(sheets[key])}")
        if key in shots:
            print(f"   screenshot:   {shots[key]}  {case.file_path(shots[key])}")
    print(f"\nresults: {jid}  {jp}")
    ran = [r for r in results if r["status"] in ("results", "no_results")]
    print(f"\nSUMMARY  {len(ran)}/{len(results)} searches ran. COPY {totals['copy']} · SAME SCENE {totals['same']} · "
          f"PARTIAL {totals['partial']} · unconfirmed {totals['none']}")
    if totals["copy"]:
        print("  COPY = the same photograph online: provenance, the strongest lead there is. Open those pages (your web "
              "fetch tool or `snapshot`) and read the caption, title, date and location tag. A page of the venue itself, "
              "its listing, or the photographer's own post that names the place is recorded as\n"
              f"    igl.py note {case.root} \"Same photograph on <page>: <what it says>\" --kind provenance --status traced "
              f"--source web --url <page> --file <sheet> --for C#:15 --why \"...\"\n"
              "  (aggregators, pins and reposts: --status reported, LR <= 6). Copies on pages that name DIFFERENT venues "
              "identify a brand or a stock picture, not a place. Then verify against an independent photo (`refs`).")
    if totals["same"] or totals["partial"]:
        print(f"  SAME SCENE / PARTIAL = another photo with matching structure: the strongest leads. See WHERE it matches:\n"
              f"    igl.py compare {case.root} --refs {jid} --pick <#,#>     (fixed architecture or unique art = site "
              "evidence; chain furniture = brand only)")
    if totals["none"]:
        print("  UNCONFIRMED = engines list look-alikes beside real matches and do not say which is which. Open each "
              "ranked sheet (your photo is tile 1) and judge by eye: the same place shows the same SPECIFIC FIXED things "
              "(the shape and count of windows, the ceiling, columns, built-ins, a floor pattern, a unique artwork or "
              "sculpture, the view), not merely the same style. Three or more such features on one hit -> `compare "
              f"--refs {jid} --pick <#>` and record a `matched` clue; none -> it is a look-alike: its title names "
              "another venue and must not be used. Titles of unconfirmed hits are leads for the region and type only.")
    if not (totals["copy"] or totals["same"] or totals["partial"] or totals["none"]) and ran:
        print("  Nothing came back. Go on: tight crops (art, carpet, ceiling, the view), Google Lens in a browser tool, "
              "text search, enumeration + `refs`.")
    if not ran:
        print("  No engine ran here (blocked or unavailable): this is NOT 'no results'. Use a browser tool with the "
              "by-URL links below, or ask the user to run Google Lens.")
    made = {k: v for k, v in url_for.made.items() if v}
    if made:
        print("\nBy-URL links for a browser tool (temporary copies made in this run):")
        for label, u in made.items():
            links = revsearch.by_url_links(u)
            print(f"  [{label}] lens {links['lens']}\n  {' ' * (len(label) + 2)} bing {links['bing']}")
    print("\n" + revsearch.MANUAL)
    return 0


# ----------------------------------------------------------------------------- reference imagery
def cmd_refs(a) -> int:
    case = Case(Path(a.case))
    img, _ = imaging.open_image(case.image_path)
    q, qlabel = _query_view(case, a, img)
    cand = case.cand(a.for_) if a.for_ else None
    queries = [t for t in (a.terms or []) if t.strip()]
    pages = list(a.url or [])
    direct = list(a.image or [])
    if not (queries or pages or direct):
        raise IglError('give at least one image-search text ("<venue> <city> <room type>"), --url <gallery page> or '
                       "--image <url|file|E##>")
    providers = [p.strip().lower() for p in a.providers.split(",") if p.strip()]
    bad = [p for p in providers if p not in refs.PROVIDERS]
    if bad:
        raise IglError(f"unknown provider(s) {bad}; choose from {', '.join(refs.PROVIDERS)}")
    wdir = case.work / "refs" / f"run{case.data['counters'].get('E', 0) + 1:03d}"
    for svc in (["image search: " + ", ".join(providers)] if queries else []) + (["reference pages"] if pages else []):
        _http(case, svc)
    print(f"collecting reference images: {len(queries)} search(es) x {', '.join(providers) if queries else '-'}, "
          f"{len(pages)} page(s), {len(direct)} given ...", flush=True)
    got = refs.collect(queries, pages, providers, per_query=a.per, per_page=a.per) if (queries or pages) else \
        {"runs": [], "items": []}
    items = got["items"]
    for ref in direct:
        if ref.startswith(("http://", "https://")):
            items.append({"title": "", "page": "", "image": ref, "thumb": "", "site": refs.site_of(ref),
                          "provider": "given", "prefer_full": True})
        else:
            eid = case.resolve_files([ref], label="reference", what="reference image given to `refs`")[0]
            items.append({"title": case.data["files"][eid]["what"], "page": "", "image": "", "thumb": "",
                          "file": str(case.file_path(eid)), "site": eid, "provider": "given"})
    for it in items:
        if it.get("provider") == "page":
            it["prefer_full"] = True
    found = len(refs.dedupe_urls(list(items)))
    items = refs.dedupe_urls(refs.interleave(items))[:a.max]      # every search and page contributes its best
    for r in got["runs"]:
        print(f"   {r.get('provider', '-'):<10} {r.get('status', '?'):<12} {r.get('n', 0):>3} image(s)  "
              f"{short(r.get('target', ''), 70)}  {r.get('note', '')}")
    counts: dict[str, int] = {}
    sheet_ids: list[str] = []
    if items:
        print(f"comparing {len(items)} reference image(s) with {qlabel} ...", flush=True)
        counts = refs.rank_against(q, items, wdir, _ranker_http(case), refine=8)
        for i, sh in enumerate(refs.ranked_sheets(q, items, per_sheet=15, max_sheets=a.sheets), 1):
            sid, sp = case.reserve_file(f"refs-{a.label or (cand['name'] if cand else 'refs')}-{i}", "jpg",
                                        f"reference images in rank order, sheet {i} (your photo first; green SAME SCENE, "
                                        f"yellow PARTIAL, blue COPY, grey no match): {'; '.join(queries + pages)[:200]}",
                                        tool="refs")
            sh.save(sp, quality=85)
            sheet_ids.append(sid)
    compared = sum(v for k, v in counts.items() if k not in ("missing",))
    out = {"query": qlabel, "for": cand["id"] if cand else None, "searches": queries, "pages": pages, "runs": got["runs"],
           "counts": counts, "items": [_slim(case, it) for it in items]}
    jid, jp = case.reserve_file(f"refs-{a.label or (cand['name'] if cand else 'refs')}", "json",
                                "reference images compared with the photo: sources, classes, inliers", tool="refs")
    write_json(jp, out)
    meta = {"json": jid, "classes": sorted({it["cls"] for it in items if it.get("cls") and not it.get("same_as")})}
    for fid in sheet_ids + [jid]:
        case.data["files"][fid]["meta"] = meta
    uniq = [it for it in items if it.get("local") and not it.get("same_as")]
    best = uniq[0] if uniq else None
    runs_ok = [r for r in got["runs"] if r.get("status") in ("results", "no_results")]
    if compared:
        status = "results"
    elif got["runs"] and not runs_ok:
        status = "blocked" if any(r.get("status") == "blocked" for r in got["runs"]) else "unavailable"
    else:
        status = "no_results" if not items else "unavailable"
    detail = (f"{'for ' + cand['id'] + ' ' + cand['name'] + ': ' if cand else ''}{compared} reference image(s) compared "
              f"({refs.summary_line(counts)})" + (f"; best #{best['n']} {match.LABEL.get(best['cls'])} "
                                                  f"{best.get('inliers', 0)} inliers <{best.get('site', '')}>" if best else "")
              + "; sources: " + "; ".join(f"{r.get('provider')} {r.get('status')}" for r in got["runs"]))
    _attempt(case, "reference_match", status, detail, engine="refs", query="; ".join(queries)[:200] or None,
             files=sheet_ids + [jid], save=False)
    if cand:
        cand.setdefault("refs", []).append({"json": jid, "sheets": sheet_ids, "compared": compared, "counts": counts,
                                            "best": ({"n": best["n"], "cls": best["cls"], "inliers": best.get("inliers", 0),
                                                      "site": best.get("site")} if best else None), "time": _now()})
    case.event("refs", f"refs {jid}: {detail}")

    print(f"\n{compared} compared ({refs.summary_line(counts)})" + (f" for {cand['id']} {cand['name']}" if cand else ""))
    for it in uniq[:a.top]:
        print("  " + _hit_line(it, 60))
    for i, sid in enumerate(sheet_ids, 1):
        print(f"sheet {i}: {sid}  {case.file_path(sid)}")
    print(f"list:    {jid}  {jp}")
    on_sheets = min(len(uniq), 15 * a.sheets)
    if len(uniq) > on_sheets or found > len(items):
        print(f"({on_sheets} of {len(uniq)} distinct pictures are on the sheets" +
              (f"; {found - len(items)} more were found but not compared" if found > len(items) else "") +
              ": --sheets N shows more, --max N compares more)")
    strong = [it for it in uniq if it["cls"] in ("same", "partial")]
    copies = [it for it in uniq if it["cls"] == "copy"]
    print()
    if copies:
        print(f"COPY (#{', #'.join(str(it['n']) for it in copies[:6])}): your photo itself is published there. That is "
              "provenance: open the page, read caption/date/location, and check that the page really is about this "
              f"venue. Record it with --status traced --source web --url <page> --file {sheet_ids[0] if sheet_ids else jid}. "
              "It is not an independent confirmation: a `matched` clue needs another photograph.")
    if strong:
        print(f"SAME SCENE / PARTIAL (#{', #'.join(str(it['n']) for it in strong[:8])}): see WHERE the structure agrees "
              f"before you count it:\n  igl.py compare {case.root} --refs {jid} --pick "
              f"{','.join(str(it['n']) for it in strong[:4])}" + (f" --for {cand['id']}" if cand else ""))
    if compared and len(uniq) > len(strong) + len(copies):
        order = ("They are sorted most similar first (`sim`: a visual likeness that orders the sheet and confirms "
                 "nothing; look-alikes score high too). " if refs.by_similarity(uniq) else
                 f"They are in the source's own order (no similarity ranking here: {embed.why_not()}). ")
        print(("No automatic match. " if not (strong or copies) else "The other references are unconfirmed. ") + order +
              "Unconfirmed is inconclusive either way: feature matching misses real photos of the same room from another "
              "time or angle. OPEN THE SHEET(S), your photo is tile 1: does a reference show the same SPECIFIC FIXED "
              "features (window shape and count, ceiling, columns, built-ins, floor pattern, the view, a unique "
              f"artwork)? If yes: `igl.py compare {case.root} --refs {jid} --pick <#>`" +
              (f" --for {cand['id']}" if cand else "") + " for a large side-by-side, then record `matched` with the "
              "features named. If only the style agrees, this candidate stays a lead: test the rivals the same way "
              "and keep searching.")
    if not compared:
        print("Nothing could be compared (see the source lines above). Unreachable is not empty: open the candidate's "
              "gallery, maps photos or listing in your browser tool, or pass image URLs you found with --image.")
    return 0


# ----------------------------------------------------------------------------- compare
def _picked(case: Case, ref_id: str, picks: str) -> list[tuple[str, str, str, str]]:
    """(label, source, fallback source, page) for numbered items of a `refs` or `revsearch` result file."""
    eid = case.resolve_files([ref_id])[0]
    rec = case.data["files"][eid]
    if rec.get("meta", {}).get("json"):
        eid = rec["meta"]["json"]
    data = read_json(case.file_path(eid))
    pool = data["items"] if isinstance(data, dict) else [h for r in data for h in r.get("hits", [])]
    by_n = {int(it["n"]): it for it in pool if "n" in it}
    out = []
    for tok in [t for t in picks.replace("#", "").split(",") if t.strip()]:
        try:
            n = int(tok)
        except ValueError as e:
            raise IglError(f"--pick takes item numbers like 3,7 (got {tok!r})") from e
        if n not in by_n:
            raise IglError(f"{eid} has no item #{n} (numbers run {min(by_n)}-{max(by_n)})" if by_n else f"{eid} lists no items")
        it = by_n[n]
        local = (case.root / it["local"]) if it.get("local") else None
        src = it.get("image") or (str(local) if local and local.exists() else "") or it.get("thumb") or ""
        fallback = str(local) if local and local.exists() else (it.get("thumb") or "")
        out.append((f"#{n} {it.get('site') or ''}".strip(), src, fallback, it.get("page") or ""))
    return out


def cmd_compare(a) -> int:
    from PIL import Image
    case = Case(Path(a.case))
    img, _ = imaging.open_image(case.image_path)
    q, qlabel = _query_view(case, a, img)
    cand = case.cand(a.for_) if getattr(a, "for_", None) else None
    todo: list[tuple[str, str, str, str]] = []            # (label, source, fallback source, page)
    for i, ref in enumerate(a.ref or [], 1):
        todo.append((f"R{i}", ref, "", ""))
    if getattr(a, "refs", None):
        if not a.pick:
            raise IglError("--refs E## needs --pick with the item numbers to compare, e.g. --pick 3,7")
        todo += _picked(case, a.refs, a.pick)
    if not todo:
        raise IglError("give --ref <url|file|E##> (repeatable) or --refs <E## of a refs/revsearch result> --pick 3,7")
    rdir = case.work / "refs" / "compare"
    rdir.mkdir(parents=True, exist_ok=True)
    http = _http(case, "reference images")
    loaded = []
    for label, src, fallback, page in todo:
        im, origin = None, src
        for cand_src in [s for s in (src, fallback) if s]:
            if cand_src.startswith(("http://", "https://")):
                dest = rdir / f"ref-{len(list(rdir.iterdir())):03d}.img"
                host = cand_src.split("/")[2]
                if not http.download(cand_src, dest, headers={"Referer": f"https://{host}/"}, timeout=25):
                    print(f"{label}: could not download {short(cand_src, 90)} ({http.last_error})")
                    continue
                try:
                    im = imaging.flatten(Image.open(dest))
                    origin = cand_src
                    break
                except Exception:  # noqa: BLE001
                    print(f"{label}: not an image: {short(cand_src, 90)}")
            else:
                try:
                    p = Path(cand_src)
                    eid = case.resolve_files([cand_src])[0] if not (p.is_absolute() and case.work in p.parents) else None
                    im = imaging.flatten(Image.open(case.file_path(eid) if eid else p))
                    origin = eid or cand_src
                    if eid and label.startswith("R"):
                        label = f"{label} {eid}"
                    break
                except IglError:
                    raise
                except Exception:  # noqa: BLE001
                    print(f"{label}: cannot open {short(cand_src, 90)}")
        if im is None:
            print(f"{label}: no usable image (save it from your browser and pass the file instead)")
            continue
        if origin.startswith("http") and label.startswith("R"):
            label = f"{label} {origin.split('/')[2]}"
        loaded.append((label, im, origin, page))
    if not loaded:
        raise IglError("no usable reference image")
    tiles_ = [("QUERY (this photo)", q)] + [(lbl, im) for lbl, im, _, _ in loaded]
    sheet = imaging.contact_sheet(tiles_, cols=min(3, len(tiles_)), cell=520)
    name = a.label or (cand["name"] if cand else "refs")
    eid, p = case.reserve_file(f"compare-{name}", "jpg",
                               f"side-by-side: photo vs {len(loaded)} reference image(s) "
                               f"({'; '.join(short(o, 70) for _, _, o, _ in loaded)[:300]})", tool="compare")
    sheet.save(p, quality=88)
    print(f"{eid}  {p}  (side-by-side sheet)")
    results: list[dict] = []
    classes: list[str] = []
    jid = None
    if not a.no_match:
        try:
            matcher = match.Matcher(q)
        except ImportError:
            matcher = None
        qh = match.hashes(q)
        rh = [match.hashes(im) for _, im, _, _ in loaded]
        for (lbl, im, src, page), h in zip(loaded, rh):
            dup = match.duplicate_from(qh, h)
            geo_ = matcher.score(im) if matcher else {"available": False, "note": "OpenCV/numpy missing"}
            v, cls = match.verdict(dup, geo_), match.classify(dup, geo_)
            row = {"ref": lbl, "source": src, "page": page, "cls": cls, "verdict": v, "duplicate": dup,
                   "geometric": {k: val for k, val in geo_.items() if k != "pairs"}}
            if geo_.get("available") and geo_.get("pairs") and geo_.get("level") != "none":
                vid, vp = case.reserve_file(f"match-{name}-{lbl.split()[0].lstrip('#').lower()}", "jpg",
                                            f"inlier correspondences: {qlabel} (left) vs {lbl} (right) - where do the "
                                            "lines land: fixed architecture, unique art, or movable furniture?",
                                            tool="compare")
                match.draw(q, im, geo_["pairs"]).save(vp, quality=85)
                row["inlier_view"] = vid
            results.append(row)
            classes.append(cls)
            print(f"\n{lbl}: {v}")
            if row.get("inlier_view"):
                print(f"   inlier view {row['inlier_view']}  {case.file_path(row['inlier_view'])}")
        same = []                       # references that are one photograph count once, however many sites copy it
        for i in range(len(loaded)):
            for j in range(i + 1, len(loaded)):
                d2 = match.duplicate_from(rh[j], rh[i])
                g2 = {} if (d2["near_duplicate"] or d2["mirrored_duplicate"] or matcher is None) else \
                    match.geometric(loaded[j][1], loaded[i][1])
                if d2["near_duplicate"] or d2["mirrored_duplicate"] or g2.get("same_photo"):
                    same.append([loaded[i][0].split()[0], loaded[j][0].split()[0]])
                    print(f"\nNOTE {loaded[j][0].split()[0]} and {loaded[i][0].split()[0]} are the SAME PHOTOGRAPH (copy, "
                          "crop or resize): one reference, not two - never count them as independent confirmations")
        if same:
            results.append({"same_photograph_pairs": same})
        jid = _save_json(case, f"compare-{name}", f"automatic match tests behind {eid}", results)
        case.data["files"][jid]["tool"] = "compare"
        meta = {"json": jid, "classes": classes}
        for fid in [eid] + [r["inlier_view"] for r in results if r.get("inlier_view")] + [jid]:
            case.data["files"][fid]["meta"] = meta
        print(f"\nmatch tests saved as {jid}")
    summary = ", ".join(f"{lbl.split()[0]} {match.LABEL.get(c, c)}" for (lbl, _, _, _), c in zip(loaded, classes)) or \
        "sheet only (--no-match)"
    _attempt(case, "reference_match", "results", (f"for {cand['id']} {cand['name']}: " if cand else "") +
             f"compare {eid}: {summary}", engine="compare", files=[eid] + ([jid] if jid else []), save=False)
    if cand:
        cand.setdefault("refs", []).append({"json": jid, "sheets": [eid], "compared": len(loaded),
                                            "counts": {c: classes.count(c) for c in set(classes)}, "time": _now()})
    case.save()
    print("\nNext: LOOK at the sheet and every inlier view, then decide what the agreement is ON:\n"
          "  - fixed architecture (windows, ceiling, columns, built-ins, floor pattern, the view) or art made for this "
          "venue -> the same place;\n"
          "  - furniture, carpet, lamps, mass-produced prints -> the same design (brand, supplier), not the site;\n"
          "  - a COPY / SAME PHOTOGRAPH -> provenance: what its page says is a `traced` clue (--url <page>), never "
          "a match.\n"
          ">=3 distinct invariant features against an independent reference make a `matched` clue:\n"
          f"  igl.py note {case.root} \"Matches <source, date>: ...\" --kind match --status matched --source reference "
          f"--file {eid} --features \"feature 1; feature 2; feature 3\" --for C#:60 --why \"...\"\n"
          "Then run the same comparison for the best RIVAL: a match that the rival's photos also produce proves "
          "nothing.")
    return 0


# ----------------------------------------------------------------------------- share, snapshot
def cmd_share(a) -> int:
    """Temporary public copy (metadata stripped) + by-URL reverse-search links for a browser tool."""
    from . import share
    case = Case(Path(a.case))
    img, _ = imaging.open_image(case.image_path)
    sdir = case.work / "share"
    sdir.mkdir(parents=True, exist_ok=True)
    images = _query_images(case, a, img, sdir, full_default=False)
    http = _http(case, "temporary image host")
    out = []
    for label, path in images:
        r = share.upload(http, path, host=a.host)
        if not r["ok"]:
            print(f"[{label}] could not share: {r['error']}")
            out.append({"label": label, "ok": False, "error": r["error"]})
            continue
        links = revsearch.by_url_links(r["url"])
        rec = {"label": label, "ok": True, "host": r["host"], "url": r["url"], "expires": r["expires"], "time": _now()}
        case.data["auto"].setdefault("shared", []).append(rec)
        out.append({**rec, "links": links})
        print(f"[{label}] {r['url']}  (host {r['host']}, deleted after {r['expires']}; metadata stripped)")
        for eng, u in links.items():
            print(f"   {eng:<7} {u}")
    case.event("share", "; ".join(f"{o['label']}: " + (f"{o['host']} {o['url']}" if o["ok"] else "failed")
                                  for o in out))
    if not any(o["ok"] for o in out):
        print("\nNo temporary host reachable from here: upload the file in your browser tool instead, or ask the user. "
              "Log reverse_search for each engine you could not run (blocked / unavailable, not no_results).")
        return 0
    print("\nOpen the lens and bing links in your browser tool (Claude in Chrome, the built-in browser) or hand them to "
          "the user. Lens: read 'Exact matches' and 'Visual matches' separately from the AI overview. Feed promising "
          f"result images back for an objective comparison:\n  igl.py refs {case.root} --image <image url> [--image ...]\n"
          "and log each engine:\n"
          f"  igl.py log {case.root} reverse_search --status results|no_results|blocked --engine lens --detail \"...\"")
    return 0


def cmd_snapshot(a) -> int:
    case = Case(Path(a.case))
    label = a.label or "web"
    ok, why = revsearch.available()
    eid = None
    if ok:
        import asyncio

        tmp = case.work / "snapshot.jpg"
        tmp.parent.mkdir(parents=True, exist_ok=True)

        async def go():
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                b = await p.chromium.launch(headless=True)
                try:
                    pg = await (await b.new_context(user_agent=revsearch.UA,
                                                    viewport={"width": 1366, "height": 1000})).new_page()
                    await pg.goto(a.url, wait_until="domcontentloaded", timeout=45000)
                    await pg.wait_for_timeout(2500)
                    await pg.screenshot(path=str(tmp), full_page=True, type="jpeg", quality=75)
                    txt = await pg.evaluate("document.body ? document.body.innerText : ''")
                    title = await pg.title()
                finally:
                    await b.close()
                return title, txt

        try:
            title, txt = asyncio.run(go())
            from PIL import Image
            eid, path = case.reserve_file(f"snap-{label}", "jpg", f"screenshot of {a.url}")
            im = Image.open(tmp)
            if im.height > 6000:                      # keep evidence files a reasonable size
                im = im.crop((0, 0, im.width, 6000))
            im.convert("RGB").save(path, quality=75)
            tmp.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            if eid:
                case.data["files"].pop(eid, None)
                eid = None
            ok, why = False, f"{type(e).__name__}: {str(e).splitlines()[0][:150] if str(e) else ''}"
    if not ok:
        r = _http(case, "web").get(a.url, as_json=False, cache=False)
        if not r["ok"]:
            raise IglError(f"could not fetch {a.url}: {r.get('error')} (browser unavailable: {why})")
        import re as _re
        html = r["text"]
        title = (_re.search(r"<title[^>]*>(.*?)</title>", html, _re.S | _re.I) or [None, ""])[1].strip()
        txt = _re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=_re.S | _re.I)
        txt = _re.sub(r"<[^>]+>", " ", txt)
    tid, tp = case.reserve_file(f"snap-{label}-text", "txt", f"page title and text of {a.url}")
    tp.write_text(redact(f"URL: {a.url}\nTITLE: {title}\nFETCHED: {_now()}\n\n{' '.join(txt.split())[:20000]}"),
                  encoding="utf-8")
    case.save()
    print(f"{eid + '  ' + str(case.file_path(eid)) if eid else '(no screenshot: ' + why + ')'}\n{tid}  {tp}\nTITLE: {title}")
    return 0
