---
name: indoor-geolocator
description: Find where an indoor photo was taken (hotel room or lobby, rental, home, restaurant, cafe, bar, shop, mall, office, school, hospital, station, airport, museum, church, vehicle interior) from one image. Returns the venue name, street address and latitude/longitude with an error radius and a rules-capped confidence, plus a tidy case folder tracing every step. Reads every channel - metadata, all visible text, QR codes and barcodes, fixed standards (sockets, switches, fittings, safety signs), style, customs, products, artwork, window views - finds candidates by reverse image search (Yandex, TinEye, Baidu; Google Lens and Bing by URL), web, listing and social media search, maps and OSM, then VERIFIES them by collecting reference photos of each candidate and comparing them with the photo, so a look-alike is never reported as the place. Use whenever a user shares an interior photo and asks where it is, which hotel, restaurant or building it shows, asks to geolocate it, or attaches the image with no other prompt.
license: MIT
---

# indoor-geolocator

**Goal: the most accurate location the evidence can support, proven step by step.** Accuracy beats speed:
keep going through every applicable route until a candidate is verified or every feasible route is
exhausted. A precise answer that is wrong is worse than a coarser answer that is right, so the headline
answer is the finest level the evidence verifies, and an unverified finer guess is reported separately
as the best lead.

## Why indoor photos get located wrongly (and what this workflow does about it)

Almost every wrong answer is one of these. Keep them in mind at each step.

1. **A look-alike is taken for the place.** Reverse image search and web search return rooms that
   *resemble* yours, with a venue name attached. Hotel lounges, chain rooms and cafés resemble hundreds
   of others. *Countermeasure:* a venue is only named after its own photos have been put next to yours
   and specific fixed features agree, and it is only called verified after a rival went through the
   same comparison (step 5). Resemblance, an engine label or a caption make a lead.
2. **The first plausible or famous candidate is kept.** *Countermeasure:* hypotheses are written
   before tools run, every venue of the kind in the area goes on the board, and the runner-up gets the
   same comparison as the favourite.
3. **Machine output is read as fact.** OCR "reads" carpets and ornaments (often as an exotic
   script), engines guess, a search that never started looks like "no results". *Countermeasure:* the
   tools filter and label their own output; you read text yourself on crops; "unavailable" and "blocked"
   never mean "nothing found".
4. **Portable things are read as the building.** A pen, a mug, a souvenir, an imported socket
   adapter travel. *Countermeasure:* fixed infrastructure outranks movable objects.
5. **A brand is taken for a branch.** Chains clone interiors. *Countermeasure:* the brand is a
   category; the branch needs a property-specific feature (the view, the layout, local art).
6. **Precision is invented.** *Countermeasure:* the confidence is capped by rules in code, and an
   unverified site is a lead with its own line, never the answer.

## What you deliver

1. In chat, in the user's language: the answer block (format at the end).
2. One case folder, nothing written anywhere else: `REPORT.md` (human report) · `result.json` (machine
   result) · `case.json` (complete ledger) · `input/` (byte-exact photo + metadata.json) · `evidence/` (only
   the files the ledger cites). Scratch lives in `.work/` and is deleted by `finalize`.

## Tools

`IGL` means `python3 "<skill dir>/scripts/igl.py"`, where `<skill dir>` is the folder holding this SKILL.md
(Claude Code sets `${CLAUDE_SKILL_DIR}`; otherwise use the absolute path; on Windows `python`). Python
3.9+ and Pillow are required (`pip install -r requirements.txt`). The optional extras
(`requirements-optional.txt`) add methods, and three of them matter for accuracy: `opencv-python-headless`
(with numpy), `playwright` with Chromium, and `onnxruntime` (it sorts reference pictures by likeness to
your photo). Install them once per environment if `IGL init` reports them missing. `IGL <command> -h`
shows every option. Give the shell a generous timeout (`scan`, `revsearch`, `refs` can take a minute or
two).

Three tool families; use all that exist, none replaces the others.

| Need | First choice | Also |
|---|---|---|
| Metadata, codes, crops, tiles, standards tables, sun, bearings, the ledger | `IGL` (offline) | — |
| Reading text in the photo | **your own eyes on the tiles and crops** | `IGL scan` (OCR hints, precision-filtered) |
| Reverse image search | `IGL revsearch` (Yandex, TinEye, Baidu; every hit compared with the photo) | **Google Lens and Bing in your browser tool** via the links `revsearch` / `IGL share` print |
| Text search: names, strings, descriptions, listings, social posts | **your own web search tool**, many queries, local languages | `IGL social search`, `IGL social links` |
| Reading a page | **your own web fetch tool** or browser | `IGL snapshot` to keep it as evidence |
| Pictures of a candidate, or of every venue of a kind in an area, compared with the photo | `IGL refs` (image search + gallery pages; sheets sorted most similar first), `IGL compare` | maps photos, listing galleries and social posts in your browser tool |
| OSM, geocoding, Commons, Wikidata, weather, time zone | `IGL geo ...` | your fetch tool on `IGL geo ... --print-url` |

`IGL init` reports what the CLI can reach from here. Cloud sandboxes share addresses that public
services rate-limit, so a command may answer "unavailable" or "rate-limited": switch route (the command
says how) and never record that as "no results". The photo must be a file: in claude.ai or Cowork,
attachments are under `/mnt/user-data/uploads/`. The case folder goes to `/mnt/user-data/outputs/` when
that exists (otherwise the current directory), or wherever `--out` says.

## Workflow

Record as you go, one call per finding: `IGL note <case> "<what exactly>" --kind K --status S --source L
[--file E##] [--for C#:LR --why "..."]`. Spend your effort on steps 4 and 5; the ledger is the trace,
not the work. Run independent tool calls in parallel where your environment allows it.

**1. Intake.** `IGL init <photo>` copies the photo, reads every metadata channel (GPS, time and UTC offset,
XMP/IPTC places, thumbnail, C2PA, filename pattern) and writes the grid view `E01`. Strong metadata is
recorded automatically; it is still a hypothesis until the pixels agree.

**2. Look, and commit to hypotheses before any tool output.** Open the photo and E01. Note the scene
type and 2-4 ranked hypotheses at whatever level you can (country cluster, city, chain, a specific venue
you think you recognise), each with its reason and what would tell them apart:
`IGL note <case> "Hypotheses: scene=...; 1) ... because ...; 2) ...; would discriminate: ..." --kind
hypothesis --status inferred --source image`. Naming a venue from memory is welcome here; it is a
candidate to test in step 5 like any other.

**3. Read the whole photo.** `IGL scan <case>` runs OCR, decodes QR codes and barcodes (payment QR,
Wi-Fi, URLs, GTIN), mines the text and writes overlapping tiles. Open **every** tile and walk
[references/indoor-clues.md](references/indoor-clues.md). You are looking for three kinds of thing:
- **Identity carriers**: anything that names the venue or exists only there. Text (names, phone numbers,
  URLs, Wi-Fi names, room signs, evacuation plans, certificates, receipts), logos, uniforms, a unique
  artwork, sculpture, mural or custom carpet, distinctive architecture, the view through a window.
- **Region evidence** that is fixed to the building: sockets and switches, plumbing, heating and cooling,
  windows, mandated safety signs, script and language, currency, tax words, units, floor numbering.
- **Local references**: a painting or photo of a local landmark, a map, a local newspaper, a tourist
  leaflet, a calendar from a nearby business, regional products. They often give the town.
Crop what matters (`IGL crop <case> --cell C3:E4 --enhance auto --label socket`, also `--rotate`, `--flip`),
read every text yourself on the crop, describe shapes before naming things, note what is absent.
OCR lines are hints: an empty OCR result is normal for a room and proves nothing. Log the sweep:
`IGL log <case> visual_sweep --status results --detail "zones covered; what stood out"`.

**4. Narrow the region, then find candidates.** Do every route that applies; they are listed by how
often they decide a case.

- **a. Names and numbers** read in the photo: search each in quotes, in the original script, with your web
  search tool; `IGL lookup phone "+43 1 234567"`; then `IGL geo search "<name> <city>" --case <case> --add
  site --parent C#`. Check same-name venues and whether the item is portable (a pen proves little).
- **b. Reverse image search**: `IGL revsearch <case>` on the full frame, then on 2-4 tight crops of the
  identity carriers (`--cell C2:D3`, artwork, sculpture, ceiling, carpet, the view) and a mirrored copy
  (`--flip`). Every hit is compared with your photo and classed: **COPY** (the same photograph:
  provenance, open the page and read caption, date and location tag), **SAME SCENE** / **PARTIAL**
  (matching structure: the strongest leads), **unconfirmed** (no automatic match; shown most similar
  first). Unconfirmed is not "different": feature matching misses real photos of the same room from
  another year or angle, so **open the ranked sheet and judge by eye**; and it is not "the place"
  either: engines list look-alikes beside real matches. What many hits share (a country, a region, a
  kind of venue, a brand) is a fair lead for the region even when none of them is the place. If you have
  any browser tool, also open the Lens and Bing links (from `revsearch` or `IGL share <case> [--cell
  ..]`): Google Lens has the largest index of interiors and listings. Feed promising result images back
  with `IGL refs <case> --image <url>`.
- **c. Region from independent fixed standards.** One standard never settles a country: intersect at
  least two (`IGL countries --plug G --case <case> --clue N4`, then `--currency`, `--lang`, `--script`,
  `--calling`, `--tld`, `--drive`, `--week`, `--clock`, `--temp`, `--paper`, `--emergency`).
  `IGL lookup plugs` lists socket shapes. Add regions and cities as the evidence reaches them, each
  attached to its parent. Style and taste alone are weak (they travel).
- **d. Describe and search.** With your web search tool: the distinctive features plus the scene type
  and region, in the local language too (`hotel bar "snake sculpture" New Mexico`). And as pictures:
  `IGL refs <case> "<scene type> <region>" "<scene type> <distinctive feature> <town>"` collects web
  images of many venues and sorts them by likeness to your photo. The top of the first sheet is where
  the venue itself turns up, named by its page, even when no text describes it. Run it as soon as you
  have a region, and again for every narrower area.
- **e. Enumerate the category.** Once the town or district is likely but the venue is not, list every
  venue of the kind there (`IGL geo poi --tag tourism=hotel --area "<town>" --case <case> --add site
  --parent C#`, your web search for "<kind> in <town>", the brand's own list, booking and map listings)
  and screen each with `IGL refs <case> "<venue> <town> <room type>" --for C#`. A town has few hotels;
  looking at all of them beats guessing among them.
- **f. Social media and listings** for the place, its text and the photo
  ([references/search-playbook.md](references/search-playbook.md)); per-scene shortcuts are in
  [references/scene-playbooks.md](references/scene-playbooks.md); any window, view or sunlight:
  [references/window-and-light.md](references/window-and-light.md).

Log what you did: `IGL log <case> text_search,social_search,candidate_enum --status results --detail
"..."` (`revsearch`, `refs` and `compare` log themselves).

**5. Verify: the gate between a lead and an answer**
([references/verification.md](references/verification.md)). For the favourite **and** its closest rival:

1. Write what must be true and what would rule it out, before looking:
   `IGL cand <case> C# --falsify "If C#: ...; ruled out by: ..."`.
2. Collect its photos: `IGL refs <case> "<venue> <city> <room type>" "<venue> <city> lobby" --url
   <its gallery or listing page> --for C#`. The sheets show your photo first, then the references, most
   similar first.
3. Compare **specific fixed features** by eye, listing them for your photo first: the shape, count and
   position of windows and doors, the ceiling, columns, beams, built-ins, staircases, floor patterns in
   public areas, fixed fittings, the view, and art or sculpture made for the venue. Furniture, bedding,
   lamps and mass-produced prints only prove a design or a brand. Then
   `IGL compare <case> --refs E## --pick 3,7 --for C#` for a large side-by-side (add `--cell` to compare one
   feature; `IGL crop <case> --of E## --rel x0,y0,x1,y1` zooms into a reference).
4. Decide honestly. Three or more specific features agree and no fixed feature disagrees: record it,
   naming them, `IGL note <case> "Matches <source, year>: ..." --kind match --status matched --source
   reference --file E## --features "feature 1; feature 2; feature 3" --for C#:60 --why "..."`. One or two
   agree: `--status observed`. Only the style agrees: nothing was verified, the candidate stays a lead.
   A fixed feature disagrees in every photo of the venue: record it `--against`.
5. Run the same comparison for the closest rival (`refs ... --for <its C#>`): HIGH needs this control.
   If the rival's photos show the same features, they are a **shared design** (a chain, a hotel group,
   one supplier), not a place: record the match for the smallest area or group that holds every venue
   with that design (`--for <the district or city C#>`), keep the venues as leads, and look for a
   feature only one of them has (the view, the room's shape, local art).

Two other things identify a venue. Text you read in the photo that names it (on something fixed or owned
by the venue) is decisive on its own; still make one visual check when photos of it exist, because
objects travel. And a **COPY**: the same photograph on the venue's own page, its listing or the
photographer's post is recorded as `--kind provenance --status traced --source web --url <page> --file
E## --for C#:15`. It makes the venue probable; one independent photo that matches makes it verified.
Copies on pages that name different venues identify a stock picture or a brand, nothing more.

**6. Consistency and a second look.** Check the leading candidate against everything independent of how
it was found, and log it as `consistency`: the EXIF offset against its time zone (`IGL geo timezone`),
season, daylight and sun direction (`IGL sun`), weather (`IGL geo weather`), standards against its
country, and whether the venue existed and looked like this at the capture date. Then argue for the
runner-up: what would make it win? Re-run the deciding step once differently (another crop, query or
reference). If anything moved, lower the confidence or widen the radius.

**7. Decide and finish.**
- `IGL rank <case>` shows every level: `share` is the probability of the whole chain, `C*` the
  alternatives not on the board, `cap` the confidence the rules allow.
- `IGL answer <case> C# [--lead C#] --summary "<2-6 sentences of decisive reasoning>" [--radius ..]`
  answers at the finest level rated MEDIUM or better. It refuses a confidence above the cap and a LOW
  site under a verified town: pass that site as `--lead`. Its coordinates then become the `PIN`, the
  single most likely point, while the verified statement stays the town with its radius. Coordinates
  come from the candidate (`--at lat,lon`, or geocoding); for a site use the building itself, not the
  street or the town centre.
- `IGL check <case>` audits coverage, unlinked clues, contradictions, the comparisons behind a site and
  the traps it can detect. Fix every FAIL and read every WARN.
- `IGL finalize <case>` writes REPORT.md and result.json, deletes `.work/` and prunes uncited files.

## What counts as evidence

- Every clue has a **status** that caps its weight (LR): `inferred` ≤3, `observed` ≤6, `reported` ≤10,
  `metadata`/`traced` ≤20, `read`/`computed` ≤50, `matched` ≤100. OCR output and captions are `reported`
  until you verify them on a crop (then `read`). An engine's label or the title of a similar image
  (source `engine`) is a lead, capped at 3 until you have verified the place yourself.
- **Decisive** clues are `read`, `computed`, `matched`, `metadata` or `traced` with LR ≥10: they identify
  one place, where the others only fit a kind of place. A site or room needs one to be more than a
  lead. `matched` needs `--features` with three named features and the comparison file (or `--url` of
  a reference you could only view in a browser tool); a COPY of the photo is provenance (`traced`,
  with the page's `--url`) and is refused as a match.
- A decisive clue is weighed against all alternatives together: LR 50 means about 50:1 that this is the
  place, however many rivals are on the board. Weaker clues compete with every alternative one by one
  (a socket type fits fifty countries), so only several of them together settle a country.
- **Independence** means a different lineage (image, text, metadata, web, engine, map, reference,
  geometry). Five décor clues are one lineage. Searching an engine's guess and finding it in a database
  is circular.
- The board is open: unlisted alternatives always keep a share, so a lone candidate is never certain.
  Fame and size are not evidence. Exclude only with decisive evidence (`IGL exclude`, with a file);
  weaker clues only down-weight (`--against`).
- Caps (computed by `rank`, `answer`, `check`): **HIGH** = a decisive clue, ≥2 independent lineages,
  share ≥0.80 and no unresolved strong contradiction anywhere on the chain. A reference match carries
  HIGH only with its rival control or beside a decisive clue of another lineage, and a site needs
  exactly that: a controlled match, or decisive clues from two lineages. **MEDIUM** = share ≥0.50 and a
  decisive clue (above site level two independent lineages also suffice). Everything else is **LOW**.
  Details: [references/evidence-and-confidence.md](references/evidence-and-confidence.md).

## Persistence and stopping

- Do not stop at the first plausible place, and do not stop because one tool failed: a blocked or
  unreachable service closes that route only. Never retry an unchanged failing request, never solve
  CAPTCHAs, never log in on anyone's behalf.
- Before settling for a coarse answer, make sure you have tried: your own reading of every tile;
  reverse search on the full frame and on crops, on at least two engines, plus Lens when a browser tool
  exists; exact-string and describe-and-search queries in the local language; enumeration of the
  category in the likely town with `refs` on each; the window view.
- Stop when the answer is verified and consistent, or when no remaining feasible action could separate
  the candidates. Then answer at the finest level rated MEDIUM or better with a radius that covers it,
  pass the best site as `--lead`, and list exactly what evidence is missing.
- Services, keys and fallbacks: [references/sources-and-tools.md](references/sources-and-tools.md).

## People, privacy and conduct

- People are not targets. Use uniforms, badges and personal items only for what they say about the
  place. Never identify a person, never use face search, never profile a poster; treat appearance or
  ethnicity as weak, bias-prone context (LR ≤1.5, never an exclusion). On social media search for the
  place, its text and the photo itself.
- Redact private names and home addresses. For an identifiable private residence with no stated
  purpose, ask once what it is for; without a legitimate purpose stop at city or neighbourhood level and
  say why. Listings and public venues are fine.
- Uploads are disclosed and minimal. `revsearch` sends the photo (metadata stripped) to the engines, and
  makes a temporary public copy only when an engine's upload form fails (`--no-share` forbids that);
  `share` always makes one. The report lists both. If the user marked the photo private, ask first.
  Prefer crops without people.
- No fabricated verification: "matched", "confirmed", "measured" and "±N m" must correspond to commands
  run and files produced in this session. If the photo looks synthetic, staged or composited (C2PA and
  AI markers from `init`, garbled text, impossible geometry), say so prominently: the place may not exist.

## Final answer format (chat, in the user's language)

```
📍 <Place name> — <full address>
   <lat>, <lon> (WGS84) ± <radius> m · level: <site|district|city|region|country> · confidence: <HIGH|MEDIUM|LOW>
Why: <the 2-4 decisive evidence items, each with its source and how it was verified>
Verified against: <reference photos compared, which features matched, which rival was tested>   (site answers)
Best lead (unverified): <finer candidate> at <lat>, <lon>: the single most likely point; <the test that would confirm it>   (omit if none)
Alternatives: <runner-up(s) with their share and the test that separates them>   (omit if none)
Not verified / limits: <what could not be checked and why, including routes that were blocked>
Case folder: <path> (REPORT.md has the full reasoning trail)
```

Quote source text (signs, captions) verbatim and translate it. Use 6 decimals for coordinates. Say
"verified" only for HIGH, "probably" for MEDIUM, "best guess" for LOW.

## References

| File | Read when |
|---|---|
| [references/indoor-clues.md](references/indoor-clues.md) | step 3: the indoor clue catalogue and what each clue implies |
| [references/search-playbook.md](references/search-playbook.md) | step 4: reverse, text, image and social search, provenance, listing platforms per country, OSM, Wikidata |
| [references/scene-playbooks.md](references/scene-playbooks.md) | step 4: per-scene fastest routes, where reference photos live, pitfalls |
| [references/window-and-light.md](references/window-and-light.md) | any window, door, reflection or sunlight in the frame |
| [references/verification.md](references/verification.md) | steps 5-6: the comparison protocol, what `refs` and `compare` report, traps, consistency, final checklist |
| [references/evidence-and-confidence.md](references/evidence-and-confidence.md) | statuses, lineages, LR scale, open board, shares, caps, leads, wording |
| [references/sources-and-tools.md](references/sources-and-tools.md) | tool routing, services and their failure modes, fallbacks, keys, uploads |
