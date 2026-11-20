"""The documents, the CLI, the installable zip and the published demo must agree: every `IGL <command>` and
every `--option` that SKILL.md, the references, the READMEs and the project page put next to a command
exists in the argument parser; the version strings are the same everywhere; indoor-geolocator.zip holds
exactly the skill folder; and the project page (docs/index.html) quotes the demo case in docs/demo/ and the
rules in the code exactly."""
from __future__ import annotations

import html
import importlib.util
import json
import re
from pathlib import Path

import igl
from iglib import __version__, knowledge
from iglib.case import ATTEMPT_STATUS, CORE_METHODS, GRADE, KINDS, OPTIONAL_METHODS, SOURCES, STATUS_CAP

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "indoor-geolocator"
READMES = [REPO / "README.md", *sorted(REPO.glob("README.*.md"))]     # English first, then the translations
DOCS = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md")), *READMES]
PAGE = REPO / "docs" / "index.html"                             # the project page (GitHub Pages)
DEMO = REPO / "docs" / "demo"                                   # the case it walks through


def _commands() -> dict[str, set[str]]:
    """{command or 'geo search': its option strings}."""
    parser = igl.build_parser()
    out: dict[str, set[str]] = {}

    def walk(p, name):
        subs = [a for a in p._actions if a.__class__.__name__ == "_SubParsersAction"]
        opts = {o for a in p._actions for o in a.option_strings}
        if name:
            out[name] = opts
        for s in subs:
            for child, cp in s.choices.items():
                walk(cp, f"{name} {child}".strip())
    walk(parser, "")
    return out


CMDS = _commands()
TOP = {c.split()[0] for c in CMDS}
CALL = re.compile(r"(?:\bIGL|igl\.py)\s+([a-z][a-z-]*)((?:[ \t]+[^\n`|]*)?)")


def _mentions(text: str):
    for m in CALL.finditer(text):
        cmd, rest = m.group(1), m.group(2) or ""
        if cmd not in TOP:
            continue
        words = rest.split()
        full = f"{cmd} {words[0]}" if words and f"{cmd} {words[0]}" in CMDS else cmd
        yield full, set(re.findall(r"(?<![\w-])--[a-z][a-z-]*", rest))


def _page_text() -> str:
    """The project page as plain text; each command chip (`<span class="chip">refs --for</span>`) becomes a
    line `igl.py refs --for`, so the chips are checked like every other mention."""
    page = PAGE.read_text(encoding="utf-8")
    chips = re.findall(r'<span class="chip">([^<]+)</span>', page)
    assert len(chips) >= 15 and all(c.split()[0] in TOP for c in chips), chips
    page = page.replace('<span class="chip">', "\nigl.py ")
    return html.unescape(re.sub(r"<[^>]+>", " ", page))


def test_documented_commands_and_options_exist():
    seen = 0
    for name, text in [(d.name, d.read_text(encoding="utf-8")) for d in DOCS] + [(PAGE.name, _page_text())]:
        for cmd, opts in _mentions(text):
            subs = (v for k, v in CMDS.items() if k.startswith(cmd + " ")) if cmd in ("geo", "social") else ()
            missing = opts - CMDS[cmd].union(*subs)
            assert not missing, f"{name}: `IGL {cmd}` is shown with {sorted(missing)}, which the CLI does not have"
            seen += 1 + len(opts)
        for word in re.findall(r"`IGL ([a-z-]+)", text):
            assert word in TOP, f"{name}: `IGL {word}` is not a command"
    assert seen > 300                                           # the docs and the page really were scanned


def test_documented_vocabulary_matches_the_code():
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    evid = (SKILL / "references" / "evidence-and-confidence.md").read_text(encoding="utf-8")
    for status, cap in STATUS_CAP.items():
        assert f"`{status}`" in evid and f"`{status}`" in skill, status
        assert re.search(rf"\| `{status}` \| [A-D] \| {cap:g} \|", evid), f"cap of {status} in the status table"
    for source in SOURCES:
        assert f"`{source}`" in evid, source
    for text in ((SKILL / "references" / f).read_text(encoding="utf-8") for f in
                 ("verification.md", "search-playbook.md", "sources-and-tools.md", "scene-playbooks.md")):
        for m in re.findall(r"--status ([a-z_]+)", text):
            assert m in STATUS_CAP or m in ATTEMPT_STATUS, m
        for m in re.findall(r"--kind ([a-z-]+)", text):
            assert m in KINDS, m
        for m in re.findall(r"IGL log <case> ([a-z_,]+)", text):
            assert all(x in CORE_METHODS or x in OPTIONAL_METHODS for x in m.split(",")), m


def _zip_builder():
    spec = importlib.util.spec_from_file_location("build_skill_zip", REPO / "build_skill_zip.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _shape(readme: Path) -> tuple:
    """What every translation must share with the English README: the heading levels, the number of list
    items, and every code block with its comments and prose removed (the commands themselves)."""
    text = readme.read_text(encoding="utf-8")
    blocks = re.findall(r"^```(\w*)\n(.*?)^```", text, flags=re.S | re.M)
    commands = [[ln.split("  #")[0].rstrip() for ln in body.splitlines() if not ln.lstrip().startswith("#")]
                for lang, body in blocks if lang == "bash"]
    trees = [re.findall(r"^[│ ]*[├└]── \S+", body, flags=re.M) for lang, body in blocks if not lang]
    prose = re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)
    return (re.findall(r"^#+", prose, flags=re.M), len(re.findall(r"^\s*(?:-|\d+\.) ", prose, flags=re.M)),
            sorted(set(re.findall(r"`[^`\n]+`", prose))), commands, trees[1:])


def test_versions_agree_and_skill_files_are_linked():
    assert f"v{__version__}" in PAGE.read_text(encoding="utf-8")
    english = _shape(READMES[0])
    assert len(READMES) == 7, [r.name for r in READMES]
    for readme in READMES:
        text = readme.read_text(encoding="utf-8")
        assert f"### {__version__}" in text, readme.name
        assert all(f"]({r.name})" in text or r == readme for r in READMES), f"{readme.name}: language links"
        assert _shape(readme) == english, f"{readme.name} has drifted from README.md (headings, lists or commands)"
    assert _zip_builder().__version__ == __version__
    # what search engines read: one canonical address, used by the sharing tags, the sitemap and the READMEs
    page = PAGE.read_text(encoding="utf-8")
    site = re.search(r'<link rel="canonical" href="([^"]+)">', page).group(1)
    data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page, flags=re.S).group(1))
    assert data["softwareVersion"] == __version__ and data["url"] == site
    assert f'<meta property="og:url" content="{site}">' in page
    assert f"<loc>{site}</loc>" in (PAGE.parent / "sitemap.xml").read_text(encoding="utf-8")
    for image in set(re.findall(r'content="(' + re.escape(site) + r'[^"]+\.(?:png|jpg))"', page)):
        assert (PAGE.parent / image[len(site):]).is_file(), image
    assert all(site in r.read_text(encoding="utf-8") for r in READMES)
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for ref in (SKILL / "references").glob("*.md"):
        assert f"references/{ref.name}" in skill, f"SKILL.md does not point to {ref.name}"
    assert len(skill.splitlines()) < 500                        # the body stays short; details live in references/


def test_zip_holds_exactly_the_skill_folder():
    """indoor-geolocator.zip is what people install. After any change to the skill: python build_skill_zip.py"""
    bz = _zip_builder()
    meta, problems = bz.front_matter(SKILL / "SKILL.md")
    assert not problems + bz.folder_problems(SKILL) and meta["name"] == SKILL.name
    stale, _line_endings_only = bz.compare(SKILL, REPO / f"{SKILL.name}.zip")
    assert not stale, "indoor-geolocator.zip is out of date - run: python build_skill_zip.py\n  " + "\n  ".join(stale)


# ----------------------------------------------------------------------------- the project page and its demo
def _demo():
    load = lambda name: json.loads((DEMO / name).read_text(encoding="utf-8"))  # noqa: E731
    return load("case.json"), load("result.json"), load("evidence/E02_scan.json")


def _kb(path: Path) -> int:
    """Size as the tool prints it (whole KB), whatever line endings a git checkout on Windows gave the file."""
    return len(path.read_bytes().replace(b"\r\n", b"\n")) // 1024


def test_project_page_quotes_the_published_demo_case():
    page = PAGE.read_text(encoding="utf-8")
    text = html.unescape(re.sub(r"<[^>]+>", "", page))            # what a reader sees, tags removed
    case, res, scan = _demo()
    assert case["tool_version"] == res["tool_version"] == __version__
    assert f"indoor-geolocator {__version__}" in (DEMO / "REPORT.md").read_text(encoding="utf-8")

    # every demo file the page shows or links to exists; pictures are declared at their real size
    shown = set(re.findall(r'(?:src|href)="(demo/[^"#]+)"', page))
    assert shown and all((REPO / "docs" / f).is_file() for f in shown), sorted(shown)
    from PIL import Image
    pictures = re.findall(r'<img[^>]*src="(demo/[^"]+)"[^>]*width="(\d+)"[^>]*height="(\d+)"', page)
    assert len(pictures) == page.count("<img ") >= 5              # every picture on the page is a demo file
    for src, w, h in pictures:
        with Image.open(REPO / "docs" / src) as im:
            assert im.size == (int(w), int(h)), src
    evidence = sorted(f.name for f in (DEMO / "evidence").iterdir())
    assert set(evidence) == {Path(f["path"]).name for f in case["files"].values()}      # nothing stray, nothing missing
    assert f"{len(evidence)} cited files" in text and f"… {len(evidence)} evidence files" in text
    for name in ("REPORT.md", "result.json", "case.json"):
        assert re.search(rf">{re.escape(name)}</a><span>{_kb(DEMO / name)} KB</span>", page), f"{name}: {_kb(DEMO / name)} KB"
    for name in ("REPORT.md", "case.json"):
        assert f"{name}  ({_kb(DEMO / name)} KB)" in text         # the quoted `finalize` listing

    # the scan viewer: OCR lines, the QR code, the text signals
    rows = re.findall(r'\["([TQ]\d+)", "([^"]*)", \[(\d+), (\d+), (\d+), (\d+)\], "([^"]+)"\]', page)
    lines = {ln["id"]: ln for ln in scan["ocr"]["lines"]}
    codes = {c["id"]: c for c in scan["codes"]["codes"]}
    assert {r[0] for r in rows} == set(lines) | set(codes)
    for rid, shown_text, x0, y0, x1, y1, conf in rows:
        box = [int(x0), int(y0), int(x1), int(y1)]
        if rid in lines:
            assert (shown_text, box, conf) == (lines[rid]["text"], lines[rid]["box"], f"{lines[rid]['conf']:.2f}"), rid
        else:
            assert box == codes[rid]["box"] and "<redacted>" in codes[rid]["raw"], rid
    phone, money = scan["text_signals"]["phones"][0], scan["text_signals"]["currencies"][0]
    assert f"{phone['raw']} → {phone['country']}, {phone['area']}, {phone['timezones'][0]}" in text
    assert f"{money['sample']} → {money['n_countries']} territories" in text

    # the clues and commands quoted from the ledger
    n1 = " ".join(case["clues"]["N1"]["text"].split())
    assert n1 in " ".join(text.split()), "the hypothesis note on the page is not the one in the ledger"
    assert case["clues"]["N4"]["text"] in " ".join(text.split())
    links = {(e["clue"], e["candidate"]): e for e in case["evidence"]}
    uk = next(c for c in case["candidates"].values() if c["name"] == "United Kingdom")
    assert f'igl.py link CASE N4 --for {uk["id"]}:30 --why "{links[("N4", uk["id"])]["why"]}"' in text
    files = {Path(f["path"]).name: eid for eid, f in case["files"].items()}
    assert f"{files['E05_socket.jpg']}  evidence/E05_socket.jpg" in text and "--file " + files["E06_tent-card.jpg"] in text

    # the country board, the tiers and the answer
    board = page[page.index("board: {"):page.index("caps: {")]
    shares = {name: float(v) for name, v in re.findall(r'\["([^"]+)", ([\d.]+),', board)}
    countries = sorted((c for c in res["candidates"]["country"] if c["id"] != "C*"), key=lambda c: -c["share"])
    rest = next(c for c in res["candidates"]["country"] if c["id"] == "C*")
    top, others = countries[:7], countries[7:]
    for c in top:
        assert shares[c["name"].replace("St.", "St")] == c["share"], c["name"]
    assert shares[f"{len(others)} other listed candidates"] == round(sum(c["share"] for c in others), 4)
    n_rest = int(re.search(r"\((\d+) not on the board\)", rest["name"]).group(1))
    assert shares[f"{n_rest} countries not on the board (C*)"] == rest["share"]
    assert f"({top[1]['share'] * 100:.1f} % share each)" in text
    levels = res["confidence"]["by_level"]
    assert levels["country"]["tier"] == "high" and f"The UK holds {levels['country']['share']:.2f}" in text
    for reason in levels["city"]["reasons"]:
        assert reason in text, reason                              # the refusal of `--confidence high`, as printed
    ans = case["answer"]
    assert f"{ans['lat']:.6f}, {ans['lon']:.6f} (WGS84) ± {ans['radius_m']} m · level: {ans['level']}" in text
    assert f"{ans['lat']}, {ans['lon']} ± {ans['radius_m']} m · level {ans['level']} · confidence {ans['confidence']} " \
           f"(cap {ans['cap']})" in text


def test_project_page_states_the_rules_and_numbers_of_the_code(request):
    page = PAGE.read_text(encoding="utf-8")
    stats = {html.unescape(cap): int(n)
             for n, cap in re.findall(r'<div class="stat"><b>(\d+)</b><span>([^<]+)</span>', page)}
    assert stats["core methods, each logged"] == len(CORE_METHODS)
    assert stats["evidence statuses, each capped in code"] == len(STATUS_CAP)
    assert stats["countries & territories, offline"] == knowledge.universe_size()
    caps = page[page.index("caps: {"):page.index("var tip")]
    rows = re.findall(r'\["(\w+)", (\d+), "[^"]*", (?:true|false), "grade ([A-D])"\]', caps)
    assert {(s, float(v), g) for s, v, g in rows} == {(s, cap, GRADE[s]) for s, cap in STATUS_CAP.items()}
    n = stats["offline tests passing"]
    assert f"<b>{n} offline tests</b>" in page                    # the same number in both places
    items = request.session.items                                 # compared only when the whole suite is running
    whole_suite = ({i.nodeid.split("::")[0].rsplit("/", 1)[-1] for i in items}
                   == {f.name for f in (REPO / "tests").glob("test_*.py")})
    if whole_suite and not request.config.getoption("keyword") and not request.config.getoption("markexpr"):
        assert n == len(items), f"docs/index.html says {n} tests (two places); this suite has {len(items)}"

