"""REPORT.md (for people) and result.json (for machines), generated from the ledger so the narrative can
never drift from the recorded evidence."""
from __future__ import annotations

from . import SCHEMA_RESULT, __version__, scoring
from .case import CORE_METHODS, GRADE, LEVELS, OPTIONAL_METHODS, RESOLVED, Case
from .match import LABEL
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
        lead = ans.get("lead")
        if lead and lead.get("candidate") in d["candidates"]:      # as the board stands now, not when it was recorded
            now_ = scoring.assess(case, lead["candidate"])
            lead = {**lead, "tier": now_["tier"], "share": round(now_["share"], 3)}
        res["lead"] = ({k: lead.get(k) for k in ("candidate", "name", "address", "lat", "lon", "radius_m", "level",
                                                 "tier", "share", "falsify")} if lead else None)
        pin = ans.get("best_estimate") or {"basis": "answer", "candidate": ans["candidate"], "name": ans["name"],
                                            "address": ans.get("address"), "lat": ans.get("lat"), "lon": ans.get("lon"),
                                            "level": ans.get("level"), "tier": ans.get("confidence")}
        res["best_estimate"] = {**pin, "map_links": map_links(pin["lat"], pin["lon"]) if pin.get("lat") is not None else {},
                                "verified_level": ans.get("level"), "verified_radius_m": ans.get("radius_m"),
                                "verified_confidence": ans.get("confidence")}
        coord = (f"{ans['lat']:.6f}, {ans['lon']:.6f} (WGS84) ± {ans.get('radius_m')} m — "
                 f"[OpenStreetMap]({links['openstreetmap']}) · [Google Maps]({links['google_maps']})"
                 if links else "not determined")
        lines += ["| | |", "|---|---|",
                  f"| **Answer (verified level)** | **{ans['name']}**" + (f" — {ans['address']}" if ans.get("address") else "") + " |",
                  f"| **Coordinates** | {coord} |",
                  f"| **Confidence** | **{ov['tier'].upper()}** at {ans.get('level')} level"
                  + (f" (rules cap: {ans.get('cap')})" if ans.get("cap") and ans.get("cap") != ov["tier"] else "")
                  + (f" · share {chain_rows[-1]['share']:.2f} of the {ans.get('level')} board" if chain_rows else "")
                  + " |",
                  f"| **Photo** | `{d['image']['file']}`" + (f" · sha256 `{d['image'].get('sha256', '')[:16]}…`"
                                                             if d['image'].get('sha256') else "") + " |",
                  f"| **Generated** | {now()[:16].replace('T', ' ')} · indoor-geolocator {__version__} |", ""]
        if lead:
            lc = (f"{lead['lat']:.6f}, {lead['lon']:.6f} ± {lead.get('radius_m')} m — "
                  f"[map]({map_links(lead['lat'], lead['lon'])['openstreetmap']})" if lead.get("lat") is not None
                  else "no coordinates")
            at = next(i for i, ln in enumerate(lines) if ln.startswith("| **Confidence**")) + 1
            lines[at:at] = [f"| **Best lead (unverified)** | {lead['name']} ({lead['level']}, {lead['tier'].upper()}, "
                            f"share {lead['share']:.2f}) — {lc}"
                            + (f"<br>would be confirmed or ruled out by: {lead['falsify']}" if lead.get("falsify") else "")
                            + " |"]
        if pin.get("lat") is not None and pin["basis"] == "lead":      # otherwise the pin is the answer's own point
            pl = map_links(pin["lat"], pin["lon"])
            at = next(i for i, ln in enumerate(lines) if ln.startswith("| **Photo**"))
            lines[at:at] = [f"| **Best-estimate pin** | {pin['lat']:.6f}, {pin['lon']:.6f} — {pin['name']} — the "
                            f"unverified lead: the single most likely point, inside the verified {ans.get('level')} — "
                            f"[OpenStreetMap]({pl['openstreetmap']}) · [Google Maps]({pl['google_maps']}) |"]
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
    ver_rows, ver_json = [], []
    matched_for: dict[str, list[str]] = {}
    for e in d["evidence"]:
        if e["lr"] > 1 and clues.get(e["clue"], {}).get("status") == "matched":
            matched_for.setdefault(e["candidate"], []).append(e["clue"])
    for c in d["candidates"].values():
        runs = c.get("refs") or []
        matched_by = sorted(set(matched_for.get(c["id"], [])), key=lambda n: int(n[1:]))
        if not runs and not matched_by:
            continue
        compared = sum(r.get("compared", 0) for r in runs)
        counts: dict[str, int] = {}
        for r in runs:
            for k, v in (r.get("counts") or {}).items():
                counts[k] = counts.get(k, 0) + v
        files = [f for r in runs for f in (r.get("sheets") or []) + ([r["json"]] if r.get("json") else [])]
        files += [f for n in matched_by for f in clues[n].get("files", []) if f not in files]
        res_txt = ", ".join(f"{counts[k]} {LABEL[k]}" for k in ("copy", "same", "partial", "none") if counts.get(k)) or "-"
        ver_rows.append(f"| {c['id']} {c['name']} ({c['level']}) | {compared or '-'} | {res_txt} | "
                        f"{', '.join(matched_by) or 'none'} | {_files_md(case, files)} |")
        ver_json.append({"candidate": c["id"], "name": c["name"], "level": c["level"], "compared": compared,
                         "counts": counts, "matched_clues": matched_by, "files": files})
    res["verification"] = ver_json
    venue = None                                     # the venue the answer names or points at as its lead
    if ans:
        for cid in (ans["candidate"], (ans.get("lead") or {}).get("candidate")):
            if cid in d["candidates"] and d["candidates"][cid]["level"] in ("site", "room"):
                venue = cid
                break
    rivals = case.rivals_compared(venue) if venue else []
    res["rival_control"] = [{"candidate": r["id"], "name": r["name"]} for r in rivals]
    if ver_rows or venue:
        lines += ["## Verification against reference imagery", ""]
        if ver_rows:
            lines += ["| Candidate | Reference photos compared | Automatic result | `matched` clues | Files |",
                      "|---|---|---|---|---|"] + ver_rows
            lines += ["", "COPY = the same photograph (provenance, never a confirmation) · SAME SCENE / PARTIAL = "
                          "geometric agreement found by feature matching · unconfirmed = no automatic match, judged by "
                          "eye on the sheets (feature matching misses photos of the same room from another time or "
                          "angle). A `matched` clue names the specific fixed features that agree; recorded for an area "
                          "or a group instead of one venue, it is a design match (the same furnishing in several "
                          "venues).", ""]
        else:
            lines += ["No candidate was compared with reference imagery in this case.", ""]
        if venue:
            lines += ["Rival control for " + d["candidates"][venue]["name"] + ": " + (
                ", ".join(f"{r['id']} {r['name']}" for r in rivals) + " went through the same comparison."
                if rivals else "none on file. Without a rival put through the same comparison, a match can be a "
                               "look-alike or a shared design, and the confidence stays below HIGH."), ""]
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
            feats = (" · features: " + short("; ".join(c["features"]), 220)) if c.get("features") else ""
            lines.append(f"| {cid} | {short(c['text'], 160)}{feats} | {c['status']} ({GRADE.get(c['status'], '?')}) | "
                         f"{c['source']} | {'; '.join(eff) or ('context' if c['kind'] in ('hypothesis', 'context', 'scene') else 'unlinked')} | "
                         f"{_files_md(case, c.get('files', []))} |")
        lines.append("")
        res["evidence"] = [{"id": cid, "text": c["text"], "kind": c["kind"], "status": c["status"],
                            "grade": GRADE.get(c["status"]), "source": c["source"], "files": c.get("files", []),
                            "url": c.get("url"), "features": c.get("features", [])} for cid, c in clues.items()]

    lines += ["## Candidates considered", ""]
    res["candidates"] = {}
    lead_id = ((ans or {}).get("lead") or {}).get("candidate")
    above = {r["id"] for r in chain_rows[:-1]}                     # the places the answer lies in

    def status_of(r: dict) -> str:
        if r.get("rest"):
            return "not on the board"
        if r["excluded"]:
            return "excluded"
        if ans and ans["candidate"] == r["id"]:
            return "answer"
        if r["id"] in above:
            return "contains the answer"
        return "lead (unverified)" if r["id"] == lead_id else "open"

    for lv in LEVELS:
        rows = scoring.rank(case, lv)
        if not rows:
            continue
        lines += [f"**{lv}**", "", "| # | Candidate | Share | Status | Location |", "|---|---|---|---|---|"]
        res["candidates"][lv] = []
        listed = [r for r in rows if not r.get("rest")]           # the open-world block is not a candidate
        block = next((r for r in rows if r.get("rest")), None)
        # shown: up to 12 rows that carry weight or were excluded, the top three in any case, and always the
        # answer, the places it lies in and the lead, wherever they rank
        keep = ({ans["candidate"], lead_id} | above) if ans else set()
        keep |= {r["id"] for r in [r for r in listed if r["share"] >= 0.01 or r["excluded"]][:12] + listed[:3]}
        shown = [r for r in listed if r["id"] in keep]
        hidden = [r for r in listed if r["id"] not in keep]
        for r in rows:
            c = r["c"]
            res["candidates"][lv].append({"id": r["id"], "name": c["name"], "share": round(r["share"], 4),
                                          "status": status_of(r), "lat": c.get("lat"), "lon": c.get("lon"),
                                          "address": c.get("address")})
        for r in shown:
            c = r["c"]
            loc = (f"{c['lat']:.5f}, {c['lon']:.5f}" if c.get("lat") is not None else "") + \
                  (f" — {short(c['address'], 70)}" if c.get("address") else "")
            lines.append(f"| {r['id']} | {c['name']} | {r['share']:.2f} | {status_of(r)} | {loc} |")
        if hidden:
            top = max(h["share"] for h in hidden)
            bound = f"≤ {top:.2f}" if top >= 0.005 else "< 0.01"
            lines.append(f"| … | {len(hidden)} more candidate(s), each with share {bound} "
                         f"({', '.join(h['name'] for h in hidden[:8])}{', …' if len(hidden) > 8 else ''}) | | | |")
        if block:
            lines.append(f"| {block['id']} | {block['name']} | {block['share']:.2f} | {status_of(block)} | |")
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
        if ev["event"] in ("note", "cand", "exclude", "log", "answer", "init", "scan", "revsearch", "link", "share",
                           "refs"):
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
        alts = [r for r in scoring.rank(case, lv) if r["id"] != ans["candidate"] and not r["excluded"]
                and not r.get("rest")][:5]
    res["alternatives"] = [{"id": r["id"], "name": r["name"], "share": round(r["share"], 4),
                            "how_to_tell": r["c"].get("falsify", "")} for r in alts]
    if ans:
        rest = [r for r in scoring.rank(case, d["candidates"][ans["candidate"]]["level"]) if r.get("rest")]
        res["unlisted_share"] = round(rest[0]["share"], 4) if rest else 0.0
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
    services = sorted(set(d.get("auto", {}).get("services", [])))
    shared = [x for x in d.get("auto", {}).get("shared", []) if x.get("ok", True)]
    closed = sorted({a.get("engine") for a in d["attempts"] if a["method"] == "reverse_search" and a.get("engine")
                     and a["status"] in ("blocked", "unavailable")} - set(uploads))
    lines += ["## Data handling", "",
              f"- Photo uploaded for reverse image search to: {', '.join(uploads) if uploads else 'none recorded'}"
              + (f" (tried without a search taking place: {', '.join(closed)})" if closed else ""),
              "- Temporary public copies (metadata stripped): " + ("; ".join(
                  f"{x['label']} on {x['host']} ({x['time'][:16].replace('T', ' ')}, deleted after {x['expires']})"
                  for x in shared) if shared else "none"),
              f"- Online services queried by the tools: {', '.join(services) if services else 'none recorded'}",
              "- Personal names / home addresses of private individuals are not reproduced in this report.", ""]
    res["data_handling"] = {"reverse_search_engines": uploads, "services": services,
                            "temporary_copies": [{k: x.get(k) for k in ("label", "host", "time", "expires")}
                                                 for x in shared]}

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
