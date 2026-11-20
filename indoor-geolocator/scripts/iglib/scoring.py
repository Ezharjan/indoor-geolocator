"""Ranking and confidence caps, computed from the ledger (not from memory).

Ranking: within one level every open candidate starts from the same prior (fame and population are not
evidence); each linked clue multiplies its odds by a likelihood ratio (LR), capped by how the clue was
obtained (case.STATUS_CAP). Support flows UP the hierarchy (a matching site supports its city and
country); refutation does not flow up. Excluding a candidate also excludes its descendants. At country
level the unlisted countries compete as one block (C*), so omission is never exclusion.

Confidence caps (an agent may report LESS than the cap, never more):
  HIGH    a decisive clue (read / computed / matched / metadata, LR >= 10) AND >= 2 independent source
          lineages with LR >= 2 AND share >= 0.80 AND no unresolved strong contradiction.
          Site/room level additionally needs a `matched` clue, or decisive clues from >= 2 lineages.
  MEDIUM  a decisive clue OR >= 2 independent lineages, AND share >= 0.50.
  LOW     anything else.
"""
from __future__ import annotations

import math

from .case import DECISIVE, EXCLUDERS, LEVELS, Case

TIERS = ["none", "low", "medium", "high"]


def _evidence_for(case: Case, cid: str) -> list[dict]:
    return [e for e in case.data["evidence"] if e["candidate"] == cid]


def _inherited(case: Case, cid: str, own_clues: set[str]) -> list[dict]:
    best: dict[str, dict] = {}
    for d in case.descendants(cid):
        if case.is_excluded(d["id"]):
            continue
        for e in _evidence_for(case, d["id"]):
            if e["lr"] > 1 and e["clue"] not in own_clues and e["lr"] > best.get(e["clue"], {}).get("lr", 1):
                best[e["clue"]] = {**e, "via": d["id"]}
    return list(best.values())


REST_ID = "C*"


def rank(case: Case, level: str) -> list[dict]:
    """Rows of one level, best first. At country level the countries that are NOT on the board take part
    as one block (id C*, prior = their number, no evidence): leaving a country off the board never
    excludes it, so weak set clues (a socket type) cannot act as silent exclusions."""
    rows = []
    for cid, c in case.data["candidates"].items():
        if c["level"] != level:
            continue
        own = _evidence_for(case, cid)
        ev = own + _inherited(case, cid, {e["clue"] for e in own})
        logit = math.log(max(float(c.get("prior", 1.0)), 1e-9)) + sum(math.log(max(e["lr"], 1e-9)) for e in ev)
        rows.append({"id": cid, "name": c["name"], "level": level, "parent": c.get("parent"), "logit": logit,
                     "ev": ev, "excluded": case.is_excluded(cid), "c": c})
    if level == "country" and rows:
        from .knowledge import universe_size
        rest = universe_size() - len(rows)
        if rest > 0:
            name = f"other countries ({rest} not on the board)"
            rows.append({"id": REST_ID, "name": name, "level": level, "parent": None, "logit": math.log(rest),
                         "ev": [], "excluded": False, "rest": True,
                         "c": {"id": REST_ID, "name": name, "level": level, "lat": None, "lon": None, "rest": True}})
    open_rows = [r for r in rows if not r["excluded"]]
    if open_rows:
        m = max(r["logit"] for r in open_rows)
        z = sum(math.exp(r["logit"] - m) for r in open_rows)
        for r in open_rows:
            r["share"] = math.exp(r["logit"] - m) / z
    for r in rows:
        r.setdefault("share", 0.0)
    rows.sort(key=lambda r: (r["excluded"], -round(r["share"], 9), int(r["id"][1:]) if r["id"][1:].isdigit() else 10**9))
    return rows


def frontier(case: Case) -> str | None:
    """Finest level that has at least one open candidate."""
    for lv in reversed(LEVELS):
        if any(c["level"] == lv and not case.is_excluded(cid) for cid, c in case.data["candidates"].items()):
            return lv
    return None


def assess(case: Case, cid: str) -> dict:
    """Confidence cap of one candidate with the reasons, from the structure of its evidence."""
    c = case.data["candidates"][cid]
    rows = {r["id"]: r for r in rank(case, c["level"])}
    row = rows[cid]
    clues = case.data["clues"]
    support = [e for e in row["ev"] if e["lr"] > 1]
    decisive = [e for e in support if clues[e["clue"]]["status"] in DECISIVE and e["lr"] >= 10]
    lineages = sorted({clues[e["clue"]]["source"] for e in support if e["lr"] >= 2})
    dec_lineages = sorted({clues[e["clue"]]["source"] for e in decisive})
    matched = [e for e in support if clues[e["clue"]]["status"] == "matched"]
    against = [e for e in _evidence_for(case, cid)
               if e["lr"] <= 0.5 and clues[e["clue"]]["status"] in EXCLUDERS and not clues[e["clue"]].get("resolved")]
    share = row["share"]
    reasons = [f"share {share:.2f} at {c['level']} level",
               f"{len(decisive)} decisive clue(s)" + (f" from {', '.join(dec_lineages)}" if dec_lineages else ""),
               f"{len(lineages)} independent lineage(s) with LR>=2" + (f": {', '.join(lineages)}" if lineages else "")]
    if against:
        reasons.append(f"{len(against)} unresolved strong contradiction(s): {', '.join(e['clue'] for e in against)}")
    if row["excluded"]:
        return {"tier": "none", "share": 0.0, "reasons": reasons + ["candidate is excluded"], "decisive": [],
                "lineages": lineages}
    site_ok = c["level"] not in ("site", "room") or bool(matched) or len(dec_lineages) >= 2
    if decisive and len(lineages) >= 2 and share >= 0.8 and not against and site_ok:
        tier = "high"
    elif (decisive or len(lineages) >= 2) and share >= 0.5:
        tier = "medium"
        if decisive and len(lineages) >= 2 and share >= 0.8 and not against and not site_ok:
            reasons.append("HIGH at site level needs a `matched` clue (reference imagery) or decisive clues from "
                           "two lineages")
    else:
        tier = "low"
    return {"tier": tier, "share": share, "reasons": reasons, "decisive": [e["clue"] for e in decisive],
            "lineages": lineages, "matched": [e["clue"] for e in matched]}


def chain(case: Case, cid: str) -> list[dict]:
    """The candidate and its ancestors, coarse to fine, each with its assessment."""
    items = list(reversed(case.ancestors(cid))) + [case.data["candidates"][cid]]
    return [{"id": c["id"], "name": c["name"], "level": c["level"], **assess(case, c["id"])} for c in items]


def overall(chain_rows: list[dict]) -> dict:
    """Reported confidence = the finest level rated medium or better (a weak room level does not drag
    down a strong site level); falls back to the best tier available."""
    best = None
    for r in chain_rows:
        if TIERS.index(r["tier"]) >= TIERS.index("medium"):
            best = r
    if best is None and chain_rows:
        best = max(chain_rows, key=lambda r: TIERS.index(r["tier"]))
    return {"tier": best["tier"], "level": best["level"], "candidate": best["id"]} if best else \
        {"tier": "none", "level": None, "candidate": None}
