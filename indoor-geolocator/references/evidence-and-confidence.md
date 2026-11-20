# Evidence and confidence

How the ledger turns observations into a ranking and a confidence. The rules live in code
(`scripts/iglib/case.py`, `scoring.py`): you supply honest statuses, lineages and likelihood ratios,
and the tools compute the shares and caps.

## 1. Status: how a clue was obtained (caps its likelihood ratio)

| Status | Grade | LR cap | Use for | Example |
|---|---|---|---|---|
| `inferred` | D | 3 | reasoning, style, taste | "décor looks Scandinavian" |
| `observed` | B | 6 | a feature you can point at | "Type G socket at C4", "tilt-and-turn window" |
| `reported` | C | 10 | third-party statements and unverified machine reads | listing caption, engine label, raw OCR line, social location tag |
| `metadata` | B | 20 | embedded in the file (editable) | EXIF GPS, XMP City, UTC offset |
| `traced` | B | 20 | the same photograph found on a page that says where it was taken | a COPY in the hotel's own gallery, on its listing, in the photographer's post |
| `read` | A | 50 | text you verified on a zoomed crop | "Hotel Sacher" on the notepad, crop E07 |
| `computed` | A | 50 | deterministic results | QR decode, phone prefix, sun angle, time-zone check |
| `matched` | A | 100 | same physical place confirmed by independent imagery | 3 invariant features match a traveller photo |

- OCR output starts as `reported`. Look at the crop yourself; if it reads the same, record `read`.
- `matched` is the strongest status, so it has to be auditable: `--features` with at least three named,
  specific, invariant features, and the comparison behind it (`--file` of a `compare`, `refs` or
  `revsearch` artefact, or `--url` of a reference you could only view in a browser tool). A comparison
  whose references are all copies of the photo is refused.
- `traced` is provenance, and it is auditable too: `--url` of the page, and (when a tool found it) the
  `revsearch`, `refs` or `compare` file that classed the picture as a COPY; a file without a COPY is
  refused, because a similar picture is not a trace. Weigh it by the page: the venue's own site, its
  listing, or the photographer's own post naming the place, LR 10–20; an aggregator, a pin board or a
  repost, `reported` with LR ≤6. If copies sit on pages that name different venues (stock pictures,
  one brand photo used for many branches), link the clue to every venue named: the share splits, as
  it should.
- **Engine leads are capped at 3.** A clue with source `engine` (a reverse-image label, the title of a
  similar image, an AI estimator) carries at most LR 3 unless its status is `metadata`, `read`,
  `computed` or `matched`: engines list look-alikes beside real matches. Verify the place and record
  that instead.
- Only `read`, `computed`, `matched`, `metadata` and `traced` clues with LR ≥10 count as **decisive**.
- Only `read`, `computed` and `matched` can **exclude** a candidate (`IGL exclude`, with a file).
  Everything weaker can only down-weight (`link --against`).

## 2. Source: the lineage of the observation (decides independence)

| Source | Meaning |
|---|---|
| `image` | things seen in the photo: objects, fittings, standards, style |
| `text` | text and codes in the photo (signs, labels, QR payloads, phone numbers) |
| `metadata` | the file's metadata |
| `web` | pages, captions, listings, social posts, reviews |
| `engine` | reverse-image and AI engines' labels and guesses |
| `map` | OSM, geocoders, Wikidata facts about places |
| `reference` | independent photos of a candidate, compared with this photo |
| `geometry` | sun position, bearings, time-zone and floor computations |
| `table` | a fact taken from the offline tables themselves (rare: it adds no independence to the clue it was derived from) |
| `user` | hints from the user |

Record the lineage of the **observation**, not of the lookup. A socket you saw is `image`, even though
`countries` maps it with a table. A phone number you read is `text`, even though the prefix lookup is a
table.

**Independence rules:**
1. Count lineages, not clues. Five décor clues are one `image` lineage, never five confirmations.
2. A clue found *by following a lead* inherits that lead's lineage unless it brings new content. The
   engine says "Hotel X" and the hotel's website describes Hotel X: still one lead, and the website text
   confirms nothing about the photo. Comparing the website's photos with the photo is new content
   (`reference`).
3. Pages that copy one caption or one photo count once. Your own photo found online is provenance, not
   confirmation.
4. Geocoding a name you read adds coordinates, not independence (`text` + map lookup = one lineage).
5. Correlated observations share an error. If the image could be staged or composited, every
   `image` and `text` clue fails together, which is why HIGH needs a second lineage (`reference`,
   `metadata`, `geometry`, `web`).

## 3. Likelihood ratios (LR)

LR = how much more likely this observation is if the candidate is right than if it is wrong. The scale:
1.5 weak lean · 3 suggestive · 6 strong observation · 10–20 strong documentary · 30–60 decisive · 100
verified match. The status cap clips what you request.

There are two kinds of clue, and the ledger weighs them differently (section 4):

- A **category clue** fits a kind of place: a socket type, a language, a style, a chain's furniture.
  Its LR compares the candidate with one typical alternative, and it stays below 10.
- An **identifying clue** points at one place: its name read in the photo, a decoded code, GPS, a
  traced copy, a matched reference photo. From LR 10 upward the number is the odds that the
  identification is sound: LR 50 says "about 50 to 1 that this is the place". What limits it is how the
  reading or the comparison could have failed (portable stationery, a namesake, a look-alike), never the
  number of other places in the world.

- **Link a set clue to every member of the set.** Type G sockets: `IGL countries --plug G --case <case>
  --clue N4` links N4 to all Type G countries with the same LR. It separates G countries from the others,
  not G countries from each other.
- **Named evidence goes to the named candidate.** "Hotel Sacher" read on stationery: LR 30–50 for that
  hotel; other hotels stay at 1 (portable stationery: see indoor-clues.md section 18).
- **Against:** `--against C7:3` multiplies C7 by 1/3. Use it for a mismatch that is not decisive.
- **Do not double count.** One observation is one clue: the logo and the name on the same sign are one
  clue. Three items with one theme (Moroccan lamp, rug and tiles) make one style clue with a modest LR.
- **Fame is not evidence.** Every candidate starts at the same prior. Population, popularity and "it is
  the famous one" never raise an LR.

## 4. Ranking and shares

Every open candidate starts from the same prior. Each linked clue multiplies its odds by its LR. Shares
are normalised probabilities, computed coarse to fine:

- **Country level**: all countries on the board plus one block, `C* other countries (N not on the board)`,
  with a prior equal to their number and no evidence. Omitting a country never excludes it. A Type B socket
  (LR 6 for the ~55 Type B countries) leaves about 37 % on the block; only further independent clues
  (script, currency, a phone prefix, a reference match) concentrate the share.
- **Every finer level**: the children of one parent compete with one block of **unlisted alternatives
  under that parent** (prior 1). A lone city without evidence holds half of its country, not all of it,
  so a candidate can never become certain just because nothing else was put on the board.
- **Decisive clues are weighed against the whole field.** A candidate holding a decisive clue (marked
  `*` by `rank`) competes with everything else at its level as one alternative: listed rivals and the
  unlisted block together. A verified hotel is therefore not diluted by the 249 countries nobody listed,
  nor by the forty other hotels you enumerated in its town; it keeps about LR/(LR+1) at each level
  (80 → 0.99) unless a rival has evidence of its own. Category clues keep competing with every
  alternative separately.
- **Coherence**: a child's `share` is its share among its siblings (`within`, `cond` in the JSON) times
  its parent's share. A city can never look more certain than its country, nor a hotel than its city.
  `IGL rank` prints both numbers. A candidate without a parent hangs under the unlisted block of the
  level above it, because the board does not know where it is: its share is then far too small. Attach
  every site to its city and every city to its country (`check` warns).

**What flows up.** Documentary and verified clues (status `reported`, `metadata`, `traced`, `read`,
`computed`, `matched`) linked to a site also support its city and country, each clue counted once per
candidate. A name read on the key card supports the hotel, its city and its country. Visual category clues (status
`observed`, `inferred`: "the chain's furniture", "Scandinavian style") do **not** flow up: they fit every
branch of the chain in every city, and letting them flow would reward whichever city you happened to
enumerate (enumeration bias). Link such clues directly to every level they speak to. Refutation does not
flow up: a refuted site says nothing against its city. Excluding a candidate excludes its descendants.

**Consequences worth knowing.**
- Category clues alone need several independent ones to settle a country (one country against ~250):
  intersect them with `IGL countries ... --case --clue` (sockets, script and language, currency, calling
  code, driving side ...). It is cheap, it is the second lineage that turns MEDIUM into HIGH, and it is
  the consistency check that catches a look-alike in the wrong country.
- One decisive clue gives its whole chain a high share: the venue, its city and its country. The share
  is then no longer what holds the confidence back. The tier is (section 5): a single lineage is
  MEDIUM, and a reference match without a rival control is MEDIUM.
- A caption or location tag (`reported`, ≤10) is never decisive. On its own it leaves a venue LOW, a
  lead to verify with `refs`.
- A hit that the tools class COPY is the photo itself: what its page says is a `traced` clue (source
  `web`), and never a `matched` clue. Traced provenance plus one independent matching photo is two
  decisive lineages: HIGH.
- Record each independent reference comparison as its own `matched` clue (different photographers or
  sources; `refs` and `compare` flag references that are one photograph, which count once).
- Add country candidates by their common names (`cand "South Korea" --level country`) so they map to the
  tables. Duplicates are refused.

## 5. Confidence caps (computed by `IGL rank` / `answer` / `check`)

| Tier | Requires |
|---|---|
| **HIGH** | a decisive clue · ≥2 independent lineages with LR ≥2 · share ≥0.80 · no unresolved strong contradiction on the chain · a reference match counts here only with its rival control, or beside a decisive clue of another lineage · at site or room level: a controlled `matched` clue, or decisive clues from ≥2 lineages |
| **MEDIUM** | share ≥0.50 and a decisive clue. Above site level, ≥2 independent lineages also suffice |
| **LOW** | anything else |

Shares are the coherent shares of section 4, so a HIGH site needs a strong city and country above it.

**The rival control.** A `matched` clue says "three specific features agree". Whether those features
are specific is an empirical question, and the test is the closest alternative: another branch, the
venue next door, the look-alike an engine proposed. So a match recorded for a venue supports HIGH only
when the reference photos of at least one other venue were examined too: `refs` or `compare` ran with
`--for <rival>`, or a clue of the `reference` lineage speaks for or against a rival (how a comparison
made in a browser tool is recorded). Without it the tier stays MEDIUM, and `rank`, `answer` and the
report say what is missing. The control is not needed when a second decisive lineage identifies the
same venue (its name read in the photo, GPS, a traced copy).

**A design match belongs to an area, not to a venue.** When the rival's photos show the same features,
the features are a shared design: a chain's room package, a hotel group's furniture, a franchise fit-out.
Record the `matched` clue for the smallest candidate that contains every venue with that design (the
district of the two sister hotels, the city, for a national chain the country), keep the venues as
leads, and say so in the answer. `check` warns when a venue is matched while a rival's photos were
classed SAME SCENE too, and when an area-level match has fewer than two venues' photos on file.

**A venue needs a decisive clue.** At site and room level, two agreeing weak lineages (it looks like the
gallery, an engine listed it, a booking page describes such a room) stay LOW however high the share:
that combination is exactly what a look-alike produces. The decisive clue is the venue's name read in
the photo, a decoded code, GPS metadata, a traced copy, or a `matched` comparison.

**One chain, consistent tiers.** An unresolved strong contradiction against a place (a `read`, `computed`
or `matched` clue linked against it with LR ≤0.5) blocks HIGH for the place and for everything inside
it: a time zone that contradicts the country also stands against the hotel. And a place is rated at
least as high as the best-rated place inside it: if the hotel is verified, so are its city and country.

`answer` refuses a confidence above the cap. You may always report less (and should, when the
consistency pass or the re-run raised doubts the ledger cannot express).

**Answer, lead and pin.** The answer is the finest level rated MEDIUM or better. A candidate rated LOW
under a coarser level that is MEDIUM or better is a **lead**, not an answer: `answer` refuses it and
tells you to answer at the verified level with `--lead C#`. The report and result.json show the lead in
its own field, with its share and its falsification test, and the chat answer gives it its own line
("Best lead (unverified)"). The **pin** (`best_estimate` in result.json) is the single most likely
point: the lead's coordinates when there is one, otherwise the answer's. A lead inside the verified area
is a better point estimate than the centre of that area; what is claimed as verified stays the answer
with its radius. When every level is LOW, the answer is the best guess and must be worded as one.

## 6. Contradictions

A finding that conflicts with the leading hypothesis gets its own clue, linked against the candidate it
contradicts:

```
IGL note <case> "EXIF offset +09:00 but candidate is in UTC+01:00" --kind contradiction --status computed --source geometry
IGL link <case> N12 --against C5:3 --why "time zone mismatch"
```

Resolve it with evidence (`IGL note ... --resolves N12`: e.g. the camera clock kept a previous trip's
time zone, shown by other metadata). Or leave it open:
- an unresolved contradiction linked against the answer or any place above it, with LR ≤0.5 and status
  `read`, `computed` or `matched`, blocks HIGH;
- every unresolved contradiction is flagged by `check` and listed in the report.

## 7. Wording and radius

| Tier | Say | Means |
|---|---|---|
| HIGH | "verified", "confirmed" | you would be surprised to be wrong; independent lines agree and the site is matched |
| MEDIUM | "probably", "likely" | more likely right than wrong; at least one strong line, the rest consistent |
| LOW | "possibly", "best guess" | a lead to check, not a finding |

The radius covers the uncertainty at the answered level (verification.md section 11). Defaults: room 30 m · site
60 m · district 1.5 km · city 8 km · region 80 km · country 400 km. Use the real extent when you know
it (a 2 km airport needs more than 60 m). Words like "matched", "confirmed", "measured" and any "±N m"
must point to ledger entries made in this session (SKILL.md: no fabricated verification).
