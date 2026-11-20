"""REPORT.md (for people) and result.json (for machines), generated from the ledger so the narrative can
never drift from the recorded evidence."""
from __future__ import annotations

from . import SCHEMA_RESULT, __version__, scoring
from .case import CORE_METHODS, GRADE, LEVELS, OPTIONAL_METHODS, RESOLVED, Case
from .util import now, short, write_json

DEFAULT_RADIUS = {"room": 30, "site": 60, "district": 1500, "city": 8000, "region": 80000, "country": 400000}


def map_links(lat: float, lon: float) -> dict:
    return {"openstreetmap": f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=19/{lat:.6f}/{lon:.6f}",
            "google_maps": f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lon:.6f}"}


def _files_md(case: Case, ids: list[str]) -> str:
    return ", ".join(f"[{i}]({case.data['files'][i]['path']})" for i in ids if i in case.data["files"]) or ""


def build(case: Case) -> tuple[str, dict]:
    d = case.data
    ans = d.get("answer")
    res: dict = {"schema": SCHEMA_RESULT, "generated": now(), "tool_version": __version__,
                 "image": {"file": d["image"]["file"], "sha256": d["image"].get("sha256"),
                           "size": d["image"].get("size")}}
    lines: list[str] = ["# Indoor geolocation report", ""]
    chain_rows, ov = [], {"tier": "none", "level": None}
    if ans:
        chain_rows = scoring.chain(case, ans["candidate"])
        ov = {"tier": ans.get("confidence") or scoring.overall(chain_rows)["tier"], "level": ans.get("level")}
        links = map_links(ans["lat"], ans["lon"]) if ans.get("lat") is not None else {}
        res["answer"] = {k: ans.get(k) for k in ("candidate", "name", "address", "lat", "lon", "radius_m", "level")}
        res["answer"]["map_links"] = links
        res["confidence"] = {"overall": ov["tier"], "level": ans.get("level"), "cap": ans.get("cap"),
                             "by_level": {r["level"]: {"candidate": r["name"], "tier": r["tier"],
                                                       "share": round(r["share"], 3), "reasons": r["reasons"]}
                                          for r in chain_rows}}
        res["summary"] = ans.get("summary", "")
        coord = (f"{ans['lat']:.6f}, {ans['lon']:.6f} (WGS84) ± {ans.get('radius_m')} m — "
                 f"[OpenStreetMap]({links['openstreetmap']}) · [Google Maps]({links['google_maps']})"
                 if links else "not determined")
        lines += ["| | |", "|---|---|",
                  f"| **Answer** | **{ans['name']}**" + (f" — {ans['address']}" if ans.get("address") else "") + " |",
                  f"| **Coordinates** | {coord} |",
                  f"| **Confidence** | **{ov['tier'].upper()}** at {ans.get('level')} level"
                  + (f" (rules cap: {ans.get('cap')})" if ans.get("cap") and ans.get("cap") != ov["tier"] else "") + " |",
                  f"| **Photo** | `{d['image']['file']}`" + (f" · sha256 `{d['image'].get('sha256', '')[:16]}…`"
                                                             if d['image'].get('sha256') else "") + " |",
                  f"| **Generated** | {now()[:16].replace('T', ' ')} · indoor-geolocator {__version__} |", ""]
        if ans.get("summary"):
            lines += ["> " + ans["summary"].replace("\n", "\n> "), ""]
    else:
        res["answer"] = None
        res["confidence"] = {"overall": "none"}
        lines += ["**No answer recorded yet** (`igl.py answer`). Current state of the investigation below.", ""]

    if chain_rows:
        lines += ["## Confidence by level", "", "| Level | Candidate | Share | Tier | Basis |", "|---|---|---|---|---|"]
        for r in chain_rows:
            lines.append(f"| {r['level']} | {r['name']} | {r['share']:.2f} | {r['tier']} | {'; '.join(r['reasons'])} |")
        lines.append("")

    clues = d["clues"]
    if clues:
        lines += ["## Evidence", "", "| Clue | Observation | Obtained (grade) | Lineage | Effect on candidates | Files |",
                  "|---|---|---|---|---|---|"]
        share_of = {}
        for lv in LEVELS:
            for r in scoring.rank(case, lv):
                share_of[r["id"]] = r["share"]
        for cid, c in clues.items():
            eff = []
            links = sorted([e for e in d["evidence"] if e["clue"] == cid],
                           key=lambda e: -share_of.get(e["candidate"], 0))
            if len(links) > 6:
                lrs = sorted({f"×{e['lr']:g}" for e in links})
                names = [d["candidates"].get(e["candidate"], {}).get("name", e["candidate"]) for e in links[:4]]
                eff.append(f"{len(links)} candidates {'/'.join(lrs)} (e.g. {', '.join(names)}, …)")
                links = []
            for e in links:
                nm = d["candidates"].get(e["candidate"], {}).get("name", e["candidate"])
                eff.append(f"{nm} ×{e['lr']:g}")
            for x in d["exclusions"]:
                if x["clue"] == cid:
                    eff.append(f"excludes {d['candidates'].get(x['candidate'], {}).get('name', x['candidate'])}")
            lines.append(f"| {cid} | {short(c['text'], 160)} | {c['status']} ({GRADE.get(c['status'], '?')}) | "
                         f"{c['source']} | {'; '.join(eff) or ('context' if c['kind'] in ('hypothesis', 'context', 'scene') else 'unlinked')} | "
                         f"{_files_md(case, c.get('files', []))} |")
        lines.append("")
        res["evidence"] = [{"id": cid, "text": c["text"], "kind": c["kind"], "status": c["status"],
                            "grade": GRADE.get(c["status"]), "source": c["source"], "files": c.get("files", []),
                            "url": c.get("url")} for cid, c in clues.items()]

    lines += ["## Candidates considered", ""]
    res["candidates"] = {}
    for lv in LEVELS:
        rows = scoring.rank(case, lv)
        if not rows:
            continue
        lines += [f"**{lv}**", "", "| # | Candidate | Share | Status | Location |", "|---|---|---|---|---|"]
        res["candidates"][lv] = []
        shown = [r for r in rows if r["share"] >= 0.01 or r["excluded"] or (ans and ans["candidate"] == r["id"])][:12]
        if len(shown) < min(3, len(rows)):
            shown = rows[:3]
        hidden = [r for r in rows if r not in shown]
        for r in rows:
            c = r["c"]
            status = "excluded" if r["excluded"] else ("answer" if ans and ans["candidate"] == r["id"] else "open")
            res["candidates"][lv].append({"id": r["id"], "name": c["name"], "share": round(r["share"], 4),
                                          "status": status, "lat": c.get("lat"), "lon": c.get("lon"),
                                          "address": c.get("address")})
        for r in shown:
            c = r["c"]
            loc = (f"{c['lat']:.5f}, {c['lon']:.5f}" if c.get("lat") is not None else "") + \
                  (f" — {short(c['address'], 70)}" if c.get("address") else "")
            status = "excluded" if r["excluded"] else ("answer" if ans and ans["candidate"] == r["id"] else "open")
            lines.append(f"| {r['id']} | {c['name']} | {r['share']:.2f} | {status} | {loc} |")
        if hidden:
            top_hidden = max(h["share"] for h in hidden)
            lines.append(f"| … | {len(hidden)} more candidate(s), each with share ≤ {top_hidden:.2f} "
                         f"({', '.join(h['name'] for h in hidden[:8])}{', …' if len(hidden) > 8 else ''}) | | | |")
        lines.append("")
    if d["exclusions"]:
        lines += ["Exclusions:", ""]
        for x in d["exclusions"]:
            nm = d["candidates"].get(x["candidate"], {}).get("name", x["candidate"])
            lines.append(f"- {nm} — by {x['clue']}: {x['why']} {_files_md(case, x.get('files', []))}")
        lines.append("")

    lines += ["## Reasoning timeline", ""]
    n = 0
    for ev in d["timeline"]:
        if ev["event"] in ("note", "cand", "exclude", "log", "answer", "init", "scan", "revsearch", "link"):
            n += 1
            lines.append(f"{n}. `{ev['t'][11:16]}` {ev['text']}")
    lines.append("")

    state = case.method_state()
    lines += ["## Methods attempted", "", "| Method | Status | Attempts | Last detail |", "|---|---|---|---|"]
    cov = {}
    for m, desc in list(CORE_METHODS.items()) + list(OPTIONAL_METHODS.items()):
        st = state.get(m)
        if m in OPTIONAL_METHODS and not st:
            continue
        status = st["status"] if st else "PENDING"
        cov[m] = status
        lines.append(f"| {m}{' (core)' if m in CORE_METHODS else ''} | {status} | {st['n'] if st else 0} | "
                     f"{short(st['detail'], 110) if st else desc} |")
    lines.append("")
    res["methods"] = cov
    core_done = sum(1 for m in CORE_METHODS if state.get(m, {}).get("status") in RESOLVED)
    res["coverage"] = f"{core_done}/{len(CORE_METHODS)} core methods resolved"

    open_items = [c for c in clues.values() if c["kind"] == "contradiction" and not c.get("resolved")]
    alts = []
    if ans:
        lv = d["candidates"][ans["candidate"]]["level"]
        alts = [r for r in scoring.rank(case, lv) if r["id"] != ans["candidate"] and not r["excluded"]][:5]
    res["alternatives"] = [{"id": r["id"], "name": r["name"], "share": round(r["share"], 4),
                            "how_to_tell": r["c"].get("falsify", "")} for r in alts]
    if open_items or alts or (ans and ans.get("open_questions")):
        lines += ["## Open questions and alternatives", ""]
        for c in open_items:
            lines.append(f"- Unresolved contradiction {c['id']}: {c['text']}")
        for r in alts:
            lines.append(f"- Alternative {r['id']} {r['name']} (share {r['share']:.2f})"
                         + (f" — would be confirmed by: {r['c']['falsify']}" if r["c"].get("falsify") else ""))
        if ans and ans.get("open_questions"):
            lines.append(f"- {ans['open_questions']}")
        lines.append("")

    uploads = sorted({a.get("engine") for a in d["attempts"] if a["method"] == "reverse_search" and a.get("engine")
                      and a["status"] in ("results", "no_results")})
    services = sorted({s for s in d.get("auto", {}).get("services", [])})
    lines += ["## Data handling", "",
              f"- Photo uploaded for reverse image search to: {', '.join(uploads) if uploads else 'none recorded'}",
              f"- Online services queried by the tools: {', '.join(services) if services else 'none recorded'}",
              "- Personal names / home addresses of private individuals are not reproduced in this report.", ""]
    res["data_handling"] = {"reverse_search_engines": uploads, "services": services}

    refs = case.referenced_files()
    lines += ["## Files", "", "| File | What it shows |", "|---|---|", f"| [{d['image']['file']}]({d['image']['file']}) | "
              "the photo (byte-exact copy) |", "| [input/metadata.json](input/metadata.json) | full metadata dump |"]
    for eid, f in sorted(d["files"].items()):
        if eid in refs:
            lines.append(f"| [{f['path']}]({f['path']}) | {f['what']} |")
    lines += ["| [case.json](case.json) | the complete ledger (every clue, link, attempt and timestamp) |", ""]
    return "\n".join(lines), res


def write(case: Case) -> tuple[str, str]:
    md, res = build(case)
    (case.root / "REPORT.md").write_text(md, encoding="utf-8")
    write_json(case.root / "result.json", res, indent=2)
    return str(case.root / "REPORT.md"), str(case.root / "result.json")
