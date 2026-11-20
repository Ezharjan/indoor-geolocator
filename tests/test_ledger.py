"""The rules-as-code: status caps, exclusions, inherited support, confidence caps, the 'other countries'
block, the coverage gate, answer refusal and the tidy finalize."""
from __future__ import annotations

import json
from pathlib import Path

from conftest import make_jpeg, run
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


def test_init_creates_tidy_case(case_dir: Path):
    names = sorted(p.name for p in case_dir.iterdir())
    assert names == ["case.json", "evidence", "input"]
    assert (case_dir / "input" / "room.jpg").exists() and (case_dir / "input" / "metadata.json").exists()
    assert len(list((case_dir / "evidence").iterdir())) == 1                  # the grid view E01
    data = json.loads((case_dir / "case.json").read_text())
    assert data["schema"] == "igl.case/1"


def test_init_never_overwrites(tmp_path: Path, photo: Path, case_dir: Path):
    code, _ = run("init", photo, "--out", case_dir)
    assert code == 2


def test_status_caps_and_against(case_dir: Path):
    n = note(case_dir, "Type G socket")
    c = cand(case_dir, "United Kingdom", "country")
    code, out = run("link", case_dir, n, "--for", f"{c}:50", "--why", "test")
    assert "capped" in out and "LR 6" in out
    code, out = run("link", case_dir, n, "--against", f"{c}:100", "--why", "test")
    ev = Case(case_dir).data["evidence"]
    assert len(ev) == 1 and abs(ev[0]["lr"] - 1 / 6) < 1e-9                  # same clue+candidate: updated


def test_read_and_matched_need_a_file(case_dir: Path):
    code, _ = run("note", case_dir, "Hotel name on notepad", "--kind", "text", "--status", "read", "--source", "text")
    assert code == 2
    e = crop(case_dir)
    note(case_dir, "Hotel name on notepad", "text", "read", "text", "--file", e)


def test_exclusion_needs_decisive_status_and_file(case_dir: Path):
    weak = note(case_dir, "looks Nordic", "style", "inferred")
    c = cand(case_dir, "Norway", "country")
    code, _ = run("exclude", case_dir, c, "--by", weak, "--why", "x")
    assert code == 2
    e = crop(case_dir)
    strong = note(case_dir, "price in yen read on menu", "text", "read", "text", "--file", e)
    code, out = run("exclude", case_dir, c, "--by", strong, "--why", "yen prices", "--file", e)
    assert code == 0 and Case(case_dir).is_excluded(c)


def test_other_countries_block(case_dir: Path):
    n = note(case_dir, "Type B socket")
    code, out = run("countries", "--plug", "B", "--case", case_dir, "--clue", n)
    assert code == 0
    case = Case(case_dir)
    rows = scoring.rank(case, "country")
    rest = [r for r in rows if r.get("rest")]
    assert len(rest) == 1 and rest[0]["id"] == scoring.REST_ID
    listed = [r for r in rows if not r.get("rest")]
    assert abs(sum(r["share"] for r in rows) - 1) < 1e-9
    # 55-ish Type B countries x6 vs ~195 others x1: the block keeps a real share (omission != exclusion)
    assert 0.25 < rest[0]["share"] < 0.5
    assert len(listed) + int(rest[0]["name"].split("(")[1].split()[0]) == 250


def test_duplicate_country_refused(case_dir: Path):
    cand(case_dir, "Japan", "country")
    code, out = run("cand", case_dir, "Japan", "--level", "country")
    assert code == 2


def test_support_flows_up_and_site_rule(case_dir: Path):
    at = cand(case_dir, "Austria", "country")
    vie = cand(case_dir, "Vienna", "city", "--parent", at, "--at", "48.2082,16.3738")
    s1 = cand(case_dir, "Hotel A", "site", "--parent", vie, "--at", "48.2039,16.3696")
    s2 = cand(case_dir, "Hotel B", "site", "--parent", vie, "--at", "48.2100,16.3700")
    e = crop(case_dir)
    name = note(case_dir, "'Hotel A' printed on the key-card sleeve", "text", "read", "text", "--file", e)
    run("link", case_dir, name, "--for", f"{s1}:40", "--why", "name read")
    sock = note(case_dir, "Type F socket", "standard", "observed", "image")
    run("link", case_dir, sock, "--for", f"{at}:6", "--why", "Schuko")
    case = Case(case_dir)
    # the site's clue supports its city and country (inherited, counted once)
    vie_row = next(r for r in scoring.rank(case, "city") if r["id"] == vie)
    assert any(e["clue"] == name and e.get("via") == s1 for e in vie_row["ev"])
    a = scoring.assess(case, s1)
    # decisive text but only one lineage at site level and no reference match: not HIGH
    assert a["tier"] in ("medium", "low") and a["tier"] != "high"
    # add an independent reference match -> HIGH becomes possible
    e2 = crop(case_dir, "C3")
    m = note(case_dir, "3 invariant features match a traveller photo", "match", "matched", "reference", "--file", e2)
    run("link", case_dir, m, "--for", f"{s1}:80", "--why", "match")
    case = Case(case_dir)
    assert scoring.assess(case, s1)["tier"] == "high"
    assert scoring.assess(case, s2)["tier"] == "low"


def test_answer_refuses_above_cap_and_check_gate(case_dir: Path):
    at = cand(case_dir, "Austria", "country")
    vie = cand(case_dir, "Vienna", "city", "--parent", at, "--at", "48.2082,16.3738")
    s1 = cand(case_dir, "Hotel A", "site", "--parent", vie, "--at", "48.2039,16.3696", "--address", "Ring 1, Wien")
    weak = note(case_dir, "carpet looks like Hotel A's", "style", "inferred")
    run("link", case_dir, weak, "--for", f"{s1}:3", "--why", "style")
    code, out = run("answer", case_dir, s1, "--confidence", "high", "--no-network")
    assert code == 2
    code, out = run("answer", case_dir, s1, "--no-network", "--summary", "weak")
    assert code == 0
    code, out = run("check", case_dir)
    assert code == 1 and "core method" in out                                   # coverage gate
    for m in CORE_METHODS:
        run("log", case_dir, m, "--status", "not_applicable", "--detail", "test")
    code, out = run("check", case_dir)
    assert "FAIL" not in out


def test_log_requires_reason_for_non_results(case_dir: Path):
    code, _ = run("log", case_dir, "reverse_search", "--status", "blocked")
    assert code == 2
    code, _ = run("log", case_dir, "reverse_search", "--status", "blocked", "--engine", "lens", "--detail", "captcha")
    assert code == 0


def test_finalize_is_tidy(case_dir: Path):
    keep = crop(case_dir, "B2")
    drop = crop(case_dir, "C3")
    n = note(case_dir, "socket", "standard", "observed", "image", "--file", keep)
    c = cand(case_dir, "Austria", "country")
    run("link", case_dir, n, "--for", f"{c}:6", "--why", "x")
    run("answer", case_dir, c, "--no-network", "--summary", "test")
    for m in CORE_METHODS:
        run("log", case_dir, m, "--status", "not_applicable", "--detail", "test")
    (case_dir / ".work" / "cache").mkdir(parents=True, exist_ok=True)
    (case_dir / "evidence" / "stray.tmp").write_text("orphan")
    code, out = run("finalize", case_dir)
    assert code == 0, out
    names = sorted(p.name for p in case_dir.iterdir())
    assert names == ["REPORT.md", "case.json", "evidence", "input", "result.json"]
    ev = sorted(p.name for p in (case_dir / "evidence").iterdir())
    data = json.loads((case_dir / "case.json").read_text())
    assert drop not in data["files"] and keep in data["files"]
    assert not any(n.startswith(drop) for n in ev) and "stray.tmp" not in ev
    res = json.loads((case_dir / "result.json").read_text())
    assert res["schema"] == "igl.result/1" and res["answer"]["candidate"] == c
    report = (case_dir / "REPORT.md").read_text()
    for section in ("## Confidence by level", "## Evidence", "## Candidates considered", "## Methods attempted",
                    "## Data handling", "## Files"):
        assert section in report


def test_gps_metadata_auto_clue_and_signs(tmp_path: Path):
    p = make_jpeg(tmp_path / "rio.jpg", lat=-22.9068, lon=-43.1729, when="2024:07:10 16:00:00", offset="-03:00")
    out_dir = tmp_path / "c"
    code, out = run("init", p, "--out", out_dir)
    assert code == 0
    meta = json.loads((out_dir / "input" / "metadata.json").read_text())
    assert abs(meta["gps"]["lat"] + 22.9068) < 1e-4 and abs(meta["gps"]["lon"] + 43.1729) < 1e-4
    assert meta["time"]["offset"] == "-03:00"
    assert any(z.startswith("America/Sao_Paulo") for z in meta["time"]["zones_with_offset"])
    clues = json.loads((out_dir / "case.json").read_text())["clues"]
    assert any(c["status"] == "metadata" and "EXIF GPS -22.906" in c["text"] for c in clues.values())
