# Verification

Workflow steps 5-6. A candidate is not an answer until its own photos have been compared with the
photo and it has survived an honest attempt to prove it wrong. The rules live in code
(evidence-and-confidence.md): without a decisive clue a site is a lead, and HIGH at site level needs a
`matched` clue whose rival was put through the same comparison, or decisive clues from two lineages.

Contents: 1 the loop · 2 falsification test · 3 getting reference photos (`refs`) · 4 what the classes
mean · 5 comparing by eye · 6 `compare` · 7 the rival (negative control) · 8 recording the result ·
9 traps · 10 consistency pass · 11 coordinates and radius · 12 checklist

## 1. The loop

```
for the favourite, then for its closest rival:
    falsification test  ->  refs (collect + rank its photos)  ->  look at the sheets
    ->  compare the best ones large  ->  count specific fixed features  ->  record matched / observed / against
```

Why both: features that also "match" the rival are generic, and counting them is how a look-alike gets
confirmed. The comparison is the same work for both, and it is cheap.

## 2. Falsification test first

Before you look at any reference photo, write what must be true if the candidate is right, and what
would rule it out:

```
IGL cand <case> C12 --falsify "If C12: coffered ceiling with square panels, two arched windows with
transoms on the bed wall, green marble fireplace. Ruled out by: flat ceiling or rectangular windows
in every room type."
```

Writing it first stops you from seeing what you hope to see. Do the same for the runner-up: the two
tests together usually name the one observation that separates them.

## 3. Getting reference photos: `refs`

```
IGL refs <case> "<venue> <city> <room type>" "<venue> <city> lobby" [--url <gallery page>] [--image <url|file>]
         --for C#  [--cell C2:E4 | --query E##]  [--per 40] [--sheets 2]
```

- **Texts** are image searches (Brave and Startpage, keyless, headless). Use two or three per candidate:
  the room type in the photo ("lounge", "deluxe room", "bar", "bathroom", "lobby"), the venue's name in
  the local language, and "guest photos" or the platform name for traveller pictures. A text without a
  venue name searches a whole area (`"hotel lounge sea view Sandbanks Poole"`): the titles and pages of
  the pictures that resemble yours name the candidates.
- **`--url`** collects every sizeable picture on a page: the venue's own gallery, a listing, a review
  page, a news article. Big booking and review sites often show a bot wall; `refs` reports that as
  `blocked`, and their photos still arrive through the image searches.
- **`--image`** adds pictures you found yourself: a Lens result, a social post, a browser screenshot
  you saved.
- **`--cell` / `--query E##`** compares one part of your photo (the window wall, the ceiling, an artwork)
  instead of the whole frame: better when the rest is furniture.

It downloads the pictures, drops repeats of one photograph, tests each against your photo, and writes
numbered contact sheets with **your photo as the first tile**, a JSON list (titles, pages, classes) and a
`reference_match` entry in the ledger. `--for C#` records the comparison on the candidate; the report
lists it.

**The order of the sheet.** Confirmed classes come first. The pictures the feature test left open are
sorted by visual similarity to your photo (`sim` in the labels and the list; a DINOv2 image model,
sources-and-tools.md), most alike first, and the originals of the likeliest ones are fetched and tested
again at full size. So the top of sheet 1 is where a real photo of the room appears, also in a search
for a whole area: in a test with only "hotel bar lounge New Mexico" and "resort bar Taos Santa Fe" as
texts, the venue's own bar came out as tile 1 of 100 pictures of different bars. `sim` orders and never confirms: a look-alike
scores high too, and a photo of the same room from the opposite corner can score low. Without the
model (`init` says so) the pictures keep the search engine's order: then look at more sheets
(`--sheets 4`).

Sources by independence:

| Source | Independence | Notes |
|---|---|---|
| Traveller and user photos (Tripadvisor, Google Maps, Booking guest photos, Yelp, Dianping, Tabelog) | high | dated, unstaged, show views and bathrooms |
| Wikimedia Commons, Flickr, Openverse, Mapillary | high | often geotagged, licensed; `IGL geo photos`, `IGL social search` |
| News, blogs, real-estate listings, 360° tours, YouTube room tours (pause and screenshot) | medium–high | check the date |
| The venue's own gallery or brand site | medium | staged, wide-angle, may be old or show a sister property |
| A copy of the same photo | **none** | provenance, not a match: it cannot confirm itself |

## 4. What the classes mean

Every reference (and every reverse-search hit) gets one class from two automatic tests: perceptual
hashes for near-duplicates, and local-feature matching (SIFT with RANSAC, a homography for planar
structure and a fundamental matrix for general two-view geometry, also against the mirror image).

| Class | Means | Do |
|---|---|---|
| **COPY** | the same photograph (re-encoded, resized, cropped or flipped) | provenance: open its page, read caption, date, location tag, and record it as a `traced` clue (section 8); then verify the place it names against an independent photo. Never a match. |
| **SAME SCENE** | strong geometric agreement: the same structure seen again | open the inlier view (`compare`): on fixed architecture or venue-specific art it is site evidence; on chain furniture or a mass-produced print it proves the design only. "ONE SMALL OBJECT" in the verdict means a single item carries every inlier. |
| **PARTIAL** | some consistent correspondences | look where they are; repetitive textures produce chance inliers |
| **unconfirmed** | the feature test found nothing | **inconclusive in both directions.** Judge by eye (section 5), from the top of the sheet: most similar first. |

The asymmetry matters. A positive is reliable. A negative is not: classical features do not survive
another viewpoint, another lens, different lighting, a renovation or years between two photos. Measured
on a real case: photos of one bar taken years apart scored 8-11 inliers, unrelated bars 10-14. So
"unconfirmed" never means "a different place", and equally it never means "probably the place":
engines and image searches put look-alikes beside real matches. Unconfirmed items are ordered by visual
similarity (or left in the source's order when the model is missing), and you decide.

## 5. Comparing by eye

Your own comparison is the main instrument. Make it disciplined:

1. **List the fixed features of your photo first**, before reading any reference: how many windows and
   doors, their shape, glazing bars and position; the ceiling (height, beams, coffers, cornice, vents,
   light positions); columns; built-ins (panelling, niches, fireplaces, bar counters, staircases);
   floor pattern in public areas; fixed fittings (sockets, radiators, AC units); the view; any art,
   sculpture, mural or carpet that looks made for this venue.
2. **Go through the sheet tile by tile** and, for each plausible reference, name which of those
   features it shows, and which it contradicts.
3. **Count only invariants.**

| Invariant (counts) | Variant (does not count alone) |
|---|---|
| Window count, shape, mullions and transoms, sill height, frame type; door positions | Furniture, bedding, curtains, cushions |
| Ceiling height and shape, beams, coffers, cornices, columns | Wall colour, wallpaper (renovations) |
| Built-ins: panelling, niches, fireplaces, staircases, fixed counters, bar backs, bathroom layout | Decorations and prints that any venue could buy |
| Stone or tile floor patterns in public spaces; custom-woven carpet | Rugs and standard carpet |
| Socket and switch positions, radiator positions, sprinkler and vent layout | Light fittings (often replaced) |
| The view through the window, and the building opposite | Seasonal decor, displays, menus |
| Art, sculpture or murals made for the venue | Chain "design package" items |

4. **Grade.**
   - **≥3 distinct, specific invariant features agree** with an independent reference and no fixed
     feature disagrees: a `matched` clue (LR 30–100).
   - **1–2 agree**: `observed` (LR ≤6). Look for more references, another angle, another room type.
   - **Only the style agrees** (same kind of chairs, same palette, "also has wood panelling"): nothing is
     verified. This is the look-alike case.
   - **A fixed feature disagrees** (window shape, ceiling form, the view): it speaks against that room or
     view, not necessarily the whole site. Check other room types, other floors and the mirror image
     first, then record it with `--against`.

Specific means it would be a coincidence elsewhere: "a snake sculpture coiling around the column left of
a round bar under a scaled oval canopy" is specific; "armchairs around low tables" is not.

## 6. `compare`

```
IGL compare <case> --refs <E## of a refs/revsearch result> --pick 3,7 [--for C#] [--cell C2:E4 | --query E##]
IGL compare <case> --ref <url|file|E##> [--ref ...]
```

It writes a large side-by-side sheet, runs both tests on full-size originals where they can be fetched,
saves an inlier view for every reference with agreement, and flags references that are copies or crops
of one photograph ("R2 and R1 are the SAME PHOTOGRAPH": one reference, not two). `IGL crop <case> --of
E## --rel x0,y0,x1,y1` zooms into any evidence image, e.g. a detail of a reference photo.

Use `--cell` (or `--query E##` with a crop) to compare one distinctive part instead of the whole frame:
matches improve when furniture is left out. Compare a flipped crop (`IGL crop --flip`, then `--query
E##`) when the room may be mirrored.

## 7. The rival (negative control)

Run sections 3-6 for the closest alternative: the next hotel of the same brand, the venue next door,
the look-alike the engine suggested (`IGL refs <case> "<rival> <city> <room type>" --for <rival C#>`).
Three outcomes:

- The favourite shows specific features and the rival does not: the comparison discriminates. This is
  what HIGH requires. Without a rival on file a match stays MEDIUM, however good it looks.
- Both "match": the features are a **shared design** (a chain's room package, a hotel group's
  furniture, a franchise fit-out, a popular supplier). The design is verified, the venue is not. Record
  the match for the smallest candidate that holds every venue with that design, and keep the venues as
  leads:
  ```
  IGL cand <case> "Sandbanks peninsula, Poole (the group's two hotels)" --level district --parent <city C#> --at <lat,lon>
  IGL note <case> "Design match: armchairs, coffee table and cliff paintings appear in both hotels' own photos (refs E19, E22)"
      --kind match --status matched --source reference --file E19 --file E22
      --features "button-tufted armchair with turned legs; glass-top oak coffee table; chalk-cliff painting series"
      --for <district C#>:40 --why "the group's furnishing, seen in two of its venues"
  IGL answer <case> <district C#> --lead <the likelier hotel C#> --summary "..."
  ```
  Then look for what only one of them has: the view, the room's shape, a fixed feature, local art.
- Neither matches: no reference photo of that room exists online, or it is neither venue. The site
  stays a lead.

A comparison you could only make in a browser tool counts when it is recorded: a clue with `--source
reference` linked for or against the rival (`--against <rival C#>:3 --why "its lounge has a flat
ceiling"`). `check` warns when the answer is a site and no rival was compared, and when a rival's photos
were classed SAME SCENE too.

## 8. Recording the result

```
IGL note <case> "Matches Tripadvisor traveller photo (2023), refs E14 #7 and compare E16" --kind match
    --status matched --source reference --file E16 --url <page of the reference>
    --features "coffered ceiling 3x4 panels; arched window pair with transoms; green marble fireplace left of the bed"
    --for C12:60 --why "three invariant features agree with an independent photo; rival C13 shows flat ceilings"
```

- `matched` requires `--features` with at least three entries, and the comparison behind it: a file
  written by `compare`, `refs` or `revsearch`, or `--url` of the reference when you could only see it in a
  browser tool. A comparison whose references are all COPY is refused: a copy is provenance.
- One `matched` clue per independent reference (another photographer, another source, another date).
  Copies of one photo count once.
- **A COPY is recorded as `traced`**, with the page and the file that shows the copy:
  ```
  IGL note <case> "Same photograph in the hotel's own gallery, captioned 'Lounge bar' (refs E14 #2)" --kind provenance
      --status traced --source web --url <page> --file E14 --for C12:15 --why "the venue's own page"
  ```
  LR 10–20 when the page is the venue's own site, its listing on a booking or map platform, or the
  photographer's post naming the place; `--status reported` with LR ≤6 for aggregators, pin boards and
  reposts. A traced copy makes the venue probable (MEDIUM). It cannot confirm itself, so look for an
  independent photo: the rest of the same gallery or album usually shows the room from another angle
  (`IGL refs <case> --url <page> --for C12`), and that match makes it HIGH.
- Before trusting a trace, look at where else the copy appears. On pages of several branches or
  several unrelated venues it is a brand or stock picture: link the clue to each venue named.

## 9. Traps

- **Look-alikes.** The default assumption for anything an engine returns. Similar is the category, not
  the place.
- **Brand ≠ property.** Chains clone rooms, lobbies and restaurants. A design match proves the brand; the
  site needs a property-specific feature.
- **Mirror-image rooms** (both sides of a corridor), mirrored reposts, selfie-camera flips. The tests
  check both orientations; check text and handedness yourself too.
- **Renovations**: compare dates. Old photos of a renovated room match its structure but not its finish.
- **Lens geometry**: ultra-wide listing photos make rooms look deeper and bend straight lines. Compare
  relations (what is next to what), not proportions.
- **Captions and location tags lie.** Users tag the nearest famous venue. Two unrelated posters agreeing,
  or a visual match, is required.
- **Stock and brand pictures.** Venues illustrate their pages with stock photos, renderings and the
  brand's "typical room"; news sites illustrate with whatever fits. A copy on a venue's page proves less
  when the same picture also sits on other venues' pages.
- **Portable identity.** Stationery, pens, cups, bags and souvenirs name where the object came from.
- **Staging and generation**: rendered or AI images, composites, virtual staging. Check `init`'s C2PA and
  AI flags; look for impossible shadows, repeated textures, garbled text.
- **Unreachable is not empty.** A blocked engine, a bot wall or a rate limit is not "no results".

## 10. Consistency pass (log as `consistency`)

Check the top candidate against everything independent of how it was found:

| Check | Tool | Pass when |
|---|---|---|
| Time zone vs the EXIF offset | `IGL geo timezone --at <lat,lon> --case <case>` | CONSISTENT, or no offset in EXIF |
| Daylight and sun direction | `IGL sun --at .. --time ..` | the light in the photo matches the elevation and azimuth |
| Weather on the day | `IGL geo weather --at .. --case <case>` | no strong mismatch with the visible weather |
| Season | — | foliage, snow and decorations fit the date and hemisphere |
| Standards and language | `IGL countries` / `IGL lookup country` | sockets, signs, script and currency fit the country |
| Height and floor | OSM `building:levels`, the view | the estimated floor exists in the building |
| Existence in time | `geo wikidata --details` (inception), news, listing dates | the venue (and its current decor) existed at the capture date |
| Bearings to landmarks | `IGL bearing` | identified landmarks lie inside the window's view |

Every failure becomes a `contradiction` clue. Resolve it (`--resolves N#`) or lower the confidence. Then
re-run the step that decided the case once, differently (another crop, keywords, engine or reference),
and argue the runner-up's case: what evidence would make it win?

## 11. Coordinates and radius

- **Site:** the building's coordinates (the OSM way centre or the main entrance), not the street and not
  the town centre. `IGL geo search "<venue>, <city>"`; when the geocoder returns the street or nothing,
  take the coordinates from the venue's map listing or official address and say where they came from.
  Radius covers the footprint: about 30–60 m for a typical building, more for a large complex (airport
  terminal, mall, hospital, campus: use the complex's extent).
- **Room:** the building's coordinates with the floor and room in the answer text.
- **District / city / region / country:** the centroid of the area that is still consistent, with a
  radius covering it (`answer` derives it from the area's bounding box when it geocodes the name;
  defaults: district 1.5 km, city 8 km, region 80 km, country 400 km). Never pretend to more precision.
- **Lead and pin:** the lead's coordinates are reported with the lead, never as the answer's. `answer`
  also prints the `PIN`, the single most likely point: the lead's coordinates when there is a lead with
  coordinates, the answer's otherwise. When the candidates are a few distinct places, the pin is the
  likeliest of them, not the midpoint between them with a large circle.

## 12. Checklist before `IGL answer`

- [ ] Hypotheses recorded first, and their fate (confirmed, refined or overturned) visible in the timeline.
- [ ] Every tile read by eye; text confirmed on crops.
- [ ] Reverse search ran (not merely "was attempted") on ≥2 engines, on the full frame and on crops; Lens
      used where any browser tool exists; ranked sheets opened.
- [ ] The category was enumerated: other branches, same-name venues, the other venues of the kind in the
      town are on the board.
- [ ] Site level: falsification test written; `refs` run for the favourite and for a rival; a `matched`
      clue with named features, a traced copy, or a venue name read in the photo. Otherwise the site is
      a `--lead` and the answer is its verified parent.
- [ ] If the rival's photos showed the same features: the match is recorded for the area or group, and
      the venues are leads.
- [ ] Consistency pass done; contradictions resolved or reflected in the confidence.
- [ ] The answer is top-ranked at its level, its ancestors are top-ranked, and its share is not carried
      by the unlisted alternatives.
- [ ] Coordinates are the building's; the radius covers the uncertainty.
- [ ] Alternatives listed with separating tests; limits stated ("not verified: ...", routes that were
      blocked).
- [ ] Privacy: no private names, home addresses or identification of people in the report.
- [ ] `IGL check` passes (fix every FAIL, read every WARN), then `IGL finalize`.
