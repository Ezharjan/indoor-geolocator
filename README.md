# indoor-geolocator

An agent skill that works out **where an indoor photo was taken**: a hotel room, a flat, a restaurant, a
shop, a station, a museum, a classroom, a car. It returns the venue, the street address, coordinates with
an error radius and a confidence level that the evidence actually supports. It also leaves one tidy case
folder that shows every step of the reasoning.

Attach a photo and invoke the skill. No prompt is needed. The answer has this shape (the values are
illustrative):

```
📍 <Venue> — <street address, city, country>
   51.044560, -114.064700 (WGS84) ± 60 m · level: site · confidence: MEDIUM
Why: ... the 2-4 decisive evidence items, each with its source and how it was verified
Alternatives: ... the runner-up and the test that would separate them
Not verified / limits: ... what could not be checked and why
Case folder: .../palliser-geolocation (REPORT.md has the full reasoning trail)
```

## What it does

The skill gives the model a strict workflow and a small command-line toolbox (`scripts/igl.py`, Python
3.9+, Pillow). Every observation goes into one ledger, and the ranking and confidence are computed from
that ledger rather than asserted.

1. **Intake.** Copies the photo byte for byte. Reads EXIF, GPS, XMP, IPTC, ICC, the embedded thumbnail
   (a crop or edit shows up), the filename pattern, AI and C2PA markers, and maps the UTC offset to time
   zones.
2. **First impression.** Recorded before any tool output, then confirmed, refined or overturned (anchor
   defence).
3. **Machine perception.**
   - Multi-pass OCR with script probing, plus a hint to re-read in the local language.
   - QR codes and barcodes, with payload interpretation: EMV payment codes (merchant name and city),
     Swiss QR-bills, SEPA, UPI, Wi-Fi, vCards, GS1 prefixes.
   - Text mining: phone numbers to the city, domains, prices and currencies (also former ones),
     calendar eras, postcodes, units, tax words.
4. **Visual sweep** with a clue catalogue of about 190 entries:
   - fixed standards: sockets, switches, plumbing, heating, windows, safety signs, lift certificates,
     floor numbering;
   - products, brands, payment schemes and regulatory marks;
   - style, patterns, customs and religious or seasonal décor;
   - personal items such as uniforms, tickets and receipts, used only for what they say about the
     place.
5. **Country intersection.** Offline tables built from Unicode CLDR and Wikipedia cover 250 countries:
   plug types, currencies, languages and scripts, calling codes, driving side, emergency numbers,
   week start, clock, units and paper size.
6. **Retrieval.**
   - Reverse image search: Yandex and TinEye headless; Google Lens and Bing in a browser.
   - Social media: keyless open APIs (Bluesky, Flickr tags, Openverse, Mastodon, Lemmy), plus
     ready-made searches for Instagram, TikTok, X, Reddit, YouTube, Xiaohongshu, Douyin, Weibo, VK, Naver
     and others.
   - Listing and review platforms for about 50 countries.
   - OpenStreetMap enumeration with co-location queries, Wikidata SPARQL, and Wikimedia Commons.
7. **Window views and light.** Floor estimate, sun azimuth and elevation (NOAA, checked against NREL SPA
   within 0.05°), bearings to landmarks, qibla, and historical weather.
8. **Verification.**
   - A falsification test is written before comparing.
   - Comparison uses invariant features only (windows, ceilings, built-ins, the view), against
     independent reference photos.
   - A consistency pass checks time zone, sun, weather, season and standards.
   - The decisive step is re-run, and the runner-up is steelmanned.
9. **Decision.** The answer is the top-ranked candidate. Its confidence is capped by rules in code, and
   the case folder is finalized and pruned.

### Accuracy rules built into the code

- **Status caps.** A clue's weight is capped by how it was obtained: an inference ≤3, an observation ≤6,
  a third-party report ≤10, metadata ≤20, text read on a zoomed crop or a computed result ≤50, a match
  against independent reference imagery ≤100.
- **Independent lineages.** Agreement counts only across independent sources (image, text, metadata,
  web, engine, map, reference, geometry). Five décor clues are one lineage. Following an engine's guess
  into a database is circular, not corroboration.
- **Exclusions.** Only decisive evidence with a file can rule a candidate out. Omission is never
  exclusion: at country level, the unlisted countries stay in play as one block.
- **Confidence caps.** HIGH needs a decisive clue, two independent lineages, a share of at least 0.80 and
  no open contradiction. At site level it also needs a reference-image match or two decisive lineages.
  `answer` refuses anything higher than the cap.
- **Coverage gate.** Thirteen core methods must each end as results, no_results or not_applicable before
  `check` passes. A blocked service is never reported as an absence.

## Install

**claude.ai, Claude Desktop and Cowork.**
1. Make sure code execution is on (*Settings → Capabilities*).
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
pip install -r indoor-geolocator/requirements-optional.txt    # OpenCV, phonenumbers, Playwright, HEIC, RapidOCR
playwright install chromium                                   # automated reverse search and page snapshots
# OCR engine (recommended): tesseract with language packs
#   apt install tesseract-ocr-all  |  brew install tesseract tesseract-lang  |  winget install UB-Mannheim.TesseractOCR
python indoor-geolocator/scripts/igl.py doctor                 # what works here, what is missing
```

## Using the toolbox directly

```bash
IGL="python3 indoor-geolocator/scripts/igl.py"
$IGL init photo.jpg                                    # new case folder + metadata + grid view
$IGL note CASE "First impression: ..." --kind hypothesis --status inferred --source image
$IGL scan CASE                                         # OCR, QR/barcodes, text signals, sweep tiles
$IGL crop CASE --cell C3:D4 --enhance auto --label socket
$IGL countries --plug G --currency £ --drive left --case CASE --clue N2
$IGL social search "Hotel Name City" --case CASE --sheet 12
$IGL geo poi --brand "Hampton" --tag tourism=hotel --area "Berlin" --case CASE --add site --parent C3
$IGL compare CASE --ref https://example.org/room.jpg
$IGL rank CASE ; $IGL answer CASE C12 --summary "..." ; $IGL check CASE ; $IGL finalize CASE
```

`$IGL <command> -h` documents every option. On Windows use `python` instead of `python3`. Southern and
western coordinates work as typed (`--at -33.86,151.21`).

## What you get

```
photo-geolocation/
├── REPORT.md       the answer, confidence by level, evidence table, candidates, timeline, methods, data handling
├── result.json     the same as machine-readable JSON (schema igl.result/1)
├── case.json       the complete ledger: clues, candidates, links, exclusions, attempts, timestamps
├── input/          the photo (byte-exact) and metadata.json
└── evidence/       only the crops, sheets and snapshots the ledger cites
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
  contact-card names are redacted where they are decoded.
- **Uploads.** Reverse image search uploads the photo to third parties, and the report lists which
  engines received it. Prefer crops without people, and ask first when a photo is sensitive.
- **Services.** The skill respects service policies (Nominatim ≤1 request/s, bounded Overpass queries,
  identifying User-Agent). It never logs in on anyone's behalf, never solves CAPTCHAs and never bulk
  scrapes. Optional user keys: `WIGLE_API_NAME` / `WIGLE_API_TOKEN` for Wi-Fi SSID lookups.
  `IGL_USER_AGENT` sets a custom User-Agent.

Geolocation results are evidence-weighted estimates, not certainties. Read the confidence and the
"not verified" line before acting on an answer.

## Repository layout

```
.
├── indoor-geolocator/          THE skill (this folder is what gets installed)
│   ├── SKILL.md                workflow, hard rules, answer format
│   ├── LICENSE.txt             copy of LICENSE (the zip ships without the repository root)
│   ├── requirements*.txt
│   ├── references/             clue catalogue, scene and search playbooks, window/light, verification,
│   │                           evidence and confidence, sources and tools
│   ├── scripts/igl.py          the CLI; scripts/iglib/ holds its modules
│   └── data/                   countries.json, gs1_prefixes.json (+ README with sources and licences)
├── indoor-geolocator.zip       the same skill, packed for upload
├── build_skill_zip.py          rebuilds and verifies the zip (run after every change to the skill)
├── tools/build_data.py         maintainer tool: rebuilds data/ from Unicode CLDR and Wikipedia
├── tests/                      offline test suite (pytest; `pytest.ini` points at it)
├── LICENSE
└── README.md
```

## Development

```bash
python -m pytest                   # offline tests: ledger rules, caps, parsers, geometry vs references
python tools/build_data.py         # refresh data/ (caches sources in .data-src/; --offline to rebuild from cache)
python build_skill_zip.py          # rebuild indoor-geolocator.zip if the folder changed; --check to verify only
```

## Licence

The code and documentation are released under the [MIT License](LICENSE). The data files in
`indoor-geolocator/data/` keep their sources' licences:
- Unicode CLDR fields: [Unicode License v3](https://www.unicode.org/license.txt).
- Wikipedia-derived fields (plug types, mains, driving side, emergency numbers, GS1 prefixes):
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), © Wikipedia contributors.

Details are in [indoor-geolocator/data/README.md](indoor-geolocator/data/README.md).

Design ideas were adapted from the reference projects geo-sleuth, Geo-Guesser, Searching-skill and
webcam-calibrator: rules enforced in code, a likelihood-ratio candidate board, evidence graded by lineage,
a method-coverage gate, and the verified zip build.
