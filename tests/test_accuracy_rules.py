"""Rules added in 1.1 against confident wrong answers: the open-world block at every level, the flow-up rule
(category clues do not inflate the enumerated city), answer gating with a separate lead, one-call
note+link, the new pre-report checks, and --print-url (offline)."""
from __future__ import annotations

import json
from pathlib import Path

from conftest import run
from iglib import scoring
from iglib.case import CORE_METHODS, Case


def note(case, text, kind="standard", status="observed", source="image", *extra):
    code, out = run("note", case, text, "--kind", kind, "--status", status, "--source", source, *extra)
    assert code == 0, out
    return out.split()[0]


def cand(case, name, level, *extra):
    code, out = run("cand", case, name, "--level", level, *extra)
    assert code == 0, out
    return out.split()[0]


def crop(case, cell="B2"):
    code, out = run("crop", case, "--cell", cell, "--label", "proof")
    assert code == 0, out
    return out.split()[0]


def share_of(case_dir, cid):
    case = Case(case_dir)
    level = case.data["candidates"][cid]["level"]
    return next(r["share"] for r in scoring.rank(case, level) if r["id"] == cid)


def row(case_dir, cid):
    case = Case(case_dir)
    return next(r for r in scoring.rank(case, case.data["candidates"][cid]["level"]) if r["id"] == cid)


def test_lone_candidate_is_not_certain_and_shares_are_coherent(case_dir: Path):
    at = cand(case_dir, "Austria", "country")
    vie = cand(case_dir, "Vienna", "city", "--parent", at, "--at", "48.2082,16.3738")
    r = row(case_dir, vie)
    assert abs(r["cond"] - 0.5) < 1e-9                            # vs the unlisted cities of Austria (prior 1)
    assert abs(r["share"] - 0.5 * row(case_dir, at)["share"]) < 1e-12
    rows = scoring.rank(Case(case_dir), "city")
    assert [x["id"] for x in rows if x.get("rest")] == [scoring.REST_ID]
    assert abs(sum(x["share"] for x in rows) - 1) < 1e-9
    e = crop(case_dir)
    ph = note(case_dir, "'+43 1 ...' read on the card; libphonenumber: AT, Vienna", "text", "computed", "text",
              "--file", e)
    run("link", case_dir, ph, "--for", f"{vie}:30", "--why", "area code 1 = Vienna")
    assert abs(row(case_dir, vie)["cond"] - 30 / 31) < 1e-9
    assert row(case_dir, vie)["share"] <= row(case_dir, at)["share"]          # never above its country
    # a decisive clue identifies: Austria is not diluted by the 249 countries nobody listed (2.0) ...
    assert abs(row(case_dir, at)["share"] - 30 / 31) < 1e-9
    a = scoring.assess(Case(case_dir), vie)
    assert a["tier"] == "medium" and a["lineages"] == ["text"]                # ... but one lineage is never HIGH
    lang = note(case_dir, "German on every notice", "language", "observed", "text")
    run("countries", "--lang", "de", "--case", case_dir, "--clue", lang)
    sock = note(case_dir, "Schuko socket (Type F)", "standard", "observed", "image")
    run("countries", "--plug", "F", "--case", case_dir, "--clue", sock)
    case = Case(case_dir)
    assert scoring.assess(case, at)["tier"] in ("medium", "high")
    assert scoring.assess(case, vie)["tier"] == "medium"


def test_category_clue_does_not_flow_up(case_dir: Path):
    de = cand(case_dir, "Germany", "country")
    ber = cand(case_dir, "Berlin", "city", "--parent", de)
    mun = cand(case_dir, "Munich", "city", "--parent", de)
    h1 = cand(case_dir, "Chain Hotel Berlin Mitte", "site", "--parent", ber)
    look = note(case_dir, "headboard and carpet of the chain's 2019 design package", "style", "observed", "image")
    run("link", case_dir, look, "--for", f"{h1}:6", "--why", "same design package")
    # enumerating the chain only in Berlin must not make Berlin more likely than Munich
    assert abs(share_of(case_dir, ber) - share_of(case_dir, mun)) < 1e-9
    e = crop(case_dir)
    name = note(case_dir, "'Mitte' printed on the key-card sleeve", "text", "read", "text", "--file", e)
    run("link", case_dir, name, "--for", f"{h1}:20", "--why", "branch name")
    assert share_of(case_dir, ber) > 5 * share_of(case_dir, mun)        # documentary evidence does flow up


def test_answer_gating_and_lead(case_dir: Path):
    gb = cand(case_dir, "United Kingdom", "country")
    lon = cand(case_dir, "London", "city", "--parent", gb, "--at", "51.5072,-0.1276")
    site = cand(case_dir, "Hotel Example", "site", "--parent", lon, "--at", "51.5101,-0.1340",
                "--falsify", "If Hotel Example: arched window pair on the bed wall")
    e = crop(case_dir)
    note(case_dir, "'+44 20 7946 0321' read on the tent card; libphonenumber: GB, London", "text", "computed",
         "text", "--file", e, "--for", f"{lon}:50", "--for", f"{gb}:50", "--why", "London area code")
    sock = note(case_dir, "BS 1363 switched socket", "standard", "observed", "image")
    run("countries", "--plug", "G", "--case", case_dir, "--clue", sock)
    gbp = note(case_dir, "'£14.50' read on the tent card", "text", "read", "text", "--file", e)
    run("countries", "--currency", "£", "--case", case_dir, "--clue", gbp, "--lr", "20")
    assert scoring.assess(Case(case_dir), lon)["tier"] == "medium"
    look = note(case_dir, "lamp looks like Hotel Example's", "style", "inferred", "image")
    run("link", case_dir, look, "--for", f"{site}:3", "--why", "style")
    code, out = run("answer", case_dir, site, "--no-network", "--summary", "x")
    assert code == 2                                                  # a LOW site under a MEDIUM city: refused
    code, out = run("answer", case_dir, lon, "--lead", site, "--no-network", "--summary", "phone + socket")
    assert code == 0 and "LEAD" in out, out
    ans = Case(case_dir).data["answer"]
    assert ans["level"] == "city" and ans["lead"]["candidate"] == site and ans["lead"]["tier"] == "low"
    for m in CORE_METHODS:
        run("log", case_dir, m, "--status", "not_applicable", "--detail", "test")
    code, out = run("finalize", case_dir)
    assert code == 0, out
    res = json.loads((case_dir / "result.json").read_text(encoding="utf-8"))
    assert res["answer"]["candidate"] == lon and res["lead"]["candidate"] == site
    assert 0 < res["unlisted_share"] < 0.3
    report = (case_dir / "REPORT.md").read_text(encoding="utf-8")
    assert "Best lead (unverified)" in report
    status = {c["id"]: c["status"] for lv in res["candidates"].values() for c in lv}     # every row says what it is
    assert (status[gb], status[lon], status[site]) == ("contains the answer", "answer", "lead (unverified)")
    assert set(status.values()) == {"contains the answer", "answer", "lead (unverified)", "open", "not on the board"}
    assert f"| {gb} | United Kingdom | " in report and "| contains the answer |" in report


def test_lead_must_be_finer(case_dir: Path):
    gb = cand(case_dir, "United Kingdom", "country")
    lon = cand(case_dir, "London", "city", "--parent", gb, "--at", "51.5072,-0.1276")
    code, _ = run("answer", case_dir, lon, "--lead", gb, "--no-network")
    assert code == 2


def test_note_links_in_one_call_and_validates_first(case_dir: Path):
    c = cand(case_dir, "Japan", "country")
    code, out = run("note", case_dir, "非常口 sign", "--kind", "text", "--status", "observed", "--source", "text",
                    "--for", f"{c}:6", "--why", "Japanese exit sign")
    assert code == 0 and "LR 6" in out
    n_before = len(Case(case_dir).data["clues"])
    code, _ = run("note", case_dir, "x", "--kind", "text", "--status", "observed", "--source", "text",
                  "--for", "C999:3", "--why", "bad id")
    assert code == 2 and len(Case(case_dir).data["clues"]) == n_before      # nothing written on error
    code, _ = run("note", case_dir, "x", "--kind", "text", "--status", "observed", "--source", "text",
                  "--for", f"{c}:3")
    assert code == 2                                                         # --why is required


def test_note_redacts_secrets(case_dir: Path):
    note(case_dir, "Wi-Fi card: WIFI:T:WPA;S:Guest-Net;P:hunter22;; on the desk", "code", "observed", "text")
    text = json.dumps(Case(case_dir).data["clues"], ensure_ascii=False)
    assert "hunter22" not in text and "Guest-Net" in text


def test_checks_flag_single_engine_and_lonely_site(case_dir: Path):
    at = cand(case_dir, "Austria", "country")
    vie = cand(case_dir, "Vienna", "city", "--parent", at)
    s1 = cand(case_dir, "Hotel A", "site", "--parent", vie, "--at", "48.2039,16.3696", "--address", "Ring 1")
    look = note(case_dir, "curtains", "style", "inferred", "image")
    run("link", case_dir, look, "--for", f"{s1}:3", "--why", "x")
    run("log", case_dir, "reverse_search", "--status", "no_results", "--engine", "yandex", "--detail", "x")
    run("answer", case_dir, s1, "--no-network")
    code, out = run("check", case_dir)
    assert "reverse search ran on 1 engine" in out
    assert "only one site on the board" in out
    assert "without a reference comparison" in out
    assert "no first-look hypotheses" in out


def test_print_url_sends_nothing(case_dir: Path):
    code, out = run("geo", "search", "Hotel Sacher Wien", "--print-url", "--case", case_dir, "--add", "site")
    assert code == 0 and "nominatim.openstreetmap.org/search?q=Hotel+Sacher+Wien" in out
    assert not Case(case_dir).data["candidates"]                             # nothing added in this mode
    code, out = run("geo", "poi", "--tag", "tourism=hotel", "--around", "48.2,16.37,500", "--print-url")
    assert code == 0 and "overpass-api.de/api/interpreter?data=" in out
    code, out = run("geo", "poi", "--tag", "tourism=hotel", "--area", "Vienna", "--print-url")
    assert code == 0 and "could not resolve area" in out                     # area needs a lookup first


def test_phone_fallback_without_phonenumbers(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "phonenumbers", None)          # import now fails: the fallback path runs
    from iglib.textmine import mine
    ph = mine(["Tel +43 1 234567", "call +44 20 7946 0321"])["phones"]
    assert ph[0]["country"] == "AT"
    assert ph[1]["country"] is None and "GB" in ph[1]["countries"] and "JE" in ph[1]["countries"]
