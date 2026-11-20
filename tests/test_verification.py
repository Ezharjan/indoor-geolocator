"""Rules and tools added in 2.0 against the commonest wrong answer - a look-alike venue named with
confidence: the OCR precision filter, engine hits and reference photos classified against the photo
itself (`revsearch` triage, `refs`, `compare`), auditable `matched` clues, the site-level gate, the cap on
engine leads, and the fallbacks for services that refuse cloud networks. Offline: synthetic images, fake
HTTP, no browser."""
from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest
from conftest import run
from PIL import Image

from iglib import embed, geo, match, net, ocr, refs, revsearch, scoring
from iglib.case import Case

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from test_match_share import new_view, scene  # noqa: E402


def note(case, text, kind="standard", status="observed", source="image", *extra):
    code, out = run("note", case, text, "--kind", kind, "--status", status, "--source", source, *extra)
    assert code == 0, out
    return out.split()[0]


def cand(case, name, level, *extra):
    code, out = run("cand", case, name, "--level", level, *extra)
    assert code == 0, out
    return out.split()[0]


@pytest.fixture
def room_case(tmp_path: Path) -> tuple[Path, Image.Image]:
    """A case whose photo has texture (the default fixture photo is one flat colour)."""
    im = scene(11)
    im.save(tmp_path / "room.jpg", quality=92)
    out = tmp_path / "case"
    code, _ = run("init", tmp_path / "room.jpg", "--out", out, "--no-probe")
    assert code == 0
    return out, im


# ----------------------------------------------------------------------------- OCR precision
@pytest.mark.parametrize("text,conf,agree,keep", [
    ("THE LARKSPUR", 0.9, 1, True), ("Reception +44 20 7946 0321", 0.6, 1, True), ("£14.50 per person incl. VAT", 0.55, 1, True),
    ("Guest Wi-Fi", 0.8, 1, True), ("EXIT", 0.8, 2, True), ("EXIT", 0.8, 1, False), ("安全出口", 0.9, 1, True),
    ("非常口", 0.86, 1, True), ("Выход", 0.86, 1, True), ("ทางออกฉุกเฉิน", 0.7, 2, True),
    # what a carpet, a curtain and an ornamented ceiling become: stray letters, never words
    ("โร ร า ร ร า ร ร า ว ๆ ร ร า", 0.81, 1, False), ("๓ ๓ 2", 0.95, 1, False), ("โร ๊ ร า ชรา ร ร า ร", 0.70, 1, False),
    ("li", 0.67, 3, False), ("ANY +", 0.49, 2, False), ("NEN", 0.80, 1, False), ("Wr @ ๑ 9", 0.62, 1, False),
    ("4 ify", 0.77, 1, False), ("UY", 0.56, 2, False), ("ด ม ATP", 0.71, 1, False),
])
def test_ocr_precision_filter(text, conf, agree, keep):
    assert ocr.plausible(text, conf, agree) is keep, ocr.text_quality(text)


def test_ocr_merges_cut_off_readings_of_one_line():
    raw = [{"text": "Reception +44 20 7946 0321", "conf": 0.96, "box": [573, 819, 906, 842], "pass": "full"},
           {"text": "Reception +44 20 7946 C", "conf": 0.94, "box": [574, 819, 863, 842], "pass": "tile"},    # tile border
           {"text": "THE LARKSP", "conf": 0.95, "box": [537, 608, 863, 644], "pass": "tile"},
           {"text": "THE LARKSPUR", "conf": 0.91, "box": [536, 608, 944, 664], "pass": "full"},
           {"text": "RKSPUR", "conf": 0.93, "box": [735, 608, 943, 644], "pass": "tile"},                     # the other half
           {"text": "£14.50 per person incl. VAT", "conf": 0.96, "box": [583, 780, 896, 804], "pass": "full"},
           {"text": "2rson incl. VAT", "conf": 0.90, "box": [735, 780, 896, 799], "pass": "tile"},            # cut at the start
           {"text": "Reception", "conf": 0.9, "box": [100, 100, 200, 120], "pass": "full"},                   # elsewhere
           {"text": "..", "conf": 0.99, "box": [0, 0, 5, 5], "pass": "full"}]
    lines = ocr.merge(raw)
    assert sorted(m["text"] for m in lines) == ["Reception", "Reception +44 20 7946 0321", "THE LARKSPUR",
                                                "£14.50 per person incl. VAT"]
    phone = next(m for m in lines if "0321" in m["text"])
    assert phone["passes"] == {"full", "tile"} and phone["conf"] == 0.96
    name = next(m for m in lines if m["text"] == "THE LARKSPUR")
    assert name["box"] == [536, 608, 944, 664] and name["conf"] == 0.95     # the fuller reading, the better score


def test_text_quality_reads_scripts_by_runs():
    q = ocr.text_quality("ทางออกฉุกเฉิน")
    assert q["script"] == "THAI" and q["script_run"] >= 8 and q["coverage"] == 1.0
    noise = ocr.text_quality("ร า ร ร า ๆ ๆ ร")
    assert noise["words"] == 0                                   # single letters are not a script signal
    assert ocr.text_quality("www.example-hotel.co.uk")["strong"]
    assert ocr.char_script("ก") == "THAI" and ocr.char_script("7") is None


# ----------------------------------------------------------------------------- the ledger's new rules
def test_matched_refuses_a_copy_of_the_photo(room_case):
    case_dir, im = room_case
    im.resize((450, 300)).save(case_dir.parent / "repost.jpg", quality=80)
    code, out = run("compare", case_dir, "--ref", case_dir.parent / "repost.jpg")
    assert code == 0 and "NEAR-DUPLICATE" in out
    sheet = out.split()[0]
    code, _ = run("note", case_dir, "same room", "--kind", "match", "--status", "matched", "--source", "reference",
                  "--file", sheet, "--features", "window pair; ceiling beams; fireplace")
    assert code == 2                                             # a copy is provenance, never a match
    assert not any(c["status"] == "matched" for c in Case(case_dir).data["clues"].values())


def test_matched_accepts_a_browser_comparison_with_url_and_features(case_dir: Path):
    code, out = run("note", case_dir, "Matches the lobby in the venue's maps photos", "--kind", "match",
                    "--status", "matched", "--source", "reference", "--url", "https://maps.example/place/photo/1",
                    "--features", "three arched windows; black-and-white chequered floor; double staircase")
    assert code == 0, out
    clue = next(iter(Case(case_dir).data["clues"].values()))
    assert len(clue["features"]) == 3
    code, _ = run("note", case_dir, "looks the same", "--kind", "match", "--status", "matched", "--source",
                  "reference", "--url", "https://maps.example/place", "--features", "same style; similar chairs")
    assert code == 2                                             # two vague "features" are not three specific ones


def test_site_needs_a_decisive_clue_and_engine_leads_are_capped(case_dir: Path):
    gb = cand(case_dir, "United Kingdom", "country")
    ayr = cand(case_dir, "Ayr", "city", "--parent", gb)
    site = cand(case_dir, "Look-alike House Hotel", "site", "--parent", ayr)
    code, out = run("crop", case_dir, "--cell", "B2", "--label", "leaflet")
    note(case_dir, "'01292' dialling code read on a taxi leaflet; lookup: Ayr, GB", "text", "computed", "text",
         "--file", out.split()[0], "--for", f"{gb}:50", "--for", f"{ayr}:50", "--why", "area code")   # the town IS verified
    code, out = run("note", case_dir, "Yandex lists this hotel's lounge among the similar images", "--kind", "provenance",
                    "--status", "reported", "--source", "engine", "--for", f"{site}:10", "--why", "engine hit")
    assert code == 0 and "LR 3" in out and "capped" in out       # an engine title is a lead (cap 3), not LR 10
    note(case_dir, "wood panelling and tufted armchairs like the hotel's gallery", "style", "observed", "image",
         "--for", f"{site}:6", "--why", "resemblance")
    note(case_dir, "a booking page describes a panelled lounge", "context", "reported", "web",
         "--for", f"{site}:10", "--why", "caption")
    a = scoring.assess(Case(case_dir), site)
    assert len(a["lineages"]) >= 2 and a["share"] > 0.5
    assert a["tier"] == "low" and any("decisive clue" in r for r in a["reasons"])
    code, out = run("answer", case_dir, site, "--confidence", "medium", "--no-network")
    assert code == 2                                             # resemblance + captions never name a venue


def test_log_takes_a_comma_list_and_clues_imply_methods(case_dir: Path):
    code, out = run("log", case_dir, "visual_sweep,text_search,social_search", "--status", "results", "--detail", "x")
    assert code == 0 and out.count("results") == 3
    code, _ = run("log", case_dir, "visual_sweep,nonsense", "--status", "results")
    assert code == 2
    note(case_dir, "Type G double socket", "standard", "observed", "image")
    note(case_dir, "harbour seen through the window", "window-view", "observed", "image")
    state = Case(case_dir).method_state()
    assert state["standards"]["status"] == "results" and state["standards"].get("implied")
    assert state["window_view"]["status"] == "results" and "culture_style" not in state


def test_check_flags_missing_rival_and_searches_that_never_ran(room_case):
    case_dir, im = room_case
    gb = cand(case_dir, "United Kingdom", "country")
    poole = cand(case_dir, "Poole", "city", "--parent", gb)
    s1 = cand(case_dir, "Hotel One", "site", "--parent", poole, "--at", "50.68,-1.95", "--address", "Banks Road")
    cand(case_dir, "Hotel Two", "site", "--parent", poole)
    new_view(im).save(case_dir.parent / "ref.jpg", quality=90)
    code, out = run("refs", case_dir, "--image", case_dir.parent / "ref.jpg", "--for", s1)
    assert code == 0 and "SAME SCENE" in out, out
    run("log", case_dir, "reverse_search", "--status", "blocked", "--engine", "yandex", "--detail", "captcha")
    run("answer", case_dir, s1, "--no-network")
    _, out = run("check", case_dir)
    assert "no rival was put through the same comparison" in out
    assert "reverse image search never actually ran" in out


# ----------------------------------------------------------------------------- decisive clues and the field
def _match(case_dir: Path, im: Image.Image, site: str, lr: int = 80, name: str = "ref.jpg") -> str:
    """A `matched` clue for a venue, with its comparison on file."""
    new_view(im).save(case_dir.parent / name, quality=90)
    code, out = run("compare", case_dir, "--ref", case_dir.parent / name, "--for", site)
    assert code == 0, out
    return note(case_dir, "Matches a visitor's photo of the bar", "match", "matched", "reference", "--file",
                out.split()[0], "--features", "snake sculpture across the ceiling; aquarium wall behind the bar; "
                "curved copper bar front", "--for", f"{site}:{lr}", "--why", "three one-of-a-kind fixed features")


def test_a_verified_venue_carries_its_chain_and_listed_rivals_do_not_dilute_it(room_case):
    """Regression: one verified venue and nothing else on the board ended LOW, because the 249 countries
    nobody had listed outweighed a single LR 80."""
    case_dir, im = room_case
    us = cand(case_dir, "United States", "country")
    taos = cand(case_dir, "Taos", "city", "--parent", us)
    bar = cand(case_dir, "Anaconda Bar", "site", "--parent", taos, "--at", "36.4034,-105.5665")
    _match(case_dir, im, bar)
    done = scoring.assess_all(Case(case_dir))
    for cid in (us, taos, bar):
        assert done[cid]["share"] > 0.95 and done[cid]["tier"] == "medium", (cid, done[cid])   # one lineage: "probably"
    assert abs(done[us]["share"] - 80 / 81) < 1e-9               # LR 80 = 80:1 against the whole field
    rivals = [cand(case_dir, f"Bar {i}", "site", "--parent", taos) for i in range(30)]
    cand(case_dir, "Mexico", "country")
    done = scoring.assess_all(Case(case_dir))
    assert done[bar]["share"] > 0.95                             # enumerating the category costs nothing
    assert done[rivals[0]]["share"] < 0.001
    _, out = run("rank", case_dir, "--level", "site")
    assert "x80*" in out and "weighed against the whole field" in out


def test_category_clues_still_compete_with_every_unlisted_country(case_dir: Path):
    gb = cand(case_dir, "United Kingdom", "country")
    note(case_dir, "BS 1363 socket", "standard", "observed", "image", "--for", f"{gb}:6", "--why", "Type G")
    r = next(x for x in scoring.rank(Case(case_dir), "country") if x["id"] == gb)
    assert abs(r["share"] - 6 / (6 + 249)) < 1e-9 and not r["identified"]
    code, out = run("crop", case_dir, "--cell", "B2", "--label", "sign")
    weak = note(case_dir, "'WAY OUT' read on the sign", "language", "read", "text", "--file", out.split()[0],
                "--for", f"{gb}:6", "--why", "British wording")
    r = next(x for x in scoring.rank(Case(case_dir), "country") if x["id"] == gb)
    assert abs(r["share"] - 36 / (36 + 249)) < 1e-9             # a `read` clue below LR 10 narrows, it does not identify
    run("link", case_dir, weak, "--for", f"{gb}:20", "--why", "now claimed as identifying")
    r = next(x for x in scoring.rank(Case(case_dir), "country") if x["id"] == gb)
    assert r["identified"] and abs(r["share"] - 120 / 121) < 1e-9


def test_site_high_needs_a_rival_control_or_a_second_decisive_lineage(room_case):
    case_dir, im = room_case
    us = cand(case_dir, "United States", "country")
    taos = cand(case_dir, "Taos", "city", "--parent", us)
    bar = cand(case_dir, "Anaconda Bar", "site", "--parent", taos)
    rival = cand(case_dir, "Adobe Bar", "site", "--parent", taos)
    _match(case_dir, im, bar)
    note(case_dir, "adobe walls and vigas, as in the listing text", "architecture", "observed", "image",
         "--for", f"{bar}:3", "--why", "fits the venue's description")
    a = scoring.assess(Case(case_dir), bar)
    assert a["tier"] == "medium" and not a["rival_control"] and any("rival control" in r for r in a["reasons"])
    code, _ = run("answer", case_dir, bar, "--confidence", "high", "--no-network")
    assert code == 2
    scene(99).save(case_dir.parent / "rival.jpg", quality=90)   # the rival's photos show another room
    code, out = run("compare", case_dir, "--ref", case_dir.parent / "rival.jpg", "--for", rival)
    assert code == 0, out
    done = scoring.assess_all(Case(case_dir))
    assert done[bar]["tier"] == "high" and done[bar]["rival_control"]
    # the town and the country are at least as certain as the verified venue inside them
    assert done[taos]["tier"] == "high" and done[us]["tier"] == "high"
    assert any("at least as certain as" in r for r in done[us]["reasons"])
    assert done[rival]["tier"] == "low"


def test_a_contradiction_against_the_country_blocks_high_inside_it(room_case):
    case_dir, im = room_case
    us = cand(case_dir, "United States", "country")
    taos = cand(case_dir, "Taos", "city", "--parent", us)
    bar = cand(case_dir, "Anaconda Bar", "site", "--parent", taos)
    rival = cand(case_dir, "Adobe Bar", "site", "--parent", taos)
    _match(case_dir, im, bar)
    scene(99).save(case_dir.parent / "rival.jpg", quality=90)
    run("compare", case_dir, "--ref", case_dir.parent / "rival.jpg", "--for", rival)
    code, out = run("crop", case_dir, "--cell", "B2", "--label", "name")
    note(case_dir, "'ANACONDA BAR' read on the menu", "text", "read", "text", "--file", out.split()[0],
         "--for", f"{bar}:40", "--why", "name on the menu")
    assert scoring.assess(Case(case_dir), bar)["tier"] == "high"
    code, out = run("crop", case_dir, "--cell", "C3", "--label", "socket")
    odd = note(case_dir, "Type G socket read on the crop: not a US standard", "contradiction", "read", "image",
               "--file", out.split()[0], "--against", f"{us}:5", "--why", "wrong socket for the country")
    done = scoring.assess_all(Case(case_dir))
    assert done[bar]["tier"] == "medium" and done[us]["tier"] == "medium"       # blocked on the whole chain
    assert any(odd in r and "against" in r for r in done[bar]["reasons"])
    code, out = run("crop", case_dir, "--cell", "C3", "--label", "adapter")
    note(case_dir, "the socket is a travel adapter plugged into a NEMA outlet", "context", "read", "image",
         "--file", out.split()[0], "--resolves", odd)
    assert scoring.assess(Case(case_dir), bar)["tier"] == "high"


def test_traced_is_a_copy_on_a_page_that_names_the_place(room_case):
    """Provenance: the same photograph on the venue's own page identifies the venue ("probably"); with one
    independent photo that matches, it is verified."""
    case_dir, im = room_case
    d = case_dir.parent
    gb = cand(case_dir, "United Kingdom", "country")
    town = cand(case_dir, "Poole", "city", "--parent", gb)
    hotel = cand(case_dir, "Hotel One", "site", "--parent", town)
    args = ("note", case_dir, "Same photograph in the gallery of the hotel's own site, captioned 'Lounge'", "--kind",
            "provenance", "--status", "traced", "--source", "web")
    code, _ = run(*args, "--for", f"{hotel}:15", "--why", "the venue's own page")
    assert code == 2                                             # no page given
    scene(99).save(d / "similar.jpg", quality=90)
    _, out = run("refs", case_dir, "--image", d / "similar.jpg")
    code, _ = run(*args, "--url", "https://hotel-one.example/gallery", "--file", out.split("sheet 1: ")[1].split()[0])
    assert code == 2                                             # a similar picture is not a trace
    im.resize((600, 400)).save(d / "copy.jpg", quality=80)
    _, out = run("refs", case_dir, "--image", d / "copy.jpg", "--for", hotel)
    assert "--status traced" in out
    sheet = out.split("sheet 1: ")[1].split()[0]
    assert Case(case_dir).data["files"][sheet]["meta"]["classes"] == ["copy"]
    code, out = run(*args, "--url", "https://hotel-one.example/gallery", "--file", sheet, "--for", f"{hotel}:50",
                    "--why", "the venue's own page")
    assert code == 0 and "LR 20" in out and "capped" in out, out
    done = scoring.assess_all(Case(case_dir))
    assert done[hotel]["tier"] == "medium" and done[hotel]["share"] > 0.85      # one lineage: "probably"
    assert done[gb]["tier"] == "medium"
    code, _ = run("note", case_dir, "same room", "--kind", "match", "--status", "matched", "--source", "reference",
                  "--file", sheet, "--features", "window pair; ceiling beams; fireplace")
    assert code == 2                                             # the copy cannot also confirm itself
    _match(case_dir, im, hotel, lr=60, name="another-angle.jpg")
    done = scoring.assess_all(Case(case_dir))
    assert done[hotel]["tier"] == "high" and sorted(done[hotel]["lineages"]) == ["reference", "web"]


def test_a_browser_only_trace_is_accepted_with_a_caution(case_dir: Path):
    site = cand(case_dir, "Cafe X", "site")
    code, out = run("note", case_dir, "Lens shows the same photograph on the cafe's listing", "--kind", "provenance",
                    "--status", "traced", "--source", "web", "--url", "https://maps.example/cafe-x", "--for",
                    f"{site}:12", "--why", "listing of the venue")
    assert code == 0 and "no COPY on file" in out
    code, out = run("note", case_dir, "An AI engine names the cafe", "--kind", "provenance", "--status", "traced",
                    "--source", "engine", "--url", "https://engine.example/r/1", "--for", f"{site}:12", "--why", "x")
    assert code == 0 and "LR 3" in out                           # an engine's say-so stays a lead under any status


def test_design_match_answers_at_the_area_with_the_venue_as_lead_and_pin(room_case):
    """Two sister hotels show the same furniture: the match is recorded for their district, the likelier
    hotel is the lead, and its coordinates are the pin (the single most likely point)."""
    case_dir, im = room_case
    d = case_dir.parent
    gb = cand(case_dir, "United Kingdom", "country")
    town = cand(case_dir, "Poole", "city", "--parent", gb, "--at", "50.7151,-1.9872")
    area = cand(case_dir, "Sandbanks peninsula", "district", "--parent", town, "--at", "50.6885,-1.9390")
    h1 = cand(case_dir, "Hotel One", "site", "--parent", area, "--at", "50.6946,-1.9306",
              "--falsify", "If Hotel One: a panelled first-floor lounge")
    h2 = cand(case_dir, "Hotel Two", "site", "--parent", area, "--at", "50.6820,-1.9480")
    new_view(im).save(d / "one.jpg", quality=90)
    _, out = run("compare", case_dir, "--ref", d / "one.jpg", "--for", h1)
    sheet = out.split()[0]
    args = ("note", case_dir, "Design match: the group's armchairs and cliff paintings", "--kind", "match", "--status",
            "matched", "--source", "reference", "--file", sheet, "--features",
            "button-tufted armchair with turned legs; glass-top oak coffee table; chalk-cliff painting series",
            "--for", f"{area}:40", "--why", "the group's furnishing")
    code, out = run(*args)
    assert code == 0, out
    run("answer", case_dir, area, "--no-network", "--summary", "x")
    _, out = run("check", case_dir)
    assert "design match" in out and "at least two venues" in out          # only one venue's photos are on file
    scene(98).save(d / "two.jpg", quality=90)
    run("compare", case_dir, "--ref", d / "two.jpg", "--for", h2)
    note(case_dir, "the lounge bar of Hotel One shows the same chairs", "match", "observed", "reference",
         "--for", f"{h1}:4", "--why", "one feature")
    code, _ = run("answer", case_dir, h1, "--no-network")
    assert code == 2                                             # a LOW venue under a verified district is a lead
    code, out = run("answer", case_dir, area, "--lead", h1, "--no-network", "--summary", "group furnishing")
    assert code == 0 and "PIN     50.6946, -1.9306" in out and "unverified lead" in out, out
    _, out = run("check", case_dir)
    assert "design match" not in out
    for m in ("visual_sweep", "text_ocr", "codes", "standards", "culture_style", "reverse_search", "text_search",
              "social_search", "candidate_enum", "window_view", "consistency"):
        run("log", case_dir, m, "--status", "not_applicable", "--detail", "test")
    code, out = run("finalize", case_dir)
    assert code == 0, out
    res = json.loads((case_dir / "result.json").read_text(encoding="utf-8"))
    assert res["answer"]["candidate"] == area and res["answer"]["level"] == "district"
    assert res["best_estimate"]["basis"] == "lead" and res["best_estimate"]["candidate"] == h1
    assert res["best_estimate"]["verified_level"] == "district" and res["best_estimate"]["lat"] == 50.6946
    assert {v["candidate"] for v in res["verification"]} == {h1, h2, area}
    assert [r["candidate"] for r in res["rival_control"]] == [h2]
    report = (case_dir / "REPORT.md").read_text(encoding="utf-8")
    assert "Best-estimate pin" in report and "Rival control for Hotel One" in report and "design match" in report
    # the candidate tables: the lead is marked, and the unlisted block has its own line (it is not a candidate)
    assert {c["id"]: c["status"] for c in res["candidates"]["site"]}[h1] == "lead (unverified)"
    assert f"| {h1} | Hotel One |" in report and "| lead (unverified) |" in report
    assert "| C* | unlisted alternatives (any site not on the board) |" in report and "more candidate(s)" not in report
    assert "| C* | other countries (249 not on the board) | 0.02 | not on the board | |" in report


def test_a_matched_venue_whose_rival_matches_too_is_flagged(room_case):
    case_dir, im = room_case
    d = case_dir.parent
    town = cand(case_dir, "Poole", "city")
    h1 = cand(case_dir, "Hotel One", "site", "--parent", town, "--at", "50.69,-1.93", "--falsify", "x")
    h2 = cand(case_dir, "Hotel Two", "site", "--parent", town)
    _match(case_dir, im, h1)
    new_view(im).save(d / "rival.jpg", quality=90)               # the rival's photo shows the same structure
    run("compare", case_dir, "--ref", d / "rival.jpg", "--for", h2)
    run("answer", case_dir, h1, "--no-network")
    _, out = run("check", case_dir)
    assert "were classed SAME SCENE too" in out and "shared design" in out


def test_crop_of_a_reference_and_interleaved_sources(room_case):
    case_dir, im = room_case
    scene(99).save(case_dir.parent / "ref.jpg", quality=90)
    _, out = run("refs", case_dir, "--image", case_dir.parent / "ref.jpg")
    sheet = out.split("sheet 1: ")[1].split()[0]
    code, out = run("crop", case_dir, "--of", sheet, "--rel", "0.25,0,0.5,0.5", "--label", "ref-detail")
    assert code == 0 and f"of {sheet}" in Case(case_dir).data["files"][out.split()[0]]["what"]
    code, _ = run("crop", case_dir, "--of", sheet, "--cell", "B2")
    assert code == 2                                             # the grid belongs to the case photo
    items = [{"provider": "brave", "query": "a", "image": f"a{i}"} for i in range(3)] + \
            [{"provider": "startpage", "query": "a", "image": f"b{i}"} for i in range(2)] + \
            [{"provider": "page", "from_page": "p", "image": "c0"}]
    assert [it["image"] for it in refs.interleave(items)] == ["a0", "b0", "c0", "a1", "b1", "a2"]


# ----------------------------------------------------------------------------- refs / compare / ranking
def test_refs_classifies_ranks_and_records(room_case):
    case_dir, im = room_case
    d = case_dir.parent
    scene(99).save(d / "other.jpg", quality=90)                  # an unrelated room
    new_view(im).save(d / "again.jpg", quality=90)               # the same room from another viewpoint
    im.resize((600, 400)).save(d / "copy.jpg", quality=80)       # the photo itself, re-posted
    site = cand(case_dir, "Hotel A", "site")
    code, out = run("refs", case_dir, "--image", d / "other.jpg", "--image", d / "again.jpg", "--image", d / "copy.jpg",
                    "--for", site, "--label", "hotel-a")
    assert code == 0, out
    case = Case(case_dir)
    jid = next(e for e, f in case.data["files"].items() if f.get("tool") == "refs" and f["path"].endswith(".json"))
    data = json.loads(case.file_path(jid).read_text(encoding="utf-8"))
    assert [it["cls"] for it in data["items"]] == ["copy", "same", "none"]          # best first
    assert data["counts"] == {"copy": 1, "same": 1, "none": 1}
    sheets = [e for e, f in case.data["files"].items() if f.get("tool") == "refs" and f["path"].endswith(".jpg")]
    assert sheets and case.file_path(sheets[0]).stat().st_size > 5000
    assert case.data["files"][sheets[0]]["meta"]["json"] == jid
    rec = case.data["candidates"][site]["refs"][0]
    assert rec["compared"] == 3 and rec["best"]["cls"] == "copy"
    att = [a for a in case.data["attempts"] if a["method"] == "reference_match"]
    assert att and att[-1]["status"] == "results" and "Hotel A" in att[-1]["detail"]
    assert "provenance" in out and "compare" in out
    same_n = next(it["n"] for it in data["items"] if it["cls"] == "same")
    code, out = run("compare", case_dir, "--refs", jid, "--pick", same_n, "--for", site)
    assert code == 0 and "STRONG geometric agreement" in out, out
    sheet = out.split()[0]
    m = note(case_dir, "Matches a second photo of the room", "match", "matched", "reference", "--file", sheet,
             "--features", "red rectangle top left; white circle pair; diagonal blue line", "--for", f"{site}:60",
             "--why", "three features and strong geometry")
    assert Case(case_dir).data["clues"][m]["features"]
    code, _ = run("compare", case_dir, "--refs", jid, "--pick", "77")
    assert code == 2                                             # unknown item number


def test_unconfirmed_items_keep_the_source_order(tmp_path: Path):
    q = scene(5)
    paths = []
    for k, seed in enumerate((41, 42, 43)):
        scene(seed).save(tmp_path / f"r{k}.jpg", quality=88)
        paths.append({"file": str(tmp_path / f"r{k}.jpg"), "title": f"hit {k}", "site": "example.org"})
    new_view(q).save(tmp_path / "same.jpg", quality=90)
    items = paths + [{"file": str(tmp_path / "same.jpg"), "title": "the room again", "site": "example.org"}]
    counts = refs.rank_against(q, items, tmp_path / "work", http=None, start=10)
    assert counts == {"same": 1, "none": 3}
    assert [it["n"] for it in items] == [13, 10, 11, 12]         # the match first, the rest as the source gave them
    assert items[0]["spread"] > 0.2
    sheets = refs.ranked_sheets(q, items)
    assert len(sheets) == 1 and sheets[0].width == 4 * 384
    assert "judge by eye" in refs.summary_line(counts)


def test_unconfirmed_items_are_ordered_by_similarity_when_the_model_ran(tmp_path: Path, monkeypatch):
    """The similarity model orders what the feature test left open; it never changes a class."""
    q = scene(5)
    items = []
    for k, seed in enumerate((41, 42, 43, 44)):
        scene(seed).save(tmp_path / f"r{k}.jpg", quality=88)
        items.append({"file": str(tmp_path / f"r{k}.jpg"), "title": f"hit {k}", "site": "example.org"})
    new_view(q).save(tmp_path / "same.jpg", quality=90)
    items.append({"file": str(tmp_path / "same.jpg"), "title": "the room again", "site": "example.org"})
    monkeypatch.setattr(embed, "similarities", lambda q_, ims, http=None: [0.31, 0.74, None, 0.52, 0.9][:len(ims)])
    counts = refs.rank_against(q, items, tmp_path / "work", http=None, start=1)
    assert counts == {"same": 1, "none": 4}
    assert [it["n"] for it in items] == [5, 2, 4, 1, 3]         # the confirmed one, then most similar first
    assert items[1]["sim"] == 0.74 and "sim" not in items[4] and refs.by_similarity(items)
    assert all(it["cls"] == "none" for it in items[1:])
    from iglib.visual import _hit_line
    assert "0.74" in _hit_line(items[1]) and "0.90" not in _hit_line(items[0])


def test_similarity_model_is_optional_verified_and_never_classifies(tmp_path: Path, monkeypatch):
    a = np.eye(4, dtype=np.float32)
    assert abs(embed.patch_score(a, a) - 1.0) < 1e-6 and embed.patch_score(a, a[::-1].copy()) > 0.99   # order-free
    assert embed.patch_score(a[:2], a[2:]) == 0.0
    assert embed.state()["state"] == "off" and embed.similarities(scene(1), [scene(2)]) is None   # the tests' default
    monkeypatch.delenv("IGL_NO_EMBED")
    monkeypatch.setenv("IGL_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setattr(embed, "_failed", "")
    monkeypatch.setattr(embed, "_session", None)
    assert embed.ensure(None) is None                            # nothing is downloaded without an HTTP client

    class Fake:
        dry, last_error = False, ""

        def download(self, url, dest, **kw):
            assert url.startswith("https://huggingface.co/") and "/resolve/" in url
            dest.write_bytes(b"not the model")
            return True
    assert embed.ensure(Fake()) is None and "checksum" in embed.why_not()
    assert not list((tmp_path / "models").glob("*"))             # a file that fails its checksum is not kept
    assert embed.similarities(scene(1), [scene(2)], Fake()) is None


def test_repeats_of_one_photograph_count_once(tmp_path: Path):
    q = scene(7)
    scene(50).save(tmp_path / "a.jpg", quality=90)
    Image.open(tmp_path / "a.jpg").resize((500, 333)).save(tmp_path / "b.jpg", quality=70)
    items = [{"file": str(tmp_path / "a.jpg"), "site": "one.example"}, {"file": str(tmp_path / "b.jpg"), "site": "two.example"}]
    counts = refs.rank_against(q, items, tmp_path / "w")
    assert counts == {"none": 1}
    assert [it.get("same_as") for it in sorted(items, key=lambda it: it["n"])] == [None, 1]


def test_small_object_agreement_is_flagged():
    dup = {"near_duplicate": False, "mirrored_duplicate": False}
    geo_ = {"available": True, "level": "strong", "mirrored": False, "h_inliers": 80, "f_inliers": 90, "matches": 120,
            "spread": 0.01, "same_photo": False}
    assert "ONE SMALL OBJECT" in match.verdict(dup, geo_)
    assert match.classify(dup, geo_) == "same"
    assert match.classify({"near_duplicate": True}, geo_) == "copy"
    assert match.classify(dup, {"available": False}) == "unchecked"
    assert match.LABEL["none"] == "unconfirmed"                  # never "different place"


# ----------------------------------------------------------------------------- providers and parsers
def test_brave_and_startpage_parsers():
    thumb = ("https://imgs.search.brave.com/sig/rs:fit:500:0:1:0/g:ce/aHR0cHM6Ly93d3cu/ZmpiaG90ZWxzLmNv/"
             "LnVrL21lZGlhL2lt/YWdlcy9zaGFyZWQv/aG90ZWxfZGRfaGF2/ZW4uanBn")
    assert refs.brave_original(thumb) == "https://www.fjbhotels.co.uk/media/images/shared/hotel_dd_haven.jpg"
    assert refs.brave_original("https://example.org/x.jpg") == ""
    html = ('results:[{title:"",url:"https://www.fjbhotels.co.uk/haven-hotel/",is_source_local:false,'
            'thumbnail:{src:"' + thumb + '",alt:null,height:246,width:500}}]')
    items = refs.parse_brave([{"thumb": thumb, "alt": "Haven Hotel", "site": "fjbhotels.co.uk"}, {"thumb": ""}], html)
    assert len(items) == 1 and items[0]["page"] == "https://www.fjbhotels.co.uk/haven-hotel/"
    assert items[0]["image"].endswith("hotel_dd_haven.jpg") and items[0]["provider"] == "brave"
    sp = ('[{"title":"Dining","clickUrl":"/av/proxy-image?piurl=x","altClickUrl":"https://www.fjbhotels.co.uk/dining/",'
          '"rawImageUrl":"https://www.fjbhotels.co.uk/a.jpg"},{"title":"Dining","rawImageUrl":"https://www.fjbhotels.co.uk/a.jpg"}]')
    got = refs.parse_startpage(sp)
    assert len(got) == 1 and got[0]["thumb"].startswith("https://www.startpage.com/av/proxy-image")
    assert got[0]["site"] == "fjbhotels.co.uk"
    merged = refs.dedupe_urls(items + [{"image": items[0]["image"], "title": "again", "page": ""}])
    assert len(merged) == 1


class FakeHttp:
    dry = False
    cache_dir = None

    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def get(self, url, params=None, **kw):
        self.calls.append((url, params))
        return self.reply


def test_lens_api_is_optional_and_parsed(monkeypatch):
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    assert revsearch.lens_api(FakeHttp({}), "https://x/y.jpg")["status"] == "unavailable"
    http = FakeHttp({"ok": True, "data": {"visual_matches": [
        {"title": "Lounge - Hotel Example", "link": "https://hotel.example/lounge", "thumbnail": "//t.example/1.jpg",
         "image": "https://hotel.example/l.jpg"}]}})
    r = revsearch.lens_api(http, "https://x/y.jpg", key="k")
    assert r["status"] == "results" and r["route"] == "api"
    h = r["hits"][0]
    assert h["kind"] == "page" and h["site"] == "hotel.example" and h["thumb"] == "https://t.example/1.jpg"
    assert http.calls[0][1]["engine"] == "google_lens"
    assert revsearch.lens_api(FakeHttp({"ok": False, "status": 429, "error": "HTTP 429"}), "u", key="k")["status"] == "blocked"
    assert revsearch.lens_api(FakeHttp({"ok": True, "data": {"error": "Google Lens hasn't returned any results"}}),
                              "u", key="k")["status"] == "no_results"


def test_a_search_that_never_started_is_not_no_results():
    assert "NOT a no-result" in revsearch.NOT_STARTED
    assert revsearch._hit("page", " A   title ", page="https://www.hotel.example/a", thumb="//cdn.example/t.jpg") == {
        "kind": "page", "title": "A title", "page": "https://www.hotel.example/a", "image": "",
        "thumb": "https://cdn.example/t.jpg", "site": "hotel.example"}


def test_photon_fallback_for_enumeration():
    feats = {"features": [
        {"geometry": {"coordinates": [-1.95, 50.68]}, "properties": {"name": "The Haven Hotel", "osm_type": "W", "osm_id": 1,
                                                                    "osm_key": "tourism", "osm_value": "hotel", "city": "Poole"}},
        {"geometry": {"coordinates": [2.35, 48.85]}, "properties": {"name": "Outside", "osm_type": "N", "osm_id": 2}}]}
    http = FakeHttp({"ok": True, "data": feats})
    r = geo.photon_poi(http, ["tourism=hotel"], None, None, {"bbox": [50.67, -1.97, 50.70, -1.92]})
    assert r["ok"] and [p["name"] for p in r["places"]] == ["The Haven Hotel"]      # outside the box: dropped
    url = http.calls[0][0]
    assert "osm_tag=tourism%3Ahotel" in url and "bbox=-1.97000%2C50.67000%2C-1.92000%2C50.70000" in url and "q=hotel" in url
    r = geo.photon_poi(FakeHttp({"ok": True, "data": {"features": []}}), [], "Blue Bottle", None, {"around": [35.66, 139.7, 800]})
    assert r["ok"] and r["places"] == []
    assert not geo.photon_poi(http, [], None, None, {"bbox": [0, 0, 1, 1]})["ok"]


def test_download_retries_transient_refusals(monkeypatch, tmp_path: Path):
    calls = {"n": 0}

    class Reply(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", None, None)
        return Reply(b"\xff\xd8image-bytes")

    monkeypatch.setattr(net.urllib.request, "urlopen", fake)
    monkeypatch.setattr(net.time, "sleep", lambda s: None)
    h = net.Http()
    assert h.download("https://cdn.example/a.jpg", tmp_path / "a.img") and calls["n"] == 2
    assert not h.download("ftp://cdn.example/a.jpg", tmp_path / "b.img") and "http" in h.last_error
