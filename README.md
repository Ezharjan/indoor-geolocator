# indoor-geolocator

**English** · [简体中文](README.zh-CN.md) · [Português](README.pt-BR.md) · [Français](README.fr.md) · [Español](README.es.md) · [日本語](README.ja.md) · [Deutsch](README.de.md)

An agent skill that works out **where an indoor photo was taken**: a hotel room, a flat, a restaurant, a
shop, a station, a museum, a classroom, a car. It returns the venue, the street address, coordinates with
an error radius and a confidence level that the evidence actually supports. It also leaves one tidy case
folder that shows every step of the reasoning.

It is an open-source OSINT tool for image geolocation by AI agents: GeoGuessr-style reasoning for interiors, backed by reverse image search, OCR, EXIF metadata and verification against reference photos.

**Project page and interactive demo:** https://ezharjan.github.io/indoor-geolocator/

Attach a photo and invoke the skill. No prompt is needed. The answer comes in the user's language and has
this shape (the values are illustrative):

```
📍 <Venue> — <street address, city, country>
   51.044560, -114.064700 (WGS84) ± 60 m · level: site · confidence: MEDIUM
Why: ... the 2-4 decisive evidence items, each with its source and how it was verified
Verified against: ... the reference photos compared, the features that matched, the rival that was tested
Best lead (unverified): ... a finer candidate, its coordinates (the single most likely point) and the test that would confirm it
Alternatives: ... the runner-up, its probability and the test that would separate them
Not verified / limits: ... what could not be checked and why
Case folder: .../photo-geolocation (REPORT.md has the full reasoning trail)
```

## What it does

The skill gives the model a strict, accuracy-first workflow and a command-line toolbox (`scripts/igl.py`,
Python 3.9+, Pillow). Every observation goes into one ledger, and the ranking and confidence are computed
from that ledger rather than asserted.

Indoor photos get located wrongly for a handful of reasons, and the workflow is built around them: a
look-alike room is taken for the place, the first plausible candidate is kept, machine output (OCR on a
carpet, an engine's label, a search that never ran) is read as fact, a portable object is read as the
building, a brand is taken for a branch, and precision is invented.

1. **Intake.** Copies the photo byte for byte. Reads EXIF, GPS, XMP, IPTC, ICC, the embedded thumbnail
   (a crop or edit shows up), the filename pattern, AI markers and C2PA content credentials, and maps the
   UTC offset to time zones. Checks in five seconds which online services the toolbox can reach.
2. **Hypotheses first.** Two to four ranked hypotheses are recorded before any tool output (anchor
   defence).
3. **Read the whole photo.**
   - Precision-filtered OCR (texture is not reported as text), QR codes and barcodes with payload
     interpretation (EMV payment codes, Swiss QR-bills, SEPA, UPI, Wi-Fi, vCards, GS1 prefixes), text
     mining (phones to the city, domains, prices, postcodes, units, tax words).
   - A clue catalogue of about 200 entries, read by the agent on overlapping tiles: identity carriers
     (names, unique art, the view), fixed standards (sockets, switches, plumbing, safety signs), and
     local references (a painting of a local landmark, a map, a leaflet).
4. **Find candidates.**
   - **Reverse image search** headless on Yandex, TinEye and Baidu, with Google Lens and Bing through a
     browser tool. Every hit is compared with the photo and classed **COPY** (the same photograph:
     provenance), **SAME SCENE** / **PARTIAL** (matching structure) or **unconfirmed**.
   - **Picture search by text** (`refs`): image searches for a venue, or for every venue of a kind in an
     area. The pictures are compared with the photo and shown **most similar first** (DINOv2), so the
     right venue surfaces even when no caption describes it. In a test, two generic searches for hotel
     bars in a US state put the actual bar first among 100 pictures of different bars.
   - Names, phones, URLs and Wi-Fi names with the agent's own web search; fixed standards intersected
     over 250 countries offline; every venue of a kind enumerated from OpenStreetMap and Wikidata;
     listings and social media (place-focused).
5. **Verify: the gate between a lead and an answer.** A falsification test is written first. The
   candidate's own photos are put next to the photo, and specific fixed features are counted (windows,
   ceiling, built-ins, the view, art made for the venue; furniture proves only a design). The closest
   rival goes through the same comparison. If the rival "matches" too, the features are a shared
   design: the match is recorded for the group's area, and the venues stay leads.
6. **Consistency.** Time zone, sun, weather, season and standards are checked against the candidate,
   the runner-up is argued for, and the deciding step is re-run differently.
7. **Decision.** The answer is the finest level the evidence verifies. An unverified venue under a
   verified area is reported as the best lead with its own coordinates (the single most likely point),
   never as the answer. The case folder is finalized and pruned.

### Accuracy rules built into the code

- **Status caps.** A clue's weight is capped by how it was obtained: an inference ≤3, an observation ≤6,
  a third-party report ≤10, file metadata or a traced copy of the photo ≤20, text read on a zoomed crop
  or a computed result ≤50, a match against independent reference imagery ≤100. An engine's label is a
  lead (≤3) whatever it says.
- **Identifying clues and category clues.** A decisive clue (a name read in the photo, a decoded code,
  GPS, a traced copy, a matched reference) identifies one place and is weighed against all alternatives
  together: LR 50 means about 50:1, however many rivals were listed. A category clue (a socket type, a
  language, a style) competes with every alternative one by one, so only several together settle a
  country.
- **Auditable matches.** A `matched` clue must name at least three specific fixed features and cite the
  comparison file. A copy of the photo is refused as a match: it is provenance, recorded as `traced`
  with its page.
- **The rival control.** A reference match reaches HIGH only when a rival venue went through the same
  comparison, or when a second decisive lineage (a name read in the photo, GPS, a traced copy) names
  the same venue.
- **A venue needs a decisive clue.** Resemblance, engine labels and captions leave a venue LOW, however
  many of them agree: that combination is exactly what a look-alike produces.
- **Independent lineages.** Agreement counts only across independent sources (image, text, metadata,
  web, engine, map, reference, geometry). Five décor clues are one lineage.
- **An open, coherent board.** Unlisted alternatives keep a share at every level, a city is never more
  certain than its country, and a contradiction against a country also blocks HIGH for the hotel in it.
- **Honest failure.** A search that was blocked or never started is reported as such, never as "no
  results". Unconfirmed pictures are never called "different".
- **Coverage gate.** Thirteen core methods must each end as results, no_results or not_applicable before

**As a plugin.** The skill folder is also a Claude plugin. In Claude Code run `claude plugin marketplace add Ezharjan/indoor-geolocator`, then `claude plugin install indoor-geolocator@ezharjan-plugins`. The privacy notice, which lists every service the skill can contact, is at https://ezharjan.github.io/indoor-geolocator/privacy.html. The plugin, like the skill, needs Pillow: `pip install pillow` (plus `tzdata` on Windows). Install one or the other, not both: as a plugin the skill is called `/indoor-geolocator:indoor-geolocator` instead of `/indoor-geolocator`.
  `check` passes; `check` also flags a site without a reference comparison or a rival, a rival that
  matched too, and reverse searches that never ran.

## Install

### Install with one prompt

In Claude Code, or in any agent that can run shell commands, just say: **"Install the indoor-geolocator skill from https://github.com/Ezharjan/indoor-geolocator"**. The rest of this section is written for the agent.

**Instructions for AI agents.** To install this skill for the user, run:

```bash
curl -L -o indoor-geolocator.zip https://github.com/Ezharjan/indoor-geolocator/releases/latest/download/indoor-geolocator.zip
mkdir -p ~/.claude/skills && unzip -o indoor-geolocator.zip -d ~/.claude/skills    # creates ~/.claude/skills/indoor-geolocator/
python3 -m pip install -r ~/.claude/skills/indoor-geolocator/requirements.txt
python3 ~/.claude/skills/indoor-geolocator/scripts/igl.py doctor                   # report what works and what is missing
```

- On Windows the skills folder is `%USERPROFILE%\.claude\skills\`: unpack with `Expand-Archive` and call `python` instead of `python3`.
- Do not install the optional extras silently. Show the user what `doctor` reports as missing and offer `requirements-optional.txt`, since those packages are large.
- Confirm that `~/.claude/skills/indoor-geolocator/SKILL.md` exists, then tell the user the skill is available in a new session as `/indoor-geolocator`.
- In a claude.ai or Claude Desktop chat an agent cannot add a skill by itself. Give the user the zip link above and the three upload steps below.

**claude.ai, Claude Desktop and Cowork.**
1. Make sure code execution is on (*Settings → Capabilities*). Network egress for code execution helps
   (the toolbox then reaches the map and reverse-search services itself); without it the agent does those
   steps with its own web search, fetch and browser tools.
2. Open *Customize → Skills*, click **+**, choose **+ Create skill → Upload a skill**, and select
   `indoor-geolocator.zip`.
3. Attach a photo and invoke the skill, or just ask "where was this taken?".

The zip holds the `indoor-geolocator/` folder at its top level, as the upload requires.

**Claude Code.** Copy the `indoor-geolocator/` folder into `~/.claude/skills/` (all projects) or
`<project>/.claude/skills/` (one project). Invoke it with `/indoor-geolocator`, or let Claude pick it up
when you share an interior photo.

**Other agents** (Codex, Gemini CLI, Cursor, …): point the agent at `indoor-geolocator/SKILL.md`. The
toolbox is a plain Python CLI.

**Dependencies.** Pillow is required, and so is `tzdata` on Windows. Everything else is optional and only
enables its method.

```bash
pip install -r indoor-geolocator/requirements.txt             # Pillow (+ tzdata, needed on Windows)
pip install -r indoor-geolocator/requirements-optional.txt    # OpenCV + numpy, Playwright, onnxruntime, phonenumbers, HEIC, RapidOCR
playwright install chromium                                   # headless reverse search, picture search, snapshots
# OCR engine (recommended): tesseract with language packs
#   apt install tesseract-ocr-all  |  brew install tesseract tesseract-lang  |  winget install UB-Mannheim.TesseractOCR
python indoor-geolocator/scripts/igl.py doctor                 # what works here, what is missing
```

Three extras matter most for accuracy: OpenCV (the COPY / SAME SCENE tests), Playwright with Chromium
(reverse image search and picture search) and onnxruntime (pictures sorted by likeness to the photo). The
similarity model (DINOv2 ViT-S/14, 24 MB, Apache-2.0) is not part of the skill: it is downloaded once
from huggingface.co on first use and checked against a SHA-256. `IGL_NO_EMBED=1` switches it off.

## Using the toolbox directly

```bash
IGL="python3 indoor-geolocator/scripts/igl.py"
$IGL init photo.jpg                                    # case folder + metadata + grid view + network check
$IGL note CASE "Hypotheses: 1) ... 2) ..." --kind hypothesis --status inferred --source image
$IGL scan CASE                                         # OCR, QR/barcodes, text signals, sweep tiles
$IGL crop CASE --cell C3:D4 --enhance auto --label socket
$IGL revsearch CASE --cell B2:C3 --flip                # Yandex, TinEye, Baidu; every hit classed against the photo
$IGL share CASE --cell B2:C3                           # links for Google Lens and Bing (temporary copy)
$IGL countries --plug G --currency £ --drive left --case CASE --clue N2
$IGL refs CASE "hotel lounge sea view Poole"           # pictures of a whole area, most similar first
$IGL geo poi --tag tourism=hotel --area "Poole" --case CASE --add site --parent C3
$IGL refs CASE "Hotel Name Poole lounge" --for C12     # one candidate's photos next to yours
$IGL compare CASE --refs E14 --pick 3,7 --for C12      # large side-by-side + match tests
$IGL note CASE "Matches a traveller photo (2023)" --kind match --status matched --source reference --file E16 \
     --features "arched window pair; coffered ceiling 3x4; green marble fireplace" --for C12:60 --why "..."
$IGL refs CASE "Rival Hotel Poole lounge" --for C13    # the rival control
$IGL rank CASE
$IGL answer CASE C12 --summary "..."
$IGL check CASE
$IGL finalize CASE
```

`$IGL <command> -h` documents every option. On Windows use `python` instead of `python3`. Southern and
western coordinates work as typed (`--at -33.86,151.21`).

## What you get

```
photo-geolocation/
├── REPORT.md       the answer, best lead, confidence by level, evidence, candidates, timeline, methods, data handling
├── result.json     the same as machine-readable JSON (schema igl.result/1)
├── case.json       the complete ledger: clues, candidates, links, exclusions, attempts, timestamps
├── input/          the photo (byte-exact) and metadata.json
└── evidence/       only the crops, sheets, match views and snapshots the ledger cites
```

Scratch work (tiles, caches, downloads) lives in `.work/` and is deleted by `finalize`, which also removes
every evidence file that nothing cites. An existing case folder is never overwritten.

## Privacy and responsible use

- **People are not targets.** No face recognition and no identification of individuals.
  - Clothing, uniforms, badges and personal items are used only for what they say about the place.
  - Apparent ethnicity is treated as weak, bias-prone context, never as an exclusion.
  - Social media is searched for places, text, tags and the photo itself, never for people or posters.
- **Private homes.** For an identifiable private residence with no stated purpose, the skill asks once
  what the result is for. Without a legitimate purpose it stops at city or neighbourhood level.
- **Redaction.** Private names and home addresses are left out of reports. Wi-Fi passwords, IBANs and
  contact-card names are redacted wherever they are decoded or echoed back by an engine or a page.
- **Uploads.** Reverse image search uploads the photo (metadata stripped) to the engines. `share` puts a
  metadata-free copy on a temporary host (deleted after 1-3 hours) for Lens and Bing, and `revsearch`
  does the same on its own when an engine's upload form fails (`--no-share` prevents it). The report
  lists every engine and every temporary copy. `refs` sends only search text, and the similarity model
  runs locally. Prefer crops without people, and nothing is uploaded without asking when the user marks
  a photo as private.
- **Services.** The skill respects service policies (Nominatim ≤1 request/s, bounded Overpass queries,
  identifying User-Agent). It never logs in on anyone's behalf, never solves CAPTCHAs and never bulk
  scrapes. Optional user keys: `SERPAPI_KEY` for Google Lens inside `revsearch`, `WIGLE_API_NAME` /
  `WIGLE_API_TOKEN` for Wi-Fi SSID lookups. `IGL_USER_AGENT` sets a custom User-Agent.

Geolocation results are evidence-weighted estimates, not certainties. Read the confidence, the best lead
and the "not verified" line before acting on an answer.

## Repository layout

```
.
├── indoor-geolocator/          THE skill (this folder is what gets installed)
│   ├── SKILL.md                workflow, evidence rules, conduct, answer format
│   ├── LICENSE.txt             copy of LICENSE (the zip ships without the repository root)
│   ├── requirements*.txt
│   ├── references/             clue catalogue, scene and search playbooks, window/light, verification,
│   │                           evidence and confidence, sources and tools
│   ├── scripts/igl.py          the CLI; scripts/iglib/ holds its modules
│   └── data/                   countries.json, gs1_prefixes.json (+ README with sources and licences)
├── indoor-geolocator.zip       the same skill, packed for upload
├── build_skill_zip.py          rebuilds and verifies the zip (run after every change to the skill)
├── tools/build_data.py         maintainer tool: rebuilds data/ from Unicode CLDR and Wikipedia
├── tools/make_demo.py          maintainer tool: rebuilds docs/demo/ with the current version
├── tests/                      offline test suite (pytest; `pytest.ini` points at it)
├── docs/                       project page (GitHub Pages) with the published demo case
├── LICENSE
├── README.md
└── README.*.md                 this README in other languages (zh-CN, pt-BR, fr, es, ja, de)
```

## Development

```bash
python -m pytest                   # offline tests: ledger rules, caps, matching, ranking, parsers, geometry;
                                   # also docs vs CLI, the zip vs the skill folder, the project page vs the demo case
python tools/build_data.py         # refresh data/ (caches sources in .data-src/; --offline to rebuild from cache)
python tools/make_demo.py          # rebuild the demo case in docs/demo/ with the current version
python build_skill_zip.py          # rebuild indoor-geolocator.zip if the folder changed; --check to verify only
```

## Changelog

### 2.0.1

Packaging only: the skill behaves as in 2.0.0.

- **Plugin.** The skill folder is now also a Claude plugin (`.claude-plugin/plugin.json`, an icon, and a README that lists everything the skill runs, sends and fetches), and the repository is a plugin marketplace.
- **Data.** `countries.json` is written one country per line: the same data in a smaller file.
- **Privacy notice.** A page that lists every service the skill can contact and what is sent to it.

### 2.0.0

The accuracy release: built against the commonest wrong answer, a look-alike venue named with confidence.

- **Finding.** New `refs` command: image search by text (Brave, Startpage) and gallery pages, every
  picture compared with the photo. Pictures and reverse-search hits are sorted by visual similarity
  (DINOv2, optional), so the likeliest references are the first tiles the agent sees.
- **Reverse search.** Every hit is classed COPY / SAME SCENE / PARTIAL / unconfirmed against the photo.
  A search that never started is `unavailable`, not `no_results`; by-URL fallback when an upload form
  fails; optional Google Lens through the user's SerpApi key.
- **Verification.** `matched` clues must name three features and cite the comparison; copies are refused
  as matches and recorded as `traced` provenance; `compare --refs E## --pick`; the rival control is
  required for HIGH; design matches are recorded for the area, with the venues as leads.
- **Confidence.** Decisive clues are weighed against the whole field (a verified venue is no longer
  diluted by unlisted countries or by the rivals the agent enumerated); a venue needs a decisive clue
  for MEDIUM; engine labels are capped at 3; contradictions block HIGH down the chain; a place is at
  least as certain as the verified place inside it.
- **Reading.** OCR output is filtered for precision (no more "text" and exotic scripts read off carpets
  and ceilings); `scan` writes a sheet of the text crops; `crop --of` zooms into any evidence image.
- **Robustness.** Photon fallback when Overpass is unreachable, retrying downloads, per-run reporting
  of rate limits, methods implied by recorded clues, `log` with comma lists.
- **Output.** A best-estimate pin (the lead's coordinates when the answer is coarser), a verification
  section with the rival control in the report, candidate tables that say what each row is (the answer,
  a place that contains it, the unverified lead, the alternatives not on the board), `tools/make_demo.py`
  to rebuild the demo case, and tests that hold the project page to that case and the zip to the skill
  folder.

### 1.1.0

Not tagged or released on its own: these changes are first published with 2.0.0.

- Workflow reordered around exact-match routes and a verification gate; hypotheses before tool output;
  routing between the toolbox and the agent's own web search, fetch and browser tools.
- Scoring: an open board at every level, coherent chain shares, no flow-up of category clues, answer
  gating with a separate best lead, pre-report checks.
- Reverse search: Baidu added, similar-image contact sheets, `share` for Lens and Bing by URL.
- `compare`: near-duplicate, same-photograph and SIFT/RANSAC geometric tests with mirrored rooms.
- `init` network check; `geo ... --print-url`; `note --for/--against` in one call; C2PA reader.

### 1.0.0

First public release.

## Licence

The code and documentation are released under the [MIT License](LICENSE). The data files in
`indoor-geolocator/data/` keep their sources' licences:
- Unicode CLDR fields: [Unicode License v3](https://www.unicode.org/license.txt).
- Wikipedia-derived fields (plug types, mains, driving side, emergency numbers, GS1 prefixes):
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), © Wikipedia contributors.

Details are in [indoor-geolocator/data/README.md](indoor-geolocator/data/README.md).

Design ideas were adapted from the open-source projects geo-sleuth, Geo-Guesser and Searching-skill: rules
enforced in code, a likelihood-ratio candidate board, evidence graded by lineage, a method-coverage gate,
"the machine ranks first" with a DINOv2 similarity order, and SIFT/RANSAC verification. The similarity
model is DINOv2 (Meta AI, Apache-2.0) in the ONNX export published as `Xenova/dinov2-small`; it is
downloaded at run time and not redistributed here.
