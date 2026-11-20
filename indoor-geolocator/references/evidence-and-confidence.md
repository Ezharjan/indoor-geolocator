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
| `read` | A | 50 | text you verified on a zoomed crop | "Hotel Sacher" on the notepad, crop E07 |
| `computed` | A | 50 | deterministic results | QR decode, phone prefix, sun angle, time-zone check |
| `matched` | A | 100 | same physical place confirmed by independent imagery | 3 invariant features match a traveller photo |

- OCR output starts as `reported`. Look at the crop yourself; if it reads the same, record `read`.
- Only `read`, `computed`, `matched` and `metadata` clues with LR ≥10 count as **decisive**.
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

LR = how much more likely this observation is if the candidate is right than if it is wrong. The scale
in SKILL.md: 1.5 weak lean · 3 suggestive · 6 strong observation · 10–20 strong documentary · 30–60
decisive · 100 verified match. The status cap clips what you request.

- **Link a set clue to every member of the set.** Type G sockets: `IGL countries --plug G --case <case>
  --clue N4` links N4 to all Type G countries with the same LR. It separates G countries from the others,
  not G countries from each other.
- **Named evidence goes to the named candidate.** "Hotel Sacher" read on stationery: LR 30–50 for that
  hotel; other hotels stay at 1 (portable stationery: see indoor-clues.md §18).
- **Against:** `--against C7:3` multiplies C7 by 1/3. Use it for a mismatch that is not decisive.
- **Do not double count.** One observation is one clue: the logo and the name on the same sign are one
  clue. Three items with one theme (Moroccan lamp, rug and tiles) make one style clue with a modest LR.
- **Fame is not evidence.** Every candidate starts at the same prior. Population, popularity and "it is
  the famous one" never raise an LR.

## 4. Ranking and shares

Within each level (country › region › city › district › site › room), every open candidate starts equal.
Each linked clue multiplies its odds by its LR. Shares are the normalised odds of the open
candidates. **Support flows up**: a site's clues also support its city and country (each clue counted
once per candidate). **Refutation does not flow up**: a refuted site says nothing against its city.
Excluding a candidate excludes its descendants. Attach every site to its city and every city to its
country, or support cannot flow.

**Countries off the board still count.** At country level, the countries you have not listed compete as
one block, `C* other countries (N not on the board)`, with a prior equal to their number and no
evidence. Omitting a country never excludes it. A Type B socket (LR 6 for the 55 Type B countries)
leaves about 37 % on "other countries", and only further independent clues (script, currency,
reference match) concentrate the share. Add country candidates by their common names (`cand
"South Korea" --level country`), so they map to the tables. Duplicates are refused.

## 5. Confidence caps (computed by `IGL rank` / `answer` / `check`)

| Tier | Requires |
|---|---|
| **HIGH** | a decisive clue · ≥2 independent lineages with LR ≥2 · share ≥0.80 · no unresolved strong contradiction · at site or room level also a `matched` clue, or decisive clues from ≥2 lineages |
| **MEDIUM** | a decisive clue or ≥2 independent lineages, and share ≥0.50 |
| **LOW** | anything else |

`answer` refuses a confidence above the cap. You may always report less (and should, when the
consistency pass or the re-run raised doubts the ledger cannot express). The reported overall confidence
is the finest level rated MEDIUM or better. A weak room level does not drag down a strong site, and the
answer states which level the confidence applies to.

## 6. Contradictions

A finding that conflicts with the leading hypothesis gets its own clue, linked against the candidate it
contradicts:

```
IGL note <case> "EXIF offset +09:00 but candidate is in UTC+01:00" --kind contradiction --status computed --source geometry
IGL link <case> N12 --against C5:3 --why "time zone mismatch"
```

Resolve it with evidence (`IGL note ... --resolves N12`: e.g. the camera clock kept a previous trip's
time zone, shown by other metadata). Or leave it open:
- an unresolved contradiction linked against the answer with LR ≤0.5 and status `read`, `computed` or
  `matched` blocks HIGH;
- every unresolved contradiction is flagged by `check` and listed in the report.

## 7. Wording and radius

| Tier | Say | Means |
|---|---|---|
| HIGH | "verified", "confirmed" | you would be surprised to be wrong; independent lines agree and the site is matched |
| MEDIUM | "probably", "likely" | more likely right than wrong; at least one strong line, the rest consistent |
| LOW | "possibly", "best guess" | a lead to check, not a finding |

The radius covers the uncertainty at the answered level (verification.md §7). Defaults: room 30 m · site
60 m · district 1.5 km · city 8 km · region 80 km · country 400 km. Use the real extent when you know
it (a 2 km airport needs more than 60 m). Words like "matched", "confirmed", "measured" and any "±N m"
must point to ledger entries made in this session (hard rule 1).
