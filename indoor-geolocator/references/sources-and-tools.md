# Sources and tools

What each command talks to, what it needs, how it fails, and the etiquette that keeps it working.
Reachability differs by network: `IGL init` checks the main services in five seconds and says what the
CLI can reach right now; `IGL doctor` checks everything, including whether headless Chromium starts.

Cloud sandboxes (claude.ai, Cowork, hosted agents) leave through shared addresses. Public services
rate-limit those addresses, some refuse them outright, and search engines show them CAPTCHAs or decoy
pages. Measured from such a sandbox (2026-11): Overpass unreachable on every mirror; Nominatim, Wikimedia
Commons and Wikidata answering HTTP 429 on and off; Open-Meteo's daily quota used up; Google (Lens,
Images), Bing and DuckDuckGo refusing headless clients; Yandex and TinEye reverse search, Brave and
Startpage image search, Photon, the Wikidata Query Service, Hugging Face and the temporary hosts working. Every
command therefore reports per run whether a service answered, and has a fallback or says which route
to use instead.

Contents: 0 tool routing · 1 command → service map · 2 failure semantics · 3 alternatives · 4 offline
data · 5 browser tools · 6 uploads and temporary copies · 7 runtime notes · 8 the similarity model

## 0. Tool routing: three families, use all you have

| Family | Strengths | Use it for |
|---|---|---|
| `IGL` (this CLI) | deterministic, records everything in the ledger, compares pictures objectively | metadata, codes, crops, tiles, standards tables, sun and bearings, the ledger; reverse search with triage (`revsearch`), reference photos (`refs`), `compare`; geodata when the service answers |
| Your own web search and web fetch tools | unblocked where the sandbox is not, broad coverage, many languages | every text search, reading listings, captions, reviews, news, regional search engines, API URLs from `--print-url` |
| A browser tool (Claude in Chrome, the built-in browser) | runs where the user is (a residential address, the user's sessions), renders JavaScript, takes screenshots | **Google Lens and Bing** (the by-URL links from `revsearch` / `IGL share`), Google Maps photos and indoor Street View, Booking/Airbnb/Tripadvisor galleries, social platforms, Google Earth 3D |

When the CLI is offline, keep using it for the offline work and the ledger, do the online steps with
your own tools, and record their results with `IGL note`, `IGL cand` (with `--at`, `--address`, `--url`)
and `IGL log`. `IGL geo <cmd> ... --print-url` prints the exact API request (Nominatim, Photon, Overpass,
Commons, Wikidata, SPARQL, time zone, weather) so your fetch tool can run it.

## 1. Command → service map

| Command | Service (keyless unless noted) | Policy and notes |
|---|---|---|
| `init`, `scan`, `crop`, `tiles`, `compare` (local files) | offline: Pillow, tesseract or RapidOCR, OpenCV | nothing leaves the machine (`compare` downloads reference URLs you give it); `init` sends one short probe to each main service |
| `refs` | Brave Search and Startpage image search via headless Chromium; the pages given with `--url`; the pictures' hosts; huggingface.co once, for the similarity model (section 8) | sends only your search text (never the photo); one page load per search, human pace; a provider that refuses is not asked again in that run |
| `countries`, `lookup` | offline tables in `data/` (section 4) | — |
| `sun`, `bearing` | offline (NOAA solar algorithm, great-circle math) | checked against NREL SPA (pvlib) within 0.05° and WGS84 geodesics within 0.13° |
| `geo search`, `geo reverse`, `answer` | Nominatim (OSM), Photon (komoot) fallback | ≤1 request/s, identifying User-Agent, no bulk geocoding |
| `geo poi` | Overpass API: overpass-api.de, then kumi.systems, maps.mail.ru, private.coffee; Photon when none answers | bounded areas; each mirror tried once, 150 s overall; the Photon fallback is a partial list (≤50, name and tag search in the box) |
| `geo photos` | Wikimedia Commons API | User-Agent, ~1 request/s; shared IPs get HTTP 429 (the client waits when told to) |
| `geo wikidata` | Wikidata API | — |
| `geo sparql` | Wikidata Query Service | 60 s server limit; use `wikibase:around`, avoid `P131*` over large areas |
| `geo timezone` | timeapi.io + local zoneinfo | the offset at capture time is computed locally |
| `geo weather` | Open-Meteo (ERA5 archive; forecast API for the last ~6 days) | free non-commercial tier, daily quota per IP; ~10–25 km grid |
| `geo wigle` | WiGLE API, **needs the user's free key** (`WIGLE_API_NAME`, `WIGLE_API_TOKEN`) | small daily query allowance; MAC addresses are not reported |
| `geo ... --print-url` | nothing is sent | prints the request URL(s) for your own fetch tool |
| `social search` | Bluesky AppView, Flickr public feeds, Openverse, Mastodon (hashtag timeline), Lemmy | open APIs; low volume; place-focused only |
| `social links` | none: prints URLs for a browser tool | — |
| `revsearch` | Yandex Images, TinEye, Baidu 识图 via headless Chromium (Playwright); Bing and Lens only with `--engines`; Google Lens through SerpApi when `SERPAPI_KEY` is set | one search per engine and image, low volume; upload form first, by URL when the upload does not start a search (a temporary copy, see `share`; `--no-share` forbids it); result images are downloaded to compare them with the photo |
| `share` | uguu.se (3 h), then litterbox.catbox.moe (1 h), then tmpfiles.org (60 min) | a metadata-free JPEG; prints by-URL links for Lens, Bing, Yandex, TinEye |
| `snapshot` | the given URL via headless Chromium (plain fetch without it) | keeps a screenshot and the page text (secrets redacted) as evidence |

Set `IGL_USER_AGENT` to identify your deployment (e.g. with a contact address) if you run the skill at
volume.

## 2. Failure semantics

- `ok: False` with status 0 means the network or proxy failed: **unavailable**. HTTP 403 or 429, a
  login wall or a CAPTCHA means **blocked**. A reverse search whose upload was never processed is
  **unavailable** too. None of these is an absence of results, and none may be reported as no_results.
- `no_results` means the service worked and found nothing relevant. That is an observed absence and can
  justify a modest down-weight.
- "unconfirmed" on a hit or a reference means the automatic comparison found nothing. It is not a
  failure and not a verdict: compare by eye (verification.md sections 4-5).
- An empty OCR result is normal for a photograph of a room. The OCR output is filtered for precision
  (texture is not reported as text), so it can miss stylised or tiny print that you can read yourself.
- On failure, switch route (the alternatives are in the next section). Never retry an unchanged request
  in a loop. The HTTP client already retries transient 429/5xx errors briefly, and stops at once when
  the server asks for a long wait (daily quota).

## 3. Alternatives when a route is closed

| Closed route | Alternatives |
|---|---|
| CLI offline (sandbox without egress) | your own web search, web fetch and browser tools for every online step; `geo ... --print-url`; record with note / cand / log |
| Lens or Bing blocked headless (the normal case) | the by-URL links from `revsearch` / `IGL share` in a browser tool; `SERPAPI_KEY` for Lens through SerpApi; ask the user to run Lens on the photo and paste what it shows |
| Yandex CAPTCHA | wait and try once later; TinEye and Baidu; the browser tool; crops through `share` links |
| Brave or Startpage refuse `refs` | the other provider (`--providers startpage`); `--url <the venue's gallery>`; `--image <urls from your web search or browser>`; maps photos in the browser tool |
| A gallery page shows a bot wall to `refs --url` | image search texts instead (the same pictures are indexed); the page in your browser tool |
| No temporary host reachable for `share` | upload the file in the browser tool; ask the user to run Lens on the photo |
| No Playwright / Chromium | `pip install playwright && playwright install chromium`; until then the browser tool for reverse search and galleries, `refs --image <urls>` for the comparison, `snapshot` falls back to a plain fetch |
| Overpass down (the normal case from cloud networks) | `geo poi` falls back to Photon by itself (partial list); your web search for "<kind> in <town>"; `geo search "<brand> <city>" --limit 40`; `geo sparql`; the brand's location list; overpass-turbo.eu in a browser; `geo poi --print-url` for your fetch tool |
| Nominatim refuses | Photon (automatic), Wikidata coordinates, the venue's website, your web search |
| Commons rate-limited | wait a minute once; Openverse via `social search --sources openverse`; Flickr; your browser |
| Instagram, TikTok, X, Facebook login walls | `social links` engine queries (`site:` searches reach indexed posts), Yahoo! JAPAN realtime search for X, the user's existing browser session if they allow it |
| Open-Meteo quota | skip weather (log consistency without it); check the visible weather against a news or METAR archive in a browser |
| No OCR engine, or OCR found nothing | read the tiles and crops yourself (`crop --enhance auto` at high scale), then record as `read` |
| No OpenCV | `revsearch`, `refs` and `compare` still write their sheets, every item "unchecked": compare invariant features by eye |
| No similarity model (no `onnxruntime`, or huggingface.co unreachable) | the sheets keep the search engine's order: write more of them (`refs --sheets 4`), use narrower search texts, and compare more tiles by eye |

## 4. Offline data (`data/`)

- `countries.json` (257 countries and territories): names and alternative names, UN region, calling
  codes, currencies (current and former), languages with script, share and official status, first
  day of the week, clock format, measurement system, temperature unit and paper size (all from the
  Unicode CLDR); plug types, voltage, frequency, driving side and emergency numbers (from Wikipedia
  tables); the ccTLD (derived from the ISO code, `.uk` for GB).
- `gs1_prefixes.json`: GS1 company-prefix ranges → issuing member organisation.
- Provenance, versions and licences: [data/README.md](../data/README.md). The repository's
  `tools/build_data.py` rebuilds both files from the sources. Tables describe the norm: older buildings,
  hotels and expat housing deviate, which is why table-based clues are `observed`-capped evidence and
  not proof.

## 5. Browser tools

Use Claude in Chrome or the built-in browser for:
- Google Lens and Bing Visual Search: open the links from `IGL share`, or upload the file;
- Google Maps photos and indoor Street View;
- listings and review sites;
- social platforms (`social links`);
- Google Earth 3D;
- pages that need JavaScript.

When the browser shows something decisive, save it: `IGL snapshot <case> <url>` (headless), or take a
screenshot in the browser and keep it with `IGL note ... --file <path>`. A screenshot of a reference
photo can go straight into `IGL compare --ref <file>`.

Rules:
- Use only sessions the user already has, and only with their consent.
- Never create accounts, sign in for the user, solve CAPTCHAs, or get around paywalls or rate limits.
- Keep to normal, human-scale browsing: no bulk scraping.

## 6. Uploads and temporary copies

Reverse search uploads the photo (or crops) to the engines. `share` puts a copy on a temporary public
host for up to three hours, and `revsearch` does the same on its own when an engine's upload form does
not start a search (`--no-share` prevents it). Every copy is re-encoded without metadata (no EXIF GPS
leaves), and `REPORT.md` lists every engine and every temporary copy. `refs` never sends the photo: it
sends search text and downloads public pictures.
- If the user marked the photo as sensitive or private, ask before any upload or share.
- Prefer crops that leave out people.
- Never upload images of identifiable private individuals to face-search services. That is forbidden in
  every case.

## 7. Runtime notes

- Long commands: `scan` (OCR budget 150 s by default; `--fast` or `--budget`), `revsearch` (20-60 s per
  image, more when an upload falls back to the URL route), `refs` (about a minute for two searches and
  100 pictures), `geo poi` with failing mirrors (up to ~2.5 min), `compare` (a second or two per
  reference). Give the shell a generous timeout (e.g. 5 min).
- Optional keys, all the user's own, read from the environment: `SERPAPI_KEY` (Google Lens inside
  `revsearch`), `WIGLE_API_NAME` + `WIGLE_API_TOKEN` (Wi-Fi names). Nothing needs a key to work.
- Other environment switches: `IGL_USER_AGENT` (section 1), `IGL_MODEL_DIR` and `IGL_NO_EMBED`
  (section 8).
- Southern and western coordinates work directly (`--at -33.86,151.21`).
- Everything is written inside the case folder. `finalize` deletes `.work/` (cache, tiles, downloads)
  and every evidence file the ledger does not cite.

## 8. The similarity model

`refs` and `revsearch` sort the pictures that the feature test left unconfirmed by visual similarity to
the photo, so that the likeliest references are the first tiles you look at. The score (`sim`) comes
from DINOv2 ViT-S/14 (Meta AI, Apache-2.0) in an 8-bit ONNX export (`Xenova/dinov2-small`, 24 MB),
run locally with `onnxruntime` on the CPU: about 0.1 s per picture. It compares patch by patch, so a
shared part of a room counts even when the rest of the frame differs.

- **It orders. It never classifies.** A high `sim` means "looks alike", which is true of the same room
  and of a good look-alike. A low `sim` does not exclude a photo of the same room from the opposite
  corner. As rough orientation from the test cases: about 0.80 and more for the same room seen from a
  similar side, 0.60–0.80 for other interiors (good look-alikes at the upper end), and below 0.5 for
  pictures that are not comparable at all (food, exteriors, logos).
- **The model is not part of the skill.** The first `refs` or `revsearch` that needs it downloads it
  once from huggingface.co (a pinned revision, checked against a SHA-256) into
  `~/.cache/indoor-geolocator/`, or into `IGL_MODEL_DIR` when that is set. The case records the
  download among the online services. Nothing about the photo is sent: the model runs on this machine.
- **It is optional.** Without `onnxruntime` and numpy, without access to huggingface.co, or with
  `IGL_NO_EMBED=1`, the commands work as before and keep the source's own order. `IGL init` and `IGL
  doctor` say which of the three it is.
