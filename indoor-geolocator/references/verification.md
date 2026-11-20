# Verification

Workflow step 8. A candidate is not an answer until it survives an honest attempt to prove it wrong.
The confidence caps (evidence-and-confidence.md) enforce this in code: no `matched` clue and no two
decisive lineages means no HIGH at site level.

## 1. Falsification test first

Before you look at any reference photo, write what must be true if the candidate is right, and what
would rule it out:

```
IGL cand <case> C12 --falsify "If C12: coffered ceiling with square panels, two arched windows with
transoms on the bed wall, green marble fireplace. Ruled out by: flat ceiling or rectangular windows
in every room type."
```

Writing it first stops you from seeing what you hope to see.

## 2. Collect independent reference imagery

Rank sources by independence from each other and from the photo's own lineage:

| Source | Independence | Notes |
|---|---|---|
| Traveller and user photos (Tripadvisor, Google Maps, Booking guest photos, Yelp, Dianping, Tabelog) | high | dated, unstaged, show views and bathrooms |
| Wikimedia Commons, Flickr, Openverse, Mapillary | high | often geotagged, licensed; `IGL geo photos`, `IGL social search` |
| News, blogs, real-estate listings, 360° tours | medium–high | check the date |
| The venue's own gallery or brand site | medium | staged, wide-angle, may be old or show a sister property |
| A copy of the same photo found by reverse search | **none** | provenance, not a match: it cannot confirm itself |

Make a side-by-side sheet: `IGL compare <case> --ref <url|file|E##> [--ref ...] [--cell C2:E4]`. Use
`--query E##` to compare a crop, for example a flipped crop from `IGL crop --flip`.

## 3. Compare invariant features only

| Invariant (counts) | Variant (does not count alone) |
|---|---|
| Window count, shape, mullions and transoms, sill height, frame type; door positions | Furniture, bedding, curtains, cushions |
| Ceiling height and shape, beams, coffers, cornices, columns | Wall colour, wallpaper (renovations) |
| Built-ins: niches, fireplaces, staircases, fixed counters, bar backs, bathroom layout | Art and decorations (often replaced) |
| Stone or tile floor patterns in public spaces | Carpets and rugs |
| Socket and switch positions, radiator positions, sprinkler and vent layout | Light fittings (often replaced) |
| The view through the window, and the building opposite | Seasonal decor, displays, menus |

**Grading a comparison:**
- **≥3 distinct, specific invariant features match** an independent reference, with no unexplained
  invariant mismatch: write a `matched` clue (LR 30–100).
- **1–2 specific features match**: `observed` (LR ≤6). Look for more references.
- **Generic agreement** (same chain furniture, white walls, standard windows): it counts for nothing at
  site level, because it only confirms the category.
- **An invariant mismatch** (window shape, ceiling form, the view) speaks against that room or that
  view, not necessarily the whole site. Check other room types, other floors and the mirror image
  first. Exclude only as much as the evidence covers (hard rule 7).

Record a match with the features named:

```
IGL note <case> "Matches E14 (Tripadvisor traveller photo, 2023): coffered ceiling 3x4 panels; arched
window pair with transoms; green marble fireplace left of the bed" --kind match --status matched
--source reference --file E14 --url <page url>
IGL link <case> N9 --for C12:60 --why "3 invariant features match an independent traveller photo"
```

## 4. Traps

- **Mirror-image rooms** (both sides of a corridor), mirrored reposts, and selfie-camera flips.
  Compare both orientations.
- **Renovations**: compare dates. Old photos of a renovated room match its structure but not its finish.
- **Sister properties and chains**: brands reuse identical designs. A match on design only proves the
  brand, and the site needs a property-specific feature (the view, the layout, local art, a fixed
  architectural detail).
- **Lens geometry**: ultra-wide listing photos make rooms look deeper and bend straight lines. Compare
  relations (what is next to what), not proportions.
- **Staging and generation**: rendered or AI images, composites, virtual staging (furniture added to an
  empty-room photo). Check `init`'s AI and C2PA flags. Look for impossible shadows, repeated textures,
  garbled text.
- **The same image** found online is provenance, never a match (see the table above).

## 5. Consistency pass (log as `consistency`)

Check the top candidate against everything independent of how it was found:

| Check | Tool | Pass when |
|---|---|---|
| Time zone vs the EXIF offset | `IGL geo timezone --at <lat,lon> --case <case>` | CONSISTENT, or no offset in EXIF |
| Daylight and sun direction | `IGL sun --at .. --time ..` | the light in the photo matches the elevation and azimuth |
| Weather on the day | `IGL geo weather --at .. --case <case>` | no strong mismatch with the visible weather |
| Season | — | foliage, snow and decorations fit the date and hemisphere |
| Standards and language | `IGL countries` / `IGL lookup country` | sockets, signs, script and currency fit the country |
| Height and floor | OSM `building:levels`, the view | the estimated floor exists in the building |
| Existence in time | `geo wikidata --details` (inception), news | the venue (and its current decor) existed at the capture date |
| Bearings to landmarks | `IGL bearing` | identified landmarks lie inside the window's view |

Every failure becomes a `contradiction` clue. Resolve it (`--resolves N#`) or lower the confidence.

## 6. Re-run and devil's advocate

- **Re-run** the step that decided the case once, differently: another crop, keywords, engine or
  reference photo. If the answer moves by more than the claimed radius, lower the confidence and
  widen the radius.
- **Steelman the runner-up:** what evidence would make it win? Name the separating test (`cand
  --falsify` on the runner-up too) and run at least one. Alternatives go into the report with their test.
- **Lineage audit:** is the top candidate carried by one lineage (e.g. only the engine and pages copying
  each other)? Then it is MEDIUM at most, whatever the share says.

## 7. Coordinates and radius

- **Site:** the building's coordinates (OSM way centre or the main entrance), not the street. Radius
  covers the footprint: about 30–60 m for a typical building, more for a large complex (airport terminal,
  mall, hospital, campus: use the complex's extent).
- **Room:** the building's coordinates with the floor and room in the answer text. The radius stays at
  building size.
- **District / city / region / country:** the centroid of the area that is still consistent, with a
  radius covering it (`report.DEFAULT_RADIUS` gives defaults: district 1.5 km, city 8 km, region 80 km,
  country 400 km). Shrink it when the evidence allows, and never pretend to more precision.

## 8. Checklist before `IGL answer`

- [ ] First impression recorded, and its fate (confirmed, refined or overturned) visible in the timeline.
- [ ] Every core method resolved, or honestly blocked or unavailable with the alternative tried.
- [ ] The answer is the top-ranked candidate at its level, and its ancestors are top-ranked too.
- [ ] Site level: falsification test written; `matched` clue from independent imagery, or two decisive
      lineages.
- [ ] Consistency pass done; contradictions resolved or reflected in the confidence.
- [ ] Re-run done; radius covers the uncertainty.
- [ ] Alternatives listed with separating tests; limits stated ("not verified: ...").
- [ ] Privacy: no private names, home addresses or identification of people in the report.
- [ ] `IGL check` passes (fix every FAIL), then `IGL finalize`.
