---
name: indoor-geolocator
description: Find where an indoor photo was taken (hotel room, home, rental, restaurant, shop, mall, office, school, hospital, station, airport, museum, church, vehicle interior) from one image. Returns the venue name, street address, latitude/longitude with an error radius, and a rules-capped confidence, plus a tidy case folder that traces every step. Mines every channel - metadata, all visible text (OCR, QR codes, barcodes, phones, prices), fixed standards (sockets, switches, fittings, safety signs), style, patterns, customs, products, personal items, window views - then reverse image search, social media, listings, maps, OSM and Wikidata OSINT, and verifies against reference imagery. Use whenever a user shares an interior photo and asks where it is, which hotel or building it is, to geolocate it, or gives the image with no other prompt.
license: MIT
---

# indoor-geolocator

**Goal: the most accurate location the evidence can support, proven step by step.** Accuracy beats speed:
keep working through every applicable method until the answer is verified or every feasible route is
exhausted. Every claim in the final answer must point to a ledger entry backed by a file, a URL or a
deterministic tool result produced in this session.

## What you deliver

1. In chat: the answer block (format at the end) - place name, full address, `lat, lon` (WGS84, 6 decimals)
   ± radius, the level reached (country › region › city › district › site › room), confidence
   HIGH / MEDIUM / LOW with the decisive evidence, alternatives, and what would change the answer.
2. One case folder - nothing is written anywhere else:
   `REPORT.md` (human report) · `result.json` (machine result) · `case.json` (complete ledger) ·
   `input/` (byte-exact photo + metadata.json) · `evidence/` (only the files the ledger cites).
   Scratch lives in `.work/` and is deleted by `finalize`, which also prunes uncited files.

## The toolbox

`IGL` below means `python3 "<skill dir>/scripts/igl.py"`, where `<skill dir>` is the folder holding this
SKILL.md (Claude Code sets `${CLAUDE_SKILL_DIR}`; otherwise use the absolute path; on Windows use
`python`). Python 3.9+ and Pillow are required, plus `tzdata` on Windows (`pip install -r
requirements.txt`). Optional extras widen coverage: tesseract or
`rapidocr-onnxruntime` (OCR), `opencv-python-headless` (QR/barcodes), `phonenumbers`, `playwright` plus
Chromium (automated reverse search), `pillow-heif` (HEIC). Run `IGL doctor` once per environment. A
missing extra disables only its method: say so and use the alternative. `IGL <command> -h` shows options.

Commands:
- Case: `init`, `scan`, `crop`, `tiles`, `compare`, `snapshot`.
- Offline knowledge: `countries`, `lookup`, `sun`, `bearing`.
- Online lookups: `geo search|reverse|poi|photos|wikidata|sparql|timezone|weather|wigle`, `revsearch`,
  `social search|links`.
- Ledger: `note`, `cand`, `link`, `exclude`, `log`, `rank`, `check`, `answer`, `report`, `finalize`,
  `status`.

`scan`, `revsearch` and `geo poi` can take a few minutes, so give your shell a generous timeout.

The photo must be a file. In claude.ai or Cowork, attachments are under `/mnt/user-data/uploads/`. If you
only see the image inline with no path, ask for the file and meanwhile analyse it visually. The case goes
to `/mnt/user-data/outputs/` when that exists (otherwise the current directory), or wherever `--out` says.

## Hard rules

1. **No fabricated verification.** "Matched", "confirmed", "measured" and "±N m" must correspond to
   commands actually run and files actually produced here. If you did not do it, write "not verified".
2. **Record a first impression before reading tool output.** This is the anchor defence. Every later
   finding confirms, refines or overturns it, and an overturn records what caused it.
3. **Every clue gets a status and a lineage** (`IGL note`). The status caps its likelihood ratio (LR):
   `inferred` ≤3, `observed` ≤6, `reported` ≤10, `metadata` ≤20, `read`/`computed` ≤50, `matched` ≤100.
   OCR output and engine labels are `reported` until you verify them on a zoomed crop (then `read`).
4. **Independence means a different data lineage.** Searching a name an engine gave you and finding it
   in a database is circular, not corroboration. Two pages copying the same caption count once.
5. **List the whole category before choosing.** Put every branch of the chain, every hotel of the brand
   in the city and every same-name venue on the board (`IGL geo poi/search --add`). Fame and size are
   never evidence.
6. **Metadata, hints and engine guesses are hypotheses.** When they conflict with the pixels, the image
   wins. Check for mirroring, cropping (EXIF thumbnail), editing and AI generation before trusting
   anything.
7. **Exclusion needs decisive evidence** (`read`, `computed` or `matched`, plus a file). Weaker clues can
   only down-weight (`link --against`). Exclude only as much as the evidence covers.
8. **Site level needs reference imagery.** HIGH at site level requires ≥3 independent invariant features
   matched against independent photos of the candidate (`IGL compare`, then a `matched` clue), or two
   decisive clues from different lineages. Write the falsification test (`cand --falsify`) before
   comparing.
9. **Discrete candidates are never averaged.** The answer is the top-ranked candidate. The others are
   alternatives with the test that would separate them.
10. **Exhaust before you settle; never loop.** Each core method must end as results, no_results or
    not_applicable (`IGL log`). A blocked or unavailable service closes that route only, so switch
    route. Never retry an unchanged failing request, and never solve CAPTCHAs or log in on anyone's
    behalf.
11. **People are not targets.** Use clothing, uniforms, badges and personal items only for what they say
    about the place. Never identify a person, never use face search, and treat appearance or ethnicity
    as weak, bias-prone context (LR ≤1.5, never an exclusion). On social media, search for the place,
    its text, its tags and the photo itself, never for people, and do not profile whoever posted the
    photo. Redact private names and home addresses in the report. For an identifiable private residence
    with no stated purpose, ask once what it is for. Without a legitimate purpose, stop at city or
    neighbourhood level and say why.
12. **Tidy outputs.** Keep only evidence that the ledger cites, and finish with `IGL finalize`.

## Workflow

Work in this order and record as you go. If a step settles the place early, still do verification
(steps 8–9) before answering.

**1. Intake.** `IGL init <photo>` copies the photo, reads every metadata channel, and writes the grid
view `E01` plus `input/metadata.json`. Strong metadata (GPS, location fields, UTC offset) is auto-noted.
Open E01 and the photo itself.

**2. First impression (anchor).** Before reading any further tool output, note the scene type, the
country cluster and the single strongest clue:
`IGL note <case> "First impression: ..." --kind hypothesis --status inferred --source image`.

**3. Machine perception.** `IGL scan <case>` runs multi-pass OCR with script probing, QR and barcode
decoding with payload interpretation (EMV payment, Swiss QR-bill, EPC, UPI, Wi-Fi, vCard, URLs, GTIN), and
text mining. It also writes overlapping sweep tiles to `.work/tiles/`. When text signals point to a
country, it prints a suggested re-run with that language pack (e.g. `--langs deu+eng`), because accents
and letters like ß or ł are lost otherwise.

**4. Systematic visual sweep.** Open every tile. Walk the checklist in
[references/indoor-clues.md](references/indoor-clues.md) zone by zone: ceiling, walls, windows, floor,
furniture, fixtures, objects, text. For each finding:
- `IGL crop <case> --cell C3:E4 --enhance auto --label socket` to keep a legible crop (also `--rotate`,
  `--flip`, `--enhance clahe|binarize`).
- `IGL note <case> "<what exactly>" --kind standard --status observed --source image --file E07`.

Describe shapes before naming things, and write negative clues too. Log
`IGL log <case> visual_sweep --status results --detail "..."`.

**5. Hard facts first.** Text read on a crop, decoded codes, phone numbers (`IGL lookup phone`),
domains, addresses, venue names, room signs, evacuation plans, certificates, receipts and tickets.
Wi-Fi names can be looked up with `IGL geo wigle --ssid ...` if the user provides a WiGLE key.
A named venue goes straight onto the board:
`IGL geo search "<name> <city>" --case <case> --add site --parent C#`, plus
`IGL geo wikidata "<name>" --details` for facts and Commons category.

**6. Narrow the country and region.** Intersect fixed standards and conventions. Each attribute is
independent, and together they shrink fast:
`IGL countries --plug G --currency £ --drive left --case <case> --clue N4`.
This adds and links country candidates. Use `--lang`, `--script`, `--calling`, `--tld`, `--week`,
`--clock`, `--temp`, `--paper` and `--emergency` as observed. `IGL lookup plugs` lists socket shapes.
Add regions and cities with `IGL cand` or `geo search --add` when the evidence points there.

**7. Scene playbook and retrieval.** Classify the scene and follow its playbook in
[references/scene-playbooks.md](references/scene-playbooks.md) (hotel, rental or home, restaurant, retail,
transit, venue or landmark, institution, vehicle, generic). Run every applicable retrieval route from
[references/search-playbook.md](references/search-playbook.md):
- Reverse image search on the full image, tight crops of distinctive objects (art, fixtures, decor), and
  a mirrored copy. `IGL revsearch <case> [--cell ..] [--flip]` automates Yandex and TinEye. Do Google
  Lens and Bing in your browser tool, or ask the user. Log each engine.
- Text search for distinctive strings and descriptive phrases in the local language(s).
- Social media, for the place and for the photo's original post:
  `IGL social search "<venue or distinctive text>" --case <case> --sheet 12` queries keyless open APIs
  (Bluesky, Flickr tags, Openverse, Mastodon hashtags, Lemmy). `IGL social links "<query>"` prints
  ready searches for Instagram, TikTok, X, Facebook, Reddit, YouTube, Pinterest, Xiaohongshu, Douyin,
  Weibo, VK, Naver and others. Open them in your browser tool, using only logins the user already
  has. Query in the local language too, and log each platform (`IGL log ... social_search --engine ..`).
- Source hunting: original post, caption, the rest of the photo set, watermark, photographer.
- Listings and review photos (hotel, rental, real estate, restaurant), maps photos, 360° tours, Commons
  (`IGL geo photos --at lat,lon --sheet 12`).
- Candidate enumeration with OSM (`IGL geo poi --brand ... --area ... --add site`, co-location
  `--near-tag`) and Wikidata (`IGL geo sparql`, templates in search-playbook.md).
- Window view or reflections, if any: treat that part as outdoor geolocation, estimate the floor, check
  the sun ([references/window-and-light.md](references/window-and-light.md)).

**8. Verify** ([references/verification.md](references/verification.md)):
- Write the falsification test on the top candidate.
- Collect independent reference imagery: official gallery, listings, maps photos, Commons, news.
- `IGL compare <case> --ref <url|file> [--cell ..]`, then compare invariant features only (windows,
  ceiling, columns, built-ins, floor pattern, fixed fittings, view).
- Record `matched` only for ≥3 distinct matches. Otherwise use `observed` or `reported` with a modest
  LR, and log `reference_match`.
- Then the consistency pass, logged as `consistency`: time zone at the candidate vs the EXIF offset
  (`IGL geo timezone --at .. --case ..`), season and daylight vs date, visible weather vs the
  recorded weather (`IGL geo weather --at .. --case ..`), language and standards vs country, sun
  direction (`IGL sun`), bearings to landmarks in the view (`IGL bearing`).
- Redo the key step once with a different crop or keywords. If the result moves by more than the
  claimed radius, lower the confidence.

**9. Decide and finish:**
- `IGL rank <case>` shows the per-level ranking and the confidence cap for each candidate.
- `IGL answer <case> C# --summary "<2-6 sentences of decisive reasoning>" [--confidence ..] [--radius ..]`
  records the answer and refuses a confidence above what the evidence supports. For a site it fills a
  missing address by reverse geocoding. For a coarse answer (country, region, city) without coordinates,
  it geocodes the name and sizes the radius from the area.
- `IGL check <case>` audits the case: core coverage, unlinked clues, contradictions, files, and caps.
  Fix every FAIL.
- `IGL finalize <case>` runs the check, writes REPORT.md and result.json, deletes `.work/`, and prunes
  uncited files.

Core methods that must be resolved (`IGL log <case> <method> --status results|no_results|not_applicable
--detail ...`): `metadata`, `visual_sweep`, `text_ocr`, `codes`, `standards`, `culture_style`,
`reverse_search`, `text_search`, `social_search`, `candidate_enum`, `reference_match`, `window_view`,
`consistency`. `init`, `scan`, `revsearch` and `social search` log their own attempts.

## Linking evidence (how the board decides)

- `IGL cand <case> "<name>" --level site --parent C# --at lat,lon --address "..."` creates a candidate.
  Pass an existing id instead of a name to update it.
- `IGL link <case> N# --for C#:LR [--against C#:LR] --why "..."` links a clue. Rough LR scale:
  1.5 weak lean · 3 suggestive · 6 strong observation · 10–20 strong documentary · 30–60 decisive · 100
  verified match. The status cap applies automatically.
- Support flows up the hierarchy: a matched site supports its city and country. Attach every site to its
  city, and every city to its country.
- At country level, unlisted countries stay in play as one block (`C* other countries`), so leaving a
  country off the board never excludes it.
- `IGL exclude <case> C# --by N# --why "..." --file E##` is only for decisive contradictions.
- Confidence caps are computed from the ledger. HIGH needs a decisive clue, ≥2 independent lineages, a
  share ≥0.80 and no unresolved strong contradiction (plus the site rule). MEDIUM needs a decisive clue
  or ≥2 lineages, with a share ≥0.50. Details: [references/evidence-and-confidence.md](references/evidence-and-confidence.md).

## Persistence and stopping

- Don't stop at the first plausible place. Do stop when the site is verified (HIGH) and consistency
  passes, or when every core method is resolved and no remaining feasible action could separate the
  candidates.
- When a site is not reachable, answer at the finest level rated MEDIUM or better. Give that level's
  coordinates and a radius that covers it, and list exactly what evidence is missing. Never invent a
  pin or a precision.
- The service catalogue, keys and fallbacks are in [references/sources-and-tools.md](references/sources-and-tools.md).
  A no_results answer is an observed absence. An unavailable or blocked service is not an absence.

## Final answer format (chat, in the user's language)

```
📍 <Place name> — <full address>
   <lat>, <lon> (WGS84) ± <radius> m · level: <site|city|...> · confidence: <HIGH|MEDIUM|LOW>
Why: <the 2-4 decisive evidence items, each with its source and how it was verified>
Alternatives: <runner-up(s) and the test that would separate them>   (omit if none)
Not verified / limits: <what could not be checked and why>
Case folder: <path> (REPORT.md has the full reasoning trail)
```

Quote source text (signs, captions) verbatim and translate it for the reader. If the photo looks
synthetic, staged or composited, say so prominently, because the location may not exist.

## References

| File | Read when |
|---|---|
| [references/indoor-clues.md](references/indoor-clues.md) | step 4-6: the full indoor clue catalogue with what each clue implies |
| [references/scene-playbooks.md](references/scene-playbooks.md) | step 7: per-scene fastest routes, reference-photo sources, pitfalls |
| [references/search-playbook.md](references/search-playbook.md) | step 7: reverse, text and social search, source hunting, listing platforms per country, OSM, Wikidata SPARQL |
| [references/window-and-light.md](references/window-and-light.md) | any window, door, reflection or sunlight in the frame |
| [references/verification.md](references/verification.md) | step 8: falsification, invariant features, consistency, final checklist |
| [references/evidence-and-confidence.md](references/evidence-and-confidence.md) | statuses, lineages, LR scale, caps, radius, wording |
| [references/sources-and-tools.md](references/sources-and-tools.md) | service catalogue, optional API keys, browser use, etiquette and ToS |
