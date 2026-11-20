# Sources and tools

What each command talks to, what it needs, how it fails, and the etiquette that keeps it working. Run
`IGL doctor` once per environment: it lists the installed components and probes every service.
Reachability differs by network, so a service that fails in one sandbox may work on the user's
machine.

## 1. Command → service map

| Command | Service (keyless unless noted) | Policy and notes |
|---|---|---|
| `init`, `scan`, `crop`, `tiles`, `compare` (local files) | offline: Pillow, tesseract or RapidOCR, OpenCV | nothing leaves the machine |
| `countries`, `lookup` | offline tables in `data/` (section 4) | — |
| `sun`, `bearing` | offline (NOAA solar algorithm, great-circle math) | checked against NREL SPA (pvlib) within 0.05° and WGS84 geodesics within 0.13° |
| `geo search`, `geo reverse`, `answer` | Nominatim (OSM), Photon (komoot) fallback | ≤1 request/s, identifying User-Agent, no bulk geocoding |
| `geo poi` | Overpass API: overpass-api.de, then kumi.systems, maps.mail.ru, private.coffee | bounded areas; each mirror tried once, 150 s overall; a slow mirror can make it take ~2.5 min |
| `geo photos` | Wikimedia Commons API | User-Agent, ~1 request/s |
| `geo wikidata` | Wikidata API | — |
| `geo sparql` | Wikidata Query Service | 60 s server limit; use `wikibase:around`, avoid `P131*` over large areas |
| `geo timezone` | timeapi.io + local zoneinfo | the offset at capture time is computed locally |
| `geo weather` | Open-Meteo (ERA5 archive; forecast API for the last ~6 days) | free non-commercial tier, daily quota per IP; ~10–25 km grid |
| `geo wigle` | WiGLE API, **needs the user's free key** (`WIGLE_API_NAME`, `WIGLE_API_TOKEN`) | small daily query allowance; MAC addresses are not reported |
| `social search` | Bluesky AppView, Flickr public feeds, Openverse, Mastodon (hashtag timeline), Lemmy | open APIs; low volume; place-focused only |
| `social links` | none: prints URLs for a browser tool | — |
| `revsearch` | Yandex Images, TinEye via headless Chromium (Playwright); Bing and Lens attempted only on request | low volume; Lens and Bing usually block headless use, so use a browser tool |
| `snapshot` | the given URL via headless Chromium | keeps a screenshot and text as evidence |

Set `IGL_USER_AGENT` to identify your deployment (e.g. with a contact address) if you run the skill at
volume.

## 2. Failure semantics

- `ok: False` with status 0 means the network or proxy failed: **unavailable**. HTTP 403 or 429, a
  login wall or a CAPTCHA means **blocked**. Neither is an absence of results, and neither may be
  reported as no_results.
- `no_results` means the service worked and found nothing relevant. That is an observed absence and can
  justify a modest down-weight.
- On failure, switch route (the alternatives are in the next section). Never retry an unchanged request
  in a loop. The HTTP client already retries transient 429/5xx errors briefly, and stops at once when
  the server asks for a long wait (daily quota).

## 3. Alternatives when a route is closed

| Closed route | Alternatives |
|---|---|
| Lens or Bing blocked headless | the browser tool (upload, or `lens.google.com/uploadbyurl?url=`), Yandex, TinEye, Baidu, Naver; ask the user |
| Overpass down | `geo search "<brand> <city>" --limit 40`, `geo sparql`, the brand's location list, overpass-turbo.eu in a browser |
| Nominatim refuses | Photon (automatic), Wikidata coordinates, the venue's website |
| Commons rate-limited | wait a minute once; Openverse via `social search --sources openverse`; Flickr |
| Instagram, TikTok, X, Facebook login walls | `social links` engine queries (`site:` searches reach indexed posts), Yahoo! JAPAN realtime search for X, the user's existing browser session if they allow it |
| Open-Meteo quota | skip weather (log consistency without it); check the visible weather against a news or METAR archive in a browser |
| No OCR engine | read crops yourself (`crop --enhance auto` at high scale), then record as `read` |
| No Playwright | the browser tool for reverse search; `revsearch` prints the manual steps |

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
- Google Lens and Bing Visual Search;
- Google Maps photos and indoor Street View;
- listings and review sites;
- social platforms (`social links`);
- Google Earth 3D;
- pages that need JavaScript.

When the browser shows something decisive, save it: `IGL snapshot <case> <url>` (headless), or take a
screenshot in the browser and keep it with `IGL note ... --file <path>`.

Rules:
- Use only sessions the user already has, and only with their consent.
- Never create accounts, sign in for the user, solve CAPTCHAs, or get around paywalls or rate limits.
- Keep to normal, human-scale browsing: no bulk scraping.

## 6. Uploading the photo

Reverse search uploads the photo (or crops) to third parties, and `REPORT.md` lists which engines
received it.
- If the user marked the photo as sensitive or private, ask before uploading.
- Prefer crops that leave out people.
- Never upload images of identifiable private individuals to face-search services. That is forbidden in
  every case.

## 7. Runtime notes

- Long commands: `scan` (OCR budget 150 s by default; `--fast` or `--budget`), `revsearch` (about 1–2
  min), `geo poi` with failing mirrors (up to ~2.5 min). Give the shell a generous timeout (e.g. 5 min).
- Southern and western coordinates work directly (`--at -33.86,151.21`).
- Everything is written inside the case folder. `finalize` deletes `.work/` (cache, tiles, downloads)
  and every evidence file the ledger does not cite.
