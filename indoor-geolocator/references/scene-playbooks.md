# Scene playbooks

Classify the scene first (`IGL note <case> "Scene: hotel room" --kind scene --status observed --source image`),
then follow its playbook. Each playbook gives the fastest routes in order, where reference photos live
(you need them for `matched`), how to enumerate candidates, the usual traps, and the level you can
realistically reach. Several playbooks can apply at once, e.g. a hotel restaurant, or a station inside a
mall. Platform lists per country are in [search-playbook.md](search-playbook.md).

Contents: hotel · rental, home, real estate · restaurant, café, bar · retail, mall, supermarket ·
transit (station, airport, vehicle on a route) · venue or landmark (museum, worship, theatre, stadium,
historic interior) · institution (school, university, hospital, office, government, library) ·
car or taxi interior · screenshots, virtual tours, renders · generic or unknown

---

## Hotel room, lobby, corridor

**Recognise:** key-card power slot, luggage rack, minibar or kettle tray, a folded towel, a "Do not disturb"
hanger, a safe, slippers, an evacuation plan on the back of the door, branded toiletries or stationery, a TV
welcome screen, a room-service folder, or numbered doors along a corridor.

**Fastest routes:**
1. **Name text**: stationery, pens, notepads, key-card sleeves, toiletries, laundry bags, coasters,
   bathrobes, the TV welcome page or the Wi-Fi card (SSID). Read it on a crop, then
   `IGL geo search "<name> <city>" --case <case> --add site`.
2. **Evacuation plan** (back of the door): it often prints the hotel name, the street, the floor and room
   number, and the floor shape, which you can compare with the building footprint in OSM.
3. **Brand identification** from the design package: headboard, carpet, lamp, desk, art, bathroom
   fittings. Brands reuse identical rooms across hundreds of properties, so treat a brand as a
   *category*, then:
4. **Enumerate every property** of the brand in the candidate area:
   `IGL geo poi --brand "<brand>" --tag tourism=hotel --area "<city>" --case <case> --add site --parent C#`.
   OSM `brand` tags are incomplete, so also try `--name "<brand>"`, a Wikidata SPARQL query on `P1716`
   (brand) or `P127` (owned by), and the brand's own hotel directory.
5. **Separate the properties** with room-specific invariants: the window view (skyline, the building
   opposite, the floor height), the window type, the ceiling height, the room shape (corner or
   standard), and local art (many chains commission local artwork for each property). Then the photos.
6. **Reference photos**: the official website gallery, Booking.com, Expedia/Hotels.com, Agoda, Trip.com,
   Tripadvisor traveller photos (dated, unedited, often show the view), Google Maps photos and indoor
   Street View, and regional platforms (search-playbook.md). Traveller photos are independent of the
   hotel's marketing.

**Traps:** rooms on opposite sides of a corridor are often **mirror images**, so compare with flipped
crops too (`IGL crop --flip` then `compare --query E##`). Renovations replace carpets and furniture, so
compare invariants and check photo dates. Toiletries and amenity brands (and sometimes the room design)
are shared across unrelated hotels. "Hotel art" can be mass-produced prints.

**Reachable:** site, often HIGH (the name plus matched photos). Room level only with a room number or a
view match plus floor geometry.

## Rental, home, real estate

**Recognise:** lived-in clutter, personal décor, a kitchen in the shot, listing-style wide-angle framing,
staged furniture, a "for rent" or agency watermark.

**Privacy gate (hard rule 11):** a private home is a person's home. If it looks like a private residence
and the user stated no purpose, ask once what it is for. Without a legitimate purpose, stop at city or
neighbourhood. Listings (short-term rentals, real estate) are commercial adverts, so matching one is
fine. Still redact host and owner names and never publish the flat number of a private home.

**Fastest routes:**
1. **Listing match**: wide-angle, bright, staged photos with a watermark suggest a listing. Reverse
   search the full frame (TinEye "oldest", Google Lens, Yandex), then search the right platform for the
   country: Airbnb, Vrbo or Booking.com for short stays, and the real-estate portals per country
   (search-playbook.md).
2. **Country and city** from the standards (indoor-clues.md §5–10), which is the main tool here. Then
   the window view.
3. **Building type**: a Soviet-era panel block, a Haussmann apartment, a Japanese mansion or apāto, a
   Korean apartment complex, an HDB flat in Singapore, a Hong Kong public housing estate, a US suburban
   tract house. This narrows the district, and the window view pins it.
4. **Mail, parcels, school notices, local business calendars and fridge magnets**: these give the city or
   postcode (redact names and the house number of a private address).

**Reference photos:** the listing's own gallery (more rooms, the exterior and the view), the same flat
re-listed over the years (sale and rent), Street View of the exterior if the listing gives the street.

**Reachable:** a listing gives the site, but report it only at the precision the purpose justifies.
Otherwise city or district.

## Restaurant, café, bar

**Recognise:** tables in rows, menus, a counter or bar, taps, a coffee machine, a pass to the kitchen,
table numbers.

**Fastest routes:**
1. **Name**: menu header, receipt, napkins, cups, sugar sachets, coasters, staff aprons, Wi-Fi card,
   window lettering seen from inside (read it mirrored with `crop --flip`).
2. **Displayed licences and certificates** (often the address itself):
   - UK: Food Hygiene Rating sticker (FSA, 0–5); Scotland's FHIS pass sticker.
   - US: NYC letter grade (A/B/C) and other city grade cards; Toronto DineSafe.
   - Nordics: Denmark's Smiley (Fødevarestyrelsen) report and Norway's Smilefjes, both with the
     business name.
   - China: 营业执照 (business licence: name, address, credit code) and 食品经营许可证 (food business
     licence), with the hygiene face rating.
   - Korea: 영업신고증 (registration: trade name, address).
   - Japan: 営業許可証 (business permit).
   - Taiwan: a restaurant hygiene-grade certificate.
3. **Menu analysis**: dish names, spelling, prices and currency, the service-charge or tax line, opening
   hours, phone or URL. Search exact dish strings in quotes with the currency.
4. **Review platforms**, which have huge photo sets of interiors: Google Maps, Tripadvisor, Yelp
   (US/CA/some EU), Dianping 大众点评 (CN), Tabelog / Retty / Gurunavi (JP), Naver Map / Kakao Map
   (KR), OpenRice (HK, also MY/SG/TH/ID/PH), Zomato (IN, AE…), Wongnai (TH), TheFork (FR/ES/IT/…),
   Foursquare. For bars, Untappd lists the beers on tap.
5. **Chain → branch**: enumerate the branches
   (`IGL geo poi --brand "<chain>" --area "<city>" --add site`), then separate them with the local
   layout, the view, murals and neighbourhood art.

**Traps:** chains clone interiors; restaurants change names and owners but keep the room. Menus,
cups and pens travel. Check the photo date against the venue's opening (and closing) date.

**Reachable:** site, frequently HIGH.

## Retail, mall, supermarket

**Recognise:** shelving, price tags, checkouts, a mall atrium, escalators, storefronts across a void.

**Fastest routes:**
1. **Retailer** from logos, shelf-edge label design, own-brand products, loyalty-scheme signs, bag
   colours and uniforms. Prices, currency and tax wording give the country (indoor-clues.md §3 and §11).
2. **Mall directory** ("You are here", 現在地, 您在此处, 현재 위치): the mall name, the floor naming
   (LG/UG/B1/M), store neighbours and the shape of the floor plan. Neighbouring store names visible
   across the atrium form a unique **co-location set**. Query it in OSM: shops tagged with `level` in
   a `shop=mall`, or `--near-tag` chains.
3. **Architecture**: atrium shape, skylights, escalator layout, column style, floor pattern. Malls are
   photographed heavily: Google Maps photos, Commons, the mall's own website, news (openings,
   renovations).
4. **Enumerate branches** of the store or mall operator, then separate them by the layout and the view
   to the outside.

**Traps:** stores of one chain are fitted from the same kit. Seasonal displays move. Duty-free shops
look alike in every airport.

**Reachable:** a mall or the branch with a directory or co-location set (often HIGH). Otherwise city.

## Transit: station, airport, vehicle on a route

**Recognise:** platforms, gates, departure boards, ticket machines, validators, route maps, wayfinding
signage, seat rows, grab rails.

**Fastest routes:**
1. **Station or terminal name** on signs, in the system's typeface and colours, plus line colours,
   station codes and platform numbers. Network signage is highly distinctive:
   - London Underground roundel and Johnston typeface.
   - New York subway coloured bullets with Helvetica.
   - Paris Métro Parisine typeface.
   - Station codes: Tokyo (G09), Singapore (NS24), Seoul station numbers.
   - Moscow Metro's ornate halls.
2. **Network map on the wall**: the full network, often with a "you are here" dot.
3. **Departure board**: the airlines, flight numbers, destinations and times. The set of destinations
   from one airport is almost a fingerprint, and a flight number plus a scheduled time identifies the
   airport and often the date (flight-history sites). Train boards work the same way with operator,
   train number and destinations.
4. **Airport identity**: gate-numbering style, signage design (each airport has its own system),
   distinctive carpets, art installations, lounges. Commons has dense categories per terminal.
5. **Vehicle interiors** (train, metro, tram, bus, ferry, aircraft): operator logos, seat-fabric
   (moquette) patterns, route maps above the doors, safety notices in the local language, ticket
   validators. The safety card on an aircraft gives the airline and aircraft type. An in-flight map
   shows the position at that moment.

**Traps:** a moving vehicle is a route, not a point. Answer the operator, line or route, and use the
window view plus timing for the position (radius = the stretch it could be on). Many airports share
the same signage vendor. Old photos may show retired signage.

**Reachable:** station or terminal (HIGH with the name plus matched photos). A vehicle: operator and
route, a point only with a window match.

## Venue or landmark: museum, place of worship, theatre, stadium, historic interior

**Recognise:** exhibits, labels, altars, iconostases, mihrabs, organs, stage and seating, vaulted or
decorated ceilings, period interiors.

**Fastest routes:**
1. **Reverse image search**: famous interiors are well indexed. Use the full frame plus crops of
   the most distinctive elements (ceiling, altar, a specific artwork).
2. **Artwork route**: identify a painting or sculpture (reverse search a tight crop, read the wall
   label), then its holding collection (Wikidata `P195` collection, `P276` location) gives the museum
   and sometimes the room. Example:
   `IGL geo sparql 'SELECT ?item ?itemLabel ?locLabel ?coord WHERE { ?item rdfs:label "Mona Lisa"@en; wdt:P276 ?loc. ?loc wdt:P625 ?coord. SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }'`.
   Titles are not unique: that query returns 14 works labelled "Mona Lisa" in 12 museums, so confirm the
   creator (`P170`), the dimensions and the image before trusting the location. Other traps: loans and
   touring exhibitions, reproductions in hotels and homes, museum-shop copies.
3. **Worship spaces**:
   - Denomination and liturgy, iconography, inscription language, saint names.
   - Commons categories ("Interior of …") are very dense.
   - A mosque's **mihrab** wall faces the qibla. Once you know the compass direction of the room
     (window view or sun), `IGL bearing --from <candidate> --to qibla` must agree.
4. **Theatres, concert halls, stadiums**: seat colours, the proscenium, balcony shapes, ceiling, roof
   structure, advertising boards, banners (event name and date), scoreboards.
5. **Enumerate** with SPARQL (museums, churches by dedication, theatres in a region) or OSM
   (`amenity=place_of_worship` + `religion=*` + `denomination=*`, `tourism=museum`, `amenity=theatre`).

**Traps:** many churches share the same neo-Gothic interior, and many stadiums the same bowl.
Renovations change colours.

**Reachable:** site, usually HIGH (reference imagery is plentiful).

## Institution: school, university, hospital, office, government, library

**Recognise:** classrooms, lecture halls, corridors with notice boards, wards, reception desks, open-plan
offices, meeting rooms, shelving with call numbers.

**Fastest routes:**
1. **Name text**: wall signs, room plates, lecture slides, posters, notice boards (events give dates and
   addresses), patient information leaflets, visitor badges, mugs and lanyards.
2. **Room numbering schemes** (e.g. "B-2.14", "3F-305") and wayfinding colours identify a campus or
   hospital, and the floor directory in the lobby names the building.
3. **Health systems**: the NHS logo (and its Scottish and Welsh variants), national health-insurance
   posters, hospital-group branding, emergency department names (A&E, ER, 急诊, 救急).
4. **Library call numbers**:
   - Library of Congress (e.g. QA76.73): mostly US academic libraries.
   - Chinese Library Classification 中图法 (e.g. TP312): China.
   - Dewey: widespread. Japan uses NDC, Korea uses KDC.
5. **Fire notices** naming the assembly point, and **meeting rooms** named after local places.
6. **Enumerate**: `amenity=university|school|hospital|library`, `office=*`, Wikidata (universities and
   hospitals have coordinates and Commons categories).

**Traps and privacy:** never identify pupils, patients or staff. Minors need extra care, so use the
institution only, never people. Corporate offices reuse fit-outs worldwide.

**Reachable:** institution site, often HIGH with a name plus matched photos.

## Car or taxi interior

- **Steering side**: shows the driving side of the car's market, not necessarily where it is (RHD
  imports in Russia's Far East, Japanese imports in NZ, Pakistan and East Africa).
- **Dashboard**: language, km/h vs mph, °C/°F, radio presets and RDS station names (regional).
- **Windscreen stickers**: toll transponders (E-ZPass, SunPass, FasTrak, Télépéage, Via-T, Hi-pass,
  ETC, FASTag, e-TAG); Swiss or Austrian motorway vignettes (most neighbours use e-vignettes now);
  city parking permits (zone and city); inspection stickers (Japanese 車検 sticker, US state stickers,
  Mexico City-area verification hologram).
- **Taxi**: meter design, licence card with the authority's name (redact the driver's name), fare table
  in local currency, partition design.
- **Window view**: decisive for the point, because the car interior only gives the region.

**Reachable:** region or city from the interior, a point only with the view.

## Screenshots, virtual tours, renders

- **UI chrome** tells the platform: Matterport and other 3D tours, Google indoor Street View, listing
  apps, game engines. A tour URL or ID is often findable. The platform's own map gives the place.
- **CGI renders** (architectural visualisations, AI images): over-perfect surfaces, impossible
  lighting, repeated textures, garbled text, warped geometry. Check `init`'s AI and C2PA markers. A
  render may show a real **planned** building (developer marketing); search the project name.
- **Video stills**: find the source video. Later frames often show the exterior.

## Generic or unknown

Run the full sweep (indoor-clues.md), then intersect country standards
(`IGL countries … --case`), then reverse search the full frame and 3–5 crops. Search distinctive
strings, and use any window view. If nothing goes below country or region, say so plainly and report
the best level with an honest radius and the evidence still missing.
