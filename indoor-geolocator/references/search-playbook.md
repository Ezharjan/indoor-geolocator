# Search playbook

Retrieval routes for workflow step 4. Run every route that applies and log each one (`IGL log`; `revsearch`,
`refs` and `compare` log themselves). Results from engines, captions and listings are leads (`reported`,
source `engine` or `web`) until the pixels or independent reference photos confirm them (verification.md).

Contents: 1 reverse image search and picture search · 2 text search · 3 social media · 4 provenance
hunting · 5 listing and review platforms by country · 6 maps, 360° tours, photo collections ·
7 OpenStreetMap enumeration · 8 Wikidata and SPARQL · 9 Wi-Fi names, AI estimators · 10 never do

---

## 1. Reverse image search and picture search

For indoor photos this is usually the highest-yield route: hotel rooms, restaurants and flats are
photographed for listings and reviews, and a copy or a sibling photo of the same room often exists. It
is also the route that produces most wrong answers, because engines return look-alikes with a venue's
name attached. So the tool compares every hit with your photo before you read a single title.

**Headless (automatic):** `IGL revsearch <case>` searches the full frame on Yandex, TinEye and Baidu. Add
`--cell C2:D3` (or `--image E07`) for a crop, `--full` to keep the full frame as well, `--flip` for a
mirrored copy, `--engines all` to also try Bing and Lens headless (they usually refuse). Each engine's
upload form is tried first; when it does not start a search, a temporary public copy is made and the
engine is asked by URL (`--no-share` forbids the copy). A search that never started is reported as
`unavailable` or `blocked`, never as `no_results`.

**What comes back.** Per engine and image: the engine's labels (guesses), and hits numbered `#1…`, each
classed against your photo:

| Class | What it is | What to do |
|---|---|---|
| COPY | your photograph, published | provenance: open the page (web fetch or `IGL snapshot`), read caption, title, date, location tag, the rest of the album; record it as a `traced` clue (verification.md section 8) |
| SAME SCENE / PARTIAL | another photo with matching structure | the strongest leads: `IGL compare <case> --refs E## --pick <#>` shows where it matches |
| unconfirmed | no automatic match | open the **ranked sheet** (your photo is tile 1, then the hits, most similar first) and judge by eye: a real photo of the same room from another year or angle lands here, and so does every look-alike |

Titles of unconfirmed hits tell you the *kind* of place and often the region, not the venue. Count
what they share, level by level: twelve hits from British seaside hotels are a fair lead for "UK,
seaside hotel" even though no two name the same hotel, and two crops that both bring up one city count
for more than two hits that each name a different venue. Record that as an `inferred` clue (source
`engine`, capped at 3). Take a venue from a hit only after section 5 of verification.md.

**After a hit, look at the rest of the set.** A COPY or a SAME SCENE picture usually sits in a gallery,
an album or a multi-photo post. The other pictures show the same room from another side (the
independent reference you need) and often the name, the view or the building:
`IGL refs <case> --url <that page> --for C#`.

**Google Lens and Bing (any browser tool).** Lens has the largest index of interiors, listings and
products, and refuses headless clients. `revsearch` prints by-URL links when it made a temporary copy;
`IGL share <case> [--cell ..|--image E07] [--flip]` makes one on request (a metadata-free copy on a
temporary host, deleted after 1-3 hours) and prints `lens.google.com/uploadbyurl?url=...`, Bing
`imgurl:`, Yandex and TinEye links. Open the Lens link in your browser tool (Claude in Chrome, the
built-in browser) for the full frame and for 2-3 crops. Read "Exact matches" (provenance) apart from
"Visual matches" (leads), ignore the AI overview as evidence, and pass the promising result images to
`IGL refs <case> --image <url> [--image ...]` so they are compared like everything else. Without a
browser tool: ask the user to run Lens on the photo, or set `SERPAPI_KEY` (the user's own SerpApi key),
and `revsearch` adds Lens results itself.

| Engine | Best for |
|---|---|
| Google Lens | the largest index: venues, interiors, listings, products, text; "Exact matches" gives provenance |
| Yandex | similar-looking interiors and buildings; strong on hotels worldwide, Eastern Europe, Central Asia, VK content |
| Bing Visual Search | a different index from Google; products and pages |
| TinEye | exact and near-duplicate copies only; sort by **oldest** to find the original |
| Baidu (graph.baidu.com), Sogou | Chinese web: Ctrip, Mafengwo, Dianping, Xiaohongshu and Weibo copies |
| Naver (search.naver.com image) | Korean blogs and cafés |
| Pinterest Lens (in the app or browser) | décor, furniture, interiors pinned from listings |

**What to search:** the full frame; then 2–4 **tight crops** of identity carriers (an artwork, a
sculpture, wallpaper, a custom carpet, an unusual lamp, the ceiling, the window view, a logo); then a
mirrored copy (reposts are often flipped). A crop of a painting finds the painting; a crop of the view
is outdoor geolocation. Crop people out: it is more private, and matches improve because faces dominate
engines. Remove clutter (watermarks, UI bars) with a crop before searching.

**Picture search by text: `IGL refs`.** The second way to find a place by its looks, and the way to
get reference photos of a named candidate (verification.md section 3):

```
IGL refs <case> "hotel bar snake sculpture Taos"                      # describe what is unusual, plus the region
IGL refs <case> "hotel lounge sea view Sandbanks Poole" --sheets 3    # every venue of a kind in a town
IGL refs <case> "Hotel Sacher Wien deluxe room" "Hotel Sacher Wien lobby" --for C12   # one candidate
```

It runs the texts on Brave and Startpage image search, downloads the results, compares each with your
photo and writes contact sheets with your photo first and the pictures most similar to it next
(verification.md section 3). Because of that order, a text does not have to describe the place well:
the scene type and the region are enough to pull in a hundred pictures of different venues, and the
one that is your room rises to the top with its page and title. Use it early and repeatedly: for the
country or region with the scene type, for every town that becomes likely, and for every candidate
you enumerate.

- Vary the text: the room type, the local-language word (Hotel, 酒店, ホテル, отель), "guest photos",
  "interior", the platform name.
- Write a version with the place name and one without: little-known venues have few pictures filed
  under their town.
- Describe shapes with words you are sure of. A wrong count or a wrong style word ("Gothic" for round
  arches) filters the right pictures out; a broad word does not.
- `--max 240 --sheets 4` compares and shows more when the area is large.

Log what you opened. A no-match from one engine says little: try the others, the crops and the mirror.

## 2. Text search

Use **your own web search tool** first: it is unblocked where the CLI may not be, and it reaches far more
of the web. Run many short queries rather than one long one, and log them (`IGL log <case> text_search
--query "..." --status ...`).

- Quote exact strings exactly as written in the photo, in the original script: shop names, slogans,
  menu items, notice texts, phone numbers in local format, URLs, Wi-Fi names.
- Add the place hypothesis: `"<string>" <city>`, `site:<country TLD>`, or the local-language word for
  hotel or restaurant.
- Describe what is unusual: `hotel room "round bathtub" "glass wall" <city>`,
  `restaurant "blue tiles" "copper bar" <city>`. Use the local language. Translate key nouns with your
  own knowledge and keep both versions.
- Use several engines when you can: Google, Bing and DuckDuckGo; Yandex (Russian-speaking web), Baidu
  (Chinese), Naver (Korean), Yahoo! JAPAN (Japanese), Seznam (Czech). Fetch result pages of regional engines
  with your web fetch or browser tool when your search tool does not cover them.
- Platform targeting: `site:booking.com`, `site:tripadvisor.com`, `site:airbnb.com`, `site:<portal>`
  (section 5), and `site:` for social platforms (section 3).
- Phone numbers: `IGL lookup phone "+43 1 234567"` gives the country, the region and often the city.
  Then search the number in quotes in local formats (with and without spaces, with the trunk 0).
- Read the pages you find with your web fetch tool (or `IGL snapshot <case> <url>` to keep a page as
  evidence). A page that names a venue is `reported` (source `web`) until the pixels confirm it.
- Turn a named candidate into pictures at once: `IGL refs <case> "<venue> <city> <room type>" --for C#`.

## 3. Social media (place-focused)

Social platforms hold the richest interior photos: location tags, room tours, check-ins, reviews.
**Search for the place, its text, its tags and the photo itself, never for people** (SKILL.md, "People, privacy and conduct").
Do not open a poster's other posts beyond the same post or album. Do not track anyone across
platforms. Never use face search.

**Keyless open APIs (automated):**
`IGL social search "<query>" --case <case> [--sheet 12] [--tag <hashtag>] [--lang xx]`.

| Source | What it gives |
|---|---|
| Bluesky (`app.bsky.feed.searchPosts`) | full-text post search with images and alt text |
| Flickr public feeds | the latest photos carrying all the given tags (e.g. `hotel,sacher,wien`) |
| Openverse | openly licensed images from Flickr, Wikimedia and others, searched by text |
| Mastodon hashtag timeline (default mastodon.social) | recent federated posts with that hashtag |
| Lemmy | federated forum posts (Reddit-like) |

Each source's outcome is logged automatically as a `social_search` attempt. `--sheet 12` writes a
contact sheet of the images so you can compare them visually.

**Platforms that need a browser (and often a login):** `IGL social links "<query>" [--only ...]` prints
two kinds of link:
- search-engine `site:` queries that reach publicly indexed posts without a login (Instagram, TikTok, X,
  Facebook, Reddit, YouTube, Pinterest, Threads, VK via Yandex, Xiaohongshu and Weibo via Baidu, Korean
  blogs on Naver and Daum, X posts on Yahoo! JAPAN realtime search);
- the platforms' own search pages.

Open them with your browser tool. If a platform wants a login, use it only when the user is already
signed in and allows it. Never create accounts, never sign in for the user, never solve CAPTCHAs.

**Which platforms by region:**

| Region | Where interiors get posted |
|---|---|
| Global | Instagram (location tags), TikTok (room tours), YouTube (walk-throughs), Pinterest, Facebook, Reddit (r/whereisthis, r/geoguessr, city subreddits), Flickr |
| China | Xiaohongshu 小红书 (hotels, cafés, flats), Douyin 抖音, Weibo 微博, Bilibili, Dianping 大众点评 |
| Japan | Instagram, X (very active; Yahoo! JAPAN realtime search works without a login), Tabelog, Ameba blogs, note |
| Korea | Naver Blog and Cafe, Instagram, Kakao Map reviews, Daum blogs |
| Russia and CIS | VK, Telegram channels (`t.me/s/<channel>?q=<word>` searches inside one public channel), Yandex Maps reviews |
| Taiwan, Hong Kong | Instagram, Facebook, Threads, Dcard (TW), OpenRice (HK) |
| SE Asia | Facebook, Instagram, TikTok, Lemon8 |
| Middle East | Instagram, Snapchat, X, TikTok |
| Latin America | Instagram, Facebook, TikTok |

**Recipes:**
- **Venue confirmation:** `<venue name>` and the hashtag form (`#hotelsacherwien`) on Instagram, TikTok
  and Xiaohongshu. Location-tag pages collect guests' photos, which make good independent reference
  imagery (`IGL refs <case> --image <url>` for the ones you can reach, your own eyes in the browser for
  the rest).
- **Find the photo's origin:** search a distinctive caption-like description, or the visible text, plus
  the city. A post that carries the same photo is provenance: read its caption, date and location tag,
  and record it as `traced` when it is the photographer's own post or the venue's page (`reported` for
  a repost).
- **Room-type match:** `<hotel> room tour` or `<hotel> <room type>` on YouTube and TikTok. Videos show
  every wall, the bathroom and the view.
- **Local language:** run the same searches in the local language and script (ホテル, 酒店, 호텔,
  отель).

**Weighting:** a caption or location tag is `reported` (source `web`). Users mis-tag places, especially
nearby big venues. It becomes strong only after a visual match (verification.md), or when two unrelated
posters agree.

## 4. Provenance hunting

Where did the photo come from? Once found, the original often states the place.

- `init` already reports the filename pattern (app, date), EXIF software, platform traces and
  watermarks. Search for the watermark text or the photographer or agency name.
- Use TinEye "oldest" and Lens "Exact matches" to find the earliest copy. Read that page's caption,
  alt text, album title and comments.
- Inside the same post or album, other photos often show the exterior, the view or a receipt. Use them
  (`IGL refs <case> --url <page> --for C#` compares them all with your photo). Do not go beyond that
  post or album into the person's life.
- Stock photos: agencies (Getty, Shutterstock, Adobe Stock, Alamy) often give a location in the caption.
- Record what the origin says as a `traced` clue: `--kind provenance --status traced --source web --url
  <page> --file <the sheet or JSON that shows the COPY>` (LR 10–20 for the venue's own page, its listing
  or the photographer's post; `reported`, LR ≤6, for aggregators and reposts). Check first whether the
  same picture also illustrates other venues: then it is a brand or stock image.
- Log `provenance_hunt`.

## 5. Listing and review platforms by country

Hotels (global): the hotel's own site, Booking.com, Expedia/Hotels.com, Agoda (strong in Asia),
Trip.com, Tripadvisor (traveller photos), Google Hotels. Short-term rentals: Airbnb, Vrbo,
Booking.com apartments. Restaurants and venues: Google Maps, Tripadvisor, Yelp, Foursquare.

| Country / region | Hotels and rentals (regional) | Real estate (sale / rent) | Reviews |
|---|---|---|---|
| United States | — | Zillow, Redfin, Realtor.com, Trulia, Apartments.com, StreetEasy (NYC), Craigslist | Yelp |
| Canada | — | Realtor.ca, Centris (QC), Kijiji | Yelp |
| United Kingdom | — | Rightmove, Zoopla, OnTheMarket, SpareRoom | Tripadvisor |
| Ireland | — | Daft.ie, MyHome.ie | |
| Germany | HRS | ImmobilienScout24, Immowelt, Kleinanzeigen, WG-Gesucht | |
| Austria | — | willhaben, ImmobilienScout24.at | |
| Switzerland | — | Homegate, ImmoScout24.ch, Comparis, Flatfox | |
| France | — | SeLoger, Leboncoin, PAP, Bien'ici | TheFork |
| Belgium / Netherlands | — | Immoweb, Zimmo / Funda, Pararius, Kamernet | |
| Spain / Portugal | — | Idealista, Fotocasa, Habitaclia / Idealista, Imovirtual, Casa Sapo | TheFork |
| Italy | — | Immobiliare.it, Idealista.it, Casa.it, Subito | TheFork |
| Nordics | — | Hemnet, Blocket, Booli (SE); Finn.no (NO); Boligsiden, Boliga (DK); Oikotie, Etuovi (FI) | |
| Poland / Czechia / Hungary / Romania / Greece | — | Otodom, OLX / Sreality, Bezrealitky / ingatlan.com / imobiliare.ro, Storia / Spitogatos, xe.gr | |
| Turkey | — | Sahibinden, Hepsiemlak, Emlakjet | |
| Russia / Ukraine / Kazakhstan | Ostrovok | Cian (ЦИАН), Avito, DomClick / DOM.RIA, OLX.ua, LUN / Krisha.kz | Yandex Maps, 2GIS |
| Israel | — | Yad2, Madlan | |
| UAE / Saudi Arabia / Egypt | — | Bayut, Property Finder, Dubizzle / Aqar / Aqarmap, Property Finder | |
| India / Pakistan | MakeMyTrip, Goibibo, OYO | MagicBricks, 99acres, Housing.com, NoBroker / Zameen.com | Zomato |
| China | Ctrip 携程 (Trip.com), Meituan 美团, Fliggy 飞猪 | Lianjia 链家, Beike 贝壳, Anjuke 安居客, 58.com, Ziroom 自如 | Dianping 大众点评 |
| Hong Kong | — | Centaline 中原, Midland 美聯, 28Hse, Spacious, Squarefoot | OpenRice |
| Taiwan | — | 591, Sinyi 信義, Yungching 永慶 | |
| Japan | Rakuten Travel, Jalan じゃらん, Ikyu 一休 | SUUMO, LIFULL HOME'S, at home, CHINTAI | Tabelog 食べログ |
| Korea | Yanolja 야놀자, Yeogi-eottae 여기어때 | Naver Real Estate, Zigbang 직방, Dabang 다방 | Naver Map, Kakao Map |
| Singapore / Malaysia | — | PropertyGuru, 99.co, EdgeProp / PropertyGuru, iProperty, Mudah.my | |
| Thailand / Vietnam / Indonesia / Philippines | Traveloka (SE Asia) | DDproperty, Hipflat / Batdongsan.com.vn / Rumah123, Lamudi / Lamudi, Dot Property | Wongnai (TH) |
| Brazil / Mexico / Argentina / Chile / Colombia | — | ZAP Imóveis, Viva Real, QuintoAndar / Inmuebles24, Vivanuncios / Zonaprop, Argenprop / Portal Inmobiliario / Finca Raíz, Metrocuadrado | |
| South Africa / Nigeria / Kenya | — | Property24, Private Property / PropertyPro, Nigeria Property Centre / BuyRentKenya | |
| Australia / New Zealand | — | realestate.com.au, Domain / Trade Me Property, realestate.co.nz | |

How to use them: listings carry the street or the building, a floor plan, and many photos of every room
and the view. Search `site:<portal> "<distinctive feature>"`, or browse the candidate district's
listings with the portal's filters (type, size, floor). The same flat is often re-listed for years,
which gives more photos. Log `listing_search`.

## 6. Maps, 360° tours and photo collections

- **Google Maps**: business photos (owner and user), indoor Street View ("See inside") for many
  hotels, shops and restaurants, and date-stamped reviews with photos. Use a browser tool.
- **Yandex Maps** (RU and CIS: photos and panoramas), **2GIS** (RU and CIS: photos), **Naver Map** and
  **Kakao Map** (KR: business photos and some indoor panoramas), **Baidu Maps** and **Amap 高德** (CN).
- **Wikimedia Commons**: `IGL geo photos --at <lat,lon> --radius 300 --sheet 12 --case <case>`, by
  category (`--category "Interior of Hotel Sacher"`), or by text. Wikidata `P373` names a candidate's
  Commons category (`geo wikidata ... --details`).
- **Openverse**, Flickr, Mapillary and KartaView (mostly street-level, useful for the view). Use
  `IGL social search` for Flickr and Openverse.
- **360° tours**: Matterport (real estate), hotel websites, Kuula; search `"<venue>" matterport` or
  `"<venue>" 360`.
- Log `map_photos`.

## 7. OpenStreetMap enumeration (Overpass)

`IGL geo poi` builds and runs bounded Overpass queries (each mirror is tried once):

```
IGL geo poi --tag tourism=hotel --brand "Hampton" --area "Berlin" --case C --add site --parent C3
IGL geo poi --tag "brand:wikidata=Q5646230" --area "Berlin"          # brand by Wikidata id (most reliable)
IGL geo poi --tag amenity=cafe --name "blue bottle" --around 35.66,139.70,3000
IGL geo poi --tag tourism=hotel --around 48.2085,16.3731,800 --near-tag amenity=place_of_worship@150
IGL geo poi --tag shop=supermarket --bbox 47.0,15.3,47.1,15.5 --save --case C
```

Useful tags:
- Lodging: `tourism=hotel|hostel|guest_house|apartment|motel`.
- Food and drink: `amenity=restaurant|cafe|bar|pub|fast_food`.
- Shops: `shop=*` (supermarket, convenience, mall, department_store, clothes ...).
- Culture and worship: `tourism=museum`, `amenity=theatre|cinema|library|place_of_worship`
  (+ `religion=*`, `denomination=*`).
- Institutions: `amenity=hospital|clinic|school|university`, `office=*`.
- Transport: `railway=station`, `station=subway`, `aeroway=terminal`.
- Brands: `brand`, `brand:wikidata`, `operator`.
- Building facts: `building:levels`.

`--near-tag` chains co-location constraints. "A hotel within 150 m of a church that is within 300 m of
a river" encodes what the window shows. Bound the area (a city bbox or `--around`) so queries finish.

Overpass refuses many cloud networks. When no mirror answers, `geo poi` falls back to Photon (a name and
tag search inside the box, at most 50 results) and says so: that list is a lower bound, so complete it
with your web search ("hotels in <town>", the booking and map listings for the town), `IGL geo search
"<kind> in <town>" --limit 40`, Wikidata SPARQL, or the brand's own location list. Then screen the
candidates with pictures: `IGL refs <case> "<venue> <town> <room type>" --for C#` for each. Enumeration
is only finished when the venues you could not rule out have been looked at.

## 8. Wikidata and SPARQL

- `IGL geo wikidata "<name>" --details` gives the Q-id, coordinates, address, website, image, Commons
  category and inception (opening date).
- `IGL geo sparql '<query>' [--case C --add site --parent C#]` runs any query. Select `?item`,
  `?itemLabel` and `?coord`, and the rows become candidates with `--add`.

Templates (replace the Q-ids: find them with `geo wikidata "<name>"`; WKT points are `Point(lon lat)`):

```sparql
# 1. Every venue of a class around a point (fast). Classes: hotel Q27686, museum Q33506,
#    church building Q16970, mosque Q32815, railway station Q55488, metro station Q928830,
#    shopping center Q11315, restaurant Q11707, theatre building Q24354, concert hall Q1060829,
#    hospital Q16917, university Q3918, school Q3914, library Q7075, airport Q1248784, stadium Q483110
SELECT ?item ?itemLabel ?coord WHERE {
  SERVICE wikibase:around { ?item wdt:P625 ?coord.
    bd:serviceParam wikibase:center "Point(16.3731 48.2085)"^^geo:wktLiteral; wikibase:radius "3". }
  ?item wdt:P31/wdt:P279* wd:Q27686.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }

# 2. Every property of a brand (P1716 brand, P137 operator, P127 owned by); coverage is partial
SELECT ?item ?itemLabel ?coord WHERE {
  ?brand rdfs:label "Hampton by Hilton"@en. ?item wdt:P1716 ?brand; wdt:P625 ?coord.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }

# 3. Stations of a line (P81 connecting line)
SELECT ?item ?itemLabel ?coord WHERE {
  ?line rdfs:label "Ginza Line"@en. ?item wdt:P81 ?line; wdt:P625 ?coord.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }

# 4. Churches dedicated to a saint (P825) in a country (P17): get the saint's Q-id first
SELECT ?item ?itemLabel ?coord WHERE {
  ?item wdt:P825 wd:Q_SAINT; wdt:P17 wd:Q40; wdt:P625 ?coord.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "de,en". } }

# 5. Where an artwork is (P276 location, P195 collection); titles repeat, so check P170 (creator)
SELECT ?item ?itemLabel ?creatorLabel ?locLabel ?coord WHERE {
  ?item rdfs:label "The Kiss"@en; wdt:P276 ?loc. OPTIONAL { ?item wdt:P170 ?creator. }
  ?loc wdt:P625 ?coord. SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }
```

Template 5 returns 44 works titled "The Kiss" (Klimt, Rodin casts in several museums, Hayez ...), and
some locations are coarse ("France" at the country centroid), so check the creator and drop
country-level points. Avoid `wdt:P131*` (transitive "located in") over big areas: it times out. Use
the `around` service.

## 9. Wi-Fi names and AI estimators

- **SSID** (from a Wi-Fi card, QR or screenshot): WiGLE (wigle.net) maps networks by name. It needs the
  user's free API key, so ask, or log `wifi_ssid` as unavailable. Venue-named SSIDs often show up
  in a plain web search too.
- **AI geolocation estimators** (GeoSpy, Picarta and similar): opaque guesses. Use them only as an
  `engine` hint (the ledger caps engine leads at LR 3) to suggest where to look, never as evidence on
  their own. They need accounts or keys. Log `ai_estimate`.

## 10. Never do

- Face search or person search (PimEyes, FaceCheck, social "people" search), profiling the poster, or
  de-anonymising anyone.
- Logging in on the user's behalf, creating accounts, solving CAPTCHAs, bypassing paywalls or rate
  limits, or bulk scraping.
- Retrying an unchanged failing request. Switch route, and log `blocked` or `unavailable`.
- Treating a no_results from a blocked or unavailable service as an observed absence.
- Naming a venue because an engine listed it. A hit is a lead until its photos have been compared.
- Sharing a photo the user marked private (`IGL share` or any upload) without asking first, or sharing
  identifiable private people when a crop without them would do.
