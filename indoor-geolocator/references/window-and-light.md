# Window views, reflections, sunlight and weather

Read this when the photo shows any window, open door, glass wall or reflection, or any direct sunlight.
A view is a second, outdoor photo inside the indoor one. It often pins the exact building, the facade
and the floor. Log `window_view` (results, no_results, or not_applicable when there is no view at all)
and `sun_light` when you use the sun.

## 1. Read the view like an outdoor geolocation

Crop the view on its own (`IGL crop --cell .. --enhance auto --label view`) and treat it as a street
photo. Go through:
- **text** on buildings opposite: shop signs, hotel names, rooftop logos, street-name plates;
- **landmarks and skyline**: towers, domes, bridges, stadiums, mountains, coastline, rivers, rail lines;
- **traffic**: driving side, road markings (yellow centre lines in the Americas and parts of Asia; white
  in Europe), taxi colours, bus liveries, tram or metro lines;
- the **format** of licence plates (size, colours, layout). Never read plates to identify vehicles or
  people;
- **street furniture**: traffic-light shape and mounting, bollards, lamp posts, kerbs, manhole covers;
- **buildings**: age, height, materials, roof shapes, balconies, air-conditioner units, solar water
  heaters on roofs;
- **vegetation and climate**: palms, conifers, bare deciduous trees, irrigation, dust, snow.

Then search as outdoors: reverse search the view crop, look up landmarks, and enumerate co-located
features with `IGL geo poi --near-tag` (e.g. a hotel within 150 m of a church and a tram stop).

**Glass traps:** text on window decals reads mirrored from inside (`crop --flip`). Night shots
reflect the room, and double glazing makes ghost images. Tinted, frosted or mesh-covered glass
distorts colour.

## 2. Floor estimate

- **Horizon rule:** with a level camera, the horizon line crosses everything that sits at the camera's
  height. On a building opposite, count the floors below the horizon line to get your floor (if both
  buildings start at the same ground level).
- **Typical storey heights:** residential 2.8–3.2 m, offices and hotels 3.5–4.2 m, ground floors and
  old buildings taller. Camera height ≈ floor index × storey height + about 1.5 m.
- **Looking down** at roofs and street furniture means high. Tree crowns at eye level means about floors
  3–6. Seeing over most rooftops means above the local building height (compare OSM `building:levels`).
- Record the estimate as `observed` with a range ("floor 7–9"), and use it to choose among room
  candidates and to check the candidate building's height.

## 3. Facade direction and the sun

Facade orientation comes from the map: the building outline, or the street the window faces (OSM,
satellite imagery in a browser). A window facing north-east has azimuth 45°.

**Direct sunlight entering** means the sun is in front of that facade: within about ±90° of the facade
direction, and above the obstruction angle of the buildings opposite. With the candidate's coordinates
and the capture time (EXIF local time with offset):

```
IGL sun --at 48.2085,16.3731 --time 2024-05-01T15:30+02:00
-> azimuth 238.4°, elevation 43.8°   (the sun is in the WSW; light travels FROM there)
```

Check: |sun azimuth − facade azimuth| < 90° and the elevation is plausible. Otherwise the candidate
facade, the time, or both are wrong.

**Sunlit patch geometry** (a patch on the floor or wall):
- The patch is displaced from the window *away* from the sun (towards azimuth + 180°).
- Elevation: tan(el) = h / d, with h the height of the window edge above the floor and d the
  horizontal distance from the wall to the matching patch edge, measured along the sun direction. If
  the sun is oblique by δ to the facade normal and you measure d⊥ perpendicular to the wall, then
  tan(el) = h·cos δ / d⊥. Estimate h from known sizes (doors about 2.0–2.1 m, sills about 0.8–0.9 m,
  ceilings about 2.5–3 m), since everything else is scaled from them.
- Without capture time: sun azimuth and elevation constrain time and orientation jointly. Use them
  only once the place is known, as a consistency check.

**Shadows outside** (poles, buildings) give the sun's direction relative to the street. With the street
bearing from the map that gives the time of day (or confirms it).

**Darkness:** elevation < 0° means the sun has set; < −6° means dark sky, street lights on, lit windows.
Compare with what the photo shows at the claimed time.

## 4. Bearings, landmarks and distances

When a landmark is identified in the view:

```
IGL bearing --from <candidate lat,lon> --to <landmark lat,lon> --facing <facade azimuth>
-> distance, bearing, angle off the facade direction, in view yes/possibly/no
```

- The landmark must lie within the window's field of view (`in_view`). Use its left–right position
  in the photo to check the bearing roughly.
- **Size versus distance:** with the 35 mm-equivalent focal length f35 from EXIF, the horizontal field
  of view is 2·atan(36 / (2·f35)) (vertical: 24 mm instead of 36). A landmark spanning p pixels of an
  image W pixels wide subtends about p/W × FOV. Its distance is about height / tan(angle). This gives
  only a rough check, so record it as `computed` with a modest LR (≤6).
- Two identified landmarks plus their bearings intersect at the camera position (resection). That can
  pin the building, and the two must agree with the candidate facade.
- **Qibla** (mosques, prayer-direction stickers in hotel rooms): `IGL bearing --from <candidate> --to
  qibla` gives the direction a mihrab or qibla arrow must point.

## 5. Reflections

Mirrors, TV screens, glass tables, glossy floors, picture glass, chrome and windows at night often show
what the camera faces away from: the window, the door, a sign or the view. Crop, enhance (`--enhance
clahe` or `brighten`) and flip. Do not use reflections in eyes or glasses to identify anyone.

## 6. Season and weather

- **Season:** foliage, blossoms, snow, holiday decorations, the sun height at noon, darkness at a given
  hour, clothing. Pair it with the EXIF date: a mismatch suggests a wrong date or a different hemisphere.
- **Weather on the day:** `IGL geo weather --at <candidate> --case <case>` gives Open-Meteo reanalysis
  (daily, plus the capture hour when EXIF time exists): weather code, cloud cover, precipitation,
  snowfall and snow depth. Compare it with what the photo shows (snow on roofs, rain on glass, clear sky
  with hard shadows).
  - The grid is about 10–25 km and local weather varies, so record the result as `reported` and use it
    only for consistency.
  - A strong mismatch (deep snow outside, 25 °C recorded) means the date, the place or the metadata is
    wrong. Write a `contradiction` and resolve it.
  - The free service is rate-limited per IP. A quota error is `blocked`, not an absence.

## 7. Verify the view from outside

Once you have a candidate building, check from the outside: Street View, Mapillary or KartaView
(street-level photos) of the facade, and the view across the street from the matching floor (Google
Earth 3D in a browser). Do the buildings, signs and skyline line up in the same order and at the same
angles? Three or more independent matches of the view count towards `matched` (verification.md).
