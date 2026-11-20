"""Ranking and confidence caps, computed from the ledger (not from memory).

Ranking: every open candidate starts from the same prior (fame and population are not evidence); each
linked clue multiplies its odds by a likelihood ratio (LR), capped by how the clue was obtained
(case.STATUS_CAP).

Open world: the candidates on the board never exhaust the world. At country level the unlisted countries
compete as one block (prior = their number). Below it, the children of one parent compete with one block
of "unlisted alternatives under that parent" (prior 1). Leaving an alternative off the board therefore
never makes a candidate certain: a lone city without evidence holds half of its country, not all of it.

Decisive clues identify: a clue with status read / computed / matched / metadata / traced and LR >= 10 says
"this is the place", not "a place of this kind". If it is wrong, it is wrong because the reading or the comparison
failed, not because every other country or venue produces the same evidence. So a candidate that holds one
is weighed against the whole field at its level - its listed rivals plus the unlisted block - as ONE
alternative: LR 50 then means about 50:1 that this is the place, whether the board lists one rival or two
hundred and whether the field is 249 unlisted countries or the other hotels of one town. Without this rule
a verified venue could not lift its own country, and listing rivals thoroughly (which the workflow asks
for) would dilute a verified match. Category clues (sockets, language, style: LR < 10, or status observed /
inferred / reported) keep competing with every alternative separately, which keeps them modest.

Coherence: shares are probabilities of the whole chain. A child's share is its share among its siblings
times its parent's share (`cond` keeps the within-parent value), so a city can never look more certain
than its country, nor a hotel than its city. A candidate without a parent hangs under the unlisted block
of the next coarser level on the board (its place in the hierarchy is unknown), so it can never borrow
certainty either. Attach every site to its city and every city to its country (`check` warns).

Support flows UP the hierarchy only for documentary or verified evidence (status reported, metadata, traced,
read, computed, matched): a name read on the key card or a matched reference photo of a site also supports
its city and country. Visual category clues (status observed / inferred: "same chain furniture") do NOT flow
up, because they fit every branch of the chain in every city: letting them flow would reward the city
the agent happened to enumerate (enumeration bias). Link such clues to every level they really speak to.
Refutation does not flow up. Excluding a candidate also excludes its descendants.

Confidence caps (an agent may report LESS than the cap, never more):
  HIGH    a decisive clue (read / computed / matched / metadata / traced, LR >= 10) AND >= 2 independent source
          lineages with LR >= 2 AND share >= 0.80 AND no unresolved strong contradiction.
          A reference match (`matched`) carries HIGH only with its rival control - the closest alternative
          venue put through the same comparison (case.Case.match_controlled) - or beside a decisive clue of
          another lineage. Site/room level needs exactly that: a controlled match, or decisive clues from
          >= 2 lineages (e.g. the name read in the photo AND a reference match).
  MEDIUM  share >= 0.50 AND a decisive clue; above site level, >= 2 independent lineages also suffice.
          A site or room never reaches MEDIUM on resemblance, engine labels or captions alone: that is how
          a look-alike venue gets named with confidence.
  LOW     anything else.
Two rules keep the tiers of one chain consistent. An unresolved strong contradiction against a place also
blocks HIGH for everything inside it. And a place is rated at least as high as the best-rated place inside
it (if the hotel is verified, so are its city and its country), unless the place itself is contradicted.
"""
from __future__ import annotations

import math

from .case import DECISIVE, EXCLUDERS, LEVELS, Case

TIERS = ["none", "low", "medium", "high"]


def _evidence_for(case: Case, cid: str) -> list[dict]:
    return [e for e in case.data["evidence"] if e["candidate"] == cid]


FLOW_UP = {"reported", "metadata", "traced", "read", "computed", "matched"}     # statuses whose support flows up
OPEN_WORLD_PRIOR = 1.0          # below country level: weight of the "unlisted alternatives" block
REST_ID = "C*"


def _inherited(case: Case, cid: str, own_clues: set[str]) -> list[dict]:
    """Support from open descendants (documentary / verified clues only), each clue counted once."""
    best: dict[str, dict] = {}
    clues = case.data["clues"]
    for d in case.descendants(cid):
        if case.is_excluded(d["id"]):
            continue
        for e in _evidence_for(case, d["id"]):
            if clues.get(e["clue"], {}).get("status") not in FLOW_UP:
                continue
            if e["lr"] > 1 and e["clue"] not in own_clues and e["lr"] > best.get(e["clue"], {}).get("lr", 1):
                best[e["clue"]] = {**e, "via": d["id"]}
    return list(best.values())


def _decisive(case: Case, ev: list[dict]) -> list[dict]:
    """Supporting links that identify the candidate (decisive status and LR >= 10)."""
    clues = case.data["clues"]
    return [e for e in ev if e["lr"] >= 10 and clues.get(e["clue"], {}).get("status") in DECISIVE]


def _against_field(members: list[dict], rest_prior: float) -> None:
    """Weigh every member that holds a decisive clue against its whole field (see the module docstring):
    its odds are multiplied by the prior mass of everything else at its level, once, however many decisive
    clues it holds. A member alone with a unit rest block is unchanged."""
    priors = [max(float(m["c"].get("prior", 1.0)), 1e-9) for m in members]
    total = sum(priors) + rest_prior
    for m, p in zip(members, priors):
        if m["identified"]:
            m["field"] = max(1.0, total - p)
            m["logit"] += math.log(m["field"])


def _rest_row(level: str, prior: float, name: str) -> dict:
    return {"id": REST_ID, "name": name, "level": level, "parent": None, "logit": math.log(prior), "ev": [],
            "excluded": False, "rest": True,
            "c": {"id": REST_ID, "name": name, "level": level, "lat": None, "lon": None, "rest": True}}


def _lse(xs: list[float]) -> float:
    m = max(xs)
    return m + math.log(sum(math.exp(x - m) for x in xs))


def board(case: Case) -> dict[str, list[dict]]:
    """Every level's rows, best first, each with `share` (probability of the whole chain) and `cond` (share
    among the siblings under the same parent), plus one open-world row (id C*) per level holding the rest."""
    out: dict[str, list[dict]] = {}
    absolute: dict[str, float] = {}
    cands = case.data["candidates"]
    for level in LEVELS:
        rows = []
        for cid, c in cands.items():
            if c["level"] != level:
                continue
            own = _evidence_for(case, cid)
            ev = own + _inherited(case, cid, {e["clue"] for e in own})
            logit = math.log(max(float(c.get("prior", 1.0)), 1e-9)) + sum(math.log(max(e["lr"], 1e-9)) for e in ev)
            rows.append({"id": cid, "name": c["name"], "level": level, "parent": c.get("parent"), "logit": logit,
                         "ev": ev, "excluded": case.is_excluded(cid), "c": c, "share": 0.0, "cond": 0.0,
                         "identified": bool(_decisive(case, ev)), "field": 1.0})
        if not rows:
            continue
        open_rows = [r for r in rows if not r["excluded"]]
        if level == "country":
            from .knowledge import universe_size
            n_rest = max(0, universe_size() - len(rows))
            _against_field(open_rows, float(n_rest))
            logits = [r["logit"] for r in open_rows] + ([math.log(n_rest)] if n_rest else [])
            if logits:
                z = _lse(logits)
                for r in open_rows:
                    r["share"] = r["cond"] = math.exp(r["logit"] - z)
            rest = _rest_row(level, max(n_rest, 1), f"other countries ({n_rest} not on the board)")
            rest["share"] = rest["cond"] = (math.exp(math.log(n_rest) - z) if (n_rest and logits) else 0.0)
            if n_rest:
                rows.append(rest)
        else:
            groups: dict[str | None, list[dict]] = {}
            for r in open_rows:
                par = r["parent"] if r["parent"] in cands else None
                groups.setdefault(par, []).append(r)
            orphan_above = 1.0                     # no parent: it hangs under the coarser unlisted block
            for coarser in reversed(LEVELS[:LEVELS.index(level)]):
                if coarser in out:
                    orphan_above = next((r["share"] for r in out[coarser] if r.get("rest")), 0.0)
                    break
            for par, members in groups.items():
                _against_field(members, OPEN_WORLD_PRIOR)
                z = _lse([r["logit"] for r in members] + [math.log(OPEN_WORLD_PRIOR)])
                above = absolute.get(par, 0.0) if par else orphan_above
                for r in members:
                    r["cond"] = math.exp(r["logit"] - z)
                    r["share"] = r["cond"] * above
            rest = _rest_row(level, OPEN_WORLD_PRIOR, f"unlisted alternatives (any {level} not on the board)")
            rest["share"] = max(0.0, 1.0 - sum(r["share"] for r in open_rows))
            rest["cond"] = rest["share"]
            rows.append(rest)
        for r in rows:
            if not r.get("rest"):
                absolute[r["id"]] = r["share"]
        rows.sort(key=lambda r: (r["excluded"], -round(r["share"], 9),
                                 int(r["id"][1:]) if r["id"][1:].isdigit() else 10**9))
        out[level] = rows
    return out


def rank(case: Case, level: str) -> list[dict]:
    """Rows of one level, best first, including its open-world row (id C*, `rest`: True)."""
    return board(case).get(level, [])


def frontier(case: Case) -> str | None:
    """Finest level that has at least one open candidate."""
    for lv in reversed(LEVELS):
        if any(c["level"] == lv and not case.is_excluded(cid) for cid, c in case.data["candidates"].items()):
            return lv
    return None


def _strong_against(case: Case, cid: str) -> list[dict]:
    """Unresolved strong contradictions (status read / computed / matched, LR <= 0.5) linked against a candidate."""
    clues = case.data["clues"]
    return [e for e in _evidence_for(case, cid)
            if e["lr"] <= 0.5 and clues[e["clue"]]["status"] in EXCLUDERS and not clues[e["clue"]].get("resolved")]


def _assess_row(case: Case, row: dict, done: dict[str, dict]) -> dict:
    """Confidence cap of one board row. `done` holds the assessments of the finer levels (see assess_all)."""
    cid, c = row["id"], row["c"]
    cands = case.data["candidates"]
    clues = case.data["clues"]
    support = [e for e in row["ev"] if e["lr"] > 1]
    decisive = _decisive(case, support)
    lineages = sorted({clues[e["clue"]]["source"] for e in support if e["lr"] >= 2})
    dec_lineages = sorted({clues[e["clue"]]["source"] for e in decisive})
    matched = [e for e in support if clues[e["clue"]]["status"] == "matched"]
    # a contradiction against the country also stands against every city and venue in it
    against = [(x["id"], e) for x in [c] + case.ancestors(cid) for e in _strong_against(case, x["id"])]
    share = row["share"]
    within = (f" ({row['cond']:.2f} within {cands[row['parent']]['name']})"
              if row.get("parent") in cands and abs(row["cond"] - share) > 0.005 else "")
    reasons = [f"share {share:.2f} at {c['level']} level{within}",
               f"{len(decisive)} decisive clue(s)" + (f" from {', '.join(dec_lineages)}" if dec_lineages else ""),
               f"{len(lineages)} independent lineage(s) with LR>=2" + (f": {', '.join(lineages)}" if lineages else "")]
    if against:
        reasons.append(f"{len(against)} unresolved strong contradiction(s): " + ", ".join(
            e["clue"] + ("" if x == cid else f" (against {x} {cands[x]['name']})") for x, e in against))
    if row["excluded"]:
        return {"tier": "none", "share": 0.0, "reasons": reasons + ["candidate is excluded"], "decisive": [],
                "lineages": lineages, "matched": [], "rival_control": False}
    # A reference match supports HIGH only with its control (a rival put through the same comparison), wherever
    # on the chain it is counted; without it the agreement may be a look-alike or a shared design.
    loose = [e for e in decisive if clues[e["clue"]]["status"] == "matched"
             and not case.match_controlled(e.get("via") or cid)]
    solid = [e for e in decisive if e not in loose]
    site = c["level"] in ("site", "room")
    two = len(dec_lineages) >= 2
    high_ok = two or (any(clues[e["clue"]]["status"] == "matched" for e in solid) if site else bool(solid))
    strong = bool(decisive) and len(lineages) >= 2 and share >= 0.8 and not against
    if strong and high_ok:
        tier = "high"
    elif (decisive or (len(lineages) >= 2 and not site)) and share >= 0.5:
        tier = "medium"
        if strong and loose:
            reasons.append(f"HIGH needs a rival control for the reference match ({', '.join(e['clue'] for e in loose)}): "
                           "put the closest alternative venue (same brand, same street, same style) through the same "
                           "comparison with `refs ... --for <its C#>`. A match that the rival's photos also produce "
                           "is a shared design, not this venue")
        elif strong:
            reasons.append("HIGH at site level needs a `matched` clue (reference imagery) with a rival control, or "
                           "decisive clues from two lineages (e.g. the name read in the photo and a reference match)")
    else:
        tier = "low"
        if site and not decisive and len(lineages) >= 2 and share >= 0.5:
            reasons.append("a venue needs a decisive clue (its name read on a crop, a decoded code, GPS metadata, or a "
                           "`matched` comparison with reference photos): resemblance, engine labels and captions make "
                           "a lead, however many of them agree")
    # A place is at least as certain as the best verified place inside it (its share is never smaller), unless
    # something contradicts the place itself.
    kids = [(done[k["id"]], k) for k in case.children(cid) if k["id"] in done and not case.is_excluded(k["id"])]
    if kids and not against:
        best, kid = max(kids, key=lambda t: (TIERS.index(t[0]["tier"]), t[0]["share"]))
        if TIERS.index(best["tier"]) > TIERS.index(tier):
            tier = best["tier"]
            reasons.append(f"at least as certain as {kid['id']} {kid['name']} inside it ({tier.upper()})")
    return {"tier": tier, "share": share, "reasons": reasons, "decisive": [e["clue"] for e in decisive],
            "lineages": lineages, "matched": [e["clue"] for e in matched], "rival_control": not loose}


def assess_all(case: Case) -> dict[str, dict]:
    """Confidence cap of every candidate, from one pass over the board (fine to coarse, so that a place can
    take the tier of a verified place inside it)."""
    b = board(case)
    done: dict[str, dict] = {}
    for level in reversed(LEVELS):
        for row in b.get(level, []):
            if not row.get("rest"):
                done[row["id"]] = _assess_row(case, row, done)
    return done


def assess(case: Case, cid: str, _all: dict[str, dict] | None = None) -> dict:
    """Confidence cap of one candidate with the reasons, from the structure of its evidence."""
    return (_all or assess_all(case))[cid]


def chain(case: Case, cid: str) -> list[dict]:
    """The candidate and its ancestors, coarse to fine, each with its assessment."""
    items = list(reversed(case.ancestors(cid))) + [case.data["candidates"][cid]]
    done = assess_all(case)
    return [{"id": c["id"], "name": c["name"], "level": c["level"], **done[c["id"]]} for c in items]


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
