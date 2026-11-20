#!/usr/bin/env python3
"""igl.py - the indoor-geolocator toolbox (one entry point, many subcommands).

    python3 igl.py <command> [options]          python3 igl.py <command> -h   for details

Case lifecycle
  init IMAGE [--out DIR]           new case folder: copy, metadata, overview grid
  scan CASE                        OCR (multi-pass), QR/barcodes, text signals, tiles for the visual sweep
  crop CASE --cell C3:E5|--box ..  zoomed / enhanced crop saved as evidence
  tiles CASE --grid 4x4            regenerate sweep tiles
  revsearch CASE [--cell ..]       reverse image search (headless Yandex/TinEye; manual Lens/Bing guidance)
  social search|links QUERY        social media: keyless open APIs + ready search links (place-focused)
  snapshot CASE URL                preserve a web page (screenshot + text) as evidence
  compare CASE --ref URL|E## ..    side-by-side sheet: photo vs reference images
Knowledge (offline)
  countries [--plug G --currency £ --drive left ...] [--case CASE --clue N3]   intersect fixed standards
  lookup phone|barcode|country|plug|plugs|currency|tld|text VALUE
Geodata (online, keyless) and geometry (offline)
  geo search|reverse|poi|photos|wikidata|sparql|timezone|weather|wigle ...
  sun --at LAT,LON --time ISO      bearing --from LAT,LON --to LAT,LON|qibla [--facing DEG]
Ledger
  note CASE "TEXT" --kind K --status S --source L [--file E##]   record a clue
  cand CASE "NAME" --level L [--parent C#] [--at LAT,LON]        add/update a candidate
  link CASE N# --for C#:LR [--against C#:LR] --why ".."           evidence -> candidates (LR capped by status)
  exclude CASE C# --by N# --why ".." --file E##                   decisive exclusions only
  log CASE METHOD --status S --detail ".."                        record a method attempt
  rank | check | status CASE                                      ranking, pre-report audit, overview
  answer CASE C# [--confidence ..] --summary ".."                 final answer (confidence capped by the rules)
  report CASE | finalize CASE                                     REPORT.md + result.json; prune scratch
Environment
  doctor [--offline]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True        # keep the installed skill folder free of __pycache__/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from iglib import __version__  # noqa: E402
from iglib.util import IglError, utf8_console  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="igl.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"indoor-geolocator {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="command")

    def add(name, help_):
        return sub.add_parser(name, help=help_, description=help_, formatter_class=argparse.RawDescriptionHelpFormatter)

    def region(p):
        g = p.add_mutually_exclusive_group()
        g.add_argument("--box", help="x0,y0,x1,y1 in pixels of the upright image")
        g.add_argument("--cell", help="grid cell(s) from the overview view: C3 or C3:E5")
        g.add_argument("--rel", help="relative box x0,y0,x1,y1 in 0..1")

    p = add("init", "create a case folder for one photo (never overwrites)")
    p.add_argument("image")
    p.add_argument("--out", help="case folder to create (default: <outputs or cwd>/<image>-geolocation)")

    p = add("scan", "automatic perception pass: OCR, QR/barcodes, text signals, sweep tiles")
    p.add_argument("case")
    p.add_argument("--langs", help="force tesseract languages, e.g. deu+eng or jpn+eng (default: auto-probe scripts)")
    p.add_argument("--regions", help="ISO codes to interpret local phone numbers, e.g. FR,BE")
    p.add_argument("--budget", type=float, default=150, help="OCR time budget in seconds (default 150)")
    p.add_argument("--fast", action="store_true", help="fewer OCR passes")
    p.add_argument("--no-ocr", action="store_true")
    p.add_argument("--no-codes", action="store_true")
    p.add_argument("--grid-cols", type=int, default=3)
    p.add_argument("--grid-rows", type=int, default=3)

    p = add("crop", "save a zoomed (optionally enhanced) crop as evidence")
    p.add_argument("case")
    region(p)
    p.add_argument("--scale", type=float, help="fixed upscale factor (default: auto, legible size)")
    p.add_argument("--enhance", help="comma list: auto,sharpen,contrast,gray,clahe,denoise,binarize,invert,brighten")
    p.add_argument("--rotate", type=float, default=0, help="degrees clockwise (straighten tilted text)")
    p.add_argument("--flip", action="store_true", help="mirror (read reversed text, check mirrored reposts)")
    p.add_argument("--pad", type=float, default=0.0, help="extra margin as a fraction of the box")
    p.add_argument("--label", help="short file label, e.g. socket, menu, fire-plan")
    p.add_argument("--what", help="one line: what this crop shows")

    p = add("tiles", "regenerate overlapping sweep tiles in .work/")
    p.add_argument("case")
    p.add_argument("--grid", default="4x4")
    p.add_argument("--overlap", type=float, default=0.2)

    p = add("countries", "intersect fixed standards across countries (offline tables)")
    p.add_argument("--plug", action="append", help="socket type seen (A..O); repeat for several seen together")
    p.add_argument("--plug-any", help="any of these types, e.g. C,F,E (ambiguous sockets)")
    p.add_argument("--calling", help="country calling code, e.g. 44")
    p.add_argument("--tld", help="country-code TLD, e.g. de or .de")
    p.add_argument("--currency", action="append", help="symbol or code (repeatable): €, £, R$, CHF ...")
    p.add_argument("--drive", choices=["left", "right"])
    p.add_argument("--lang", action="append", help="language code or name (repeatable)")
    p.add_argument("--script", action="append", help="writing system: Latn, Cyrl, Arab, Hebr, Hans, Hant, Jpan, "
                                                    "Kore, Thai, Deva, Grek, HANGUL, KATAKANA ...")
    p.add_argument("--week", choices=["mon", "sun", "sat", "fri"], help="first day of week on calendars")
    p.add_argument("--clock", choices=["12h", "24h"])
    p.add_argument("--temp", choices=["celsius", "fahrenheit"])
    p.add_argument("--paper", choices=["A4", "US-Letter"])
    p.add_argument("--emergency", action="append", help="emergency number seen on a sign (repeatable)")
    p.add_argument("--freq", choices=["50", "60"], help="mains frequency")
    p.add_argument("--voltage", choices=["100-130", "200-250"])
    p.add_argument("--min-pct", type=float, default=30.0,
                   help="a non-official language counts if spoken by >= this %% (default 30)")
    p.add_argument("--all", action="store_true", help="also list minor non-ISO territories (Ascension, Clipperton, Sark, "
                                                    "Diego Garcia, Ceuta & Melilla, Canary Islands, Tristan da Cunha)")
    p.add_argument("--limit", type=int, default=80)
    p.add_argument("--case", help="with --clue: add matches as country candidates and link the clue")
    p.add_argument("--clue", help="clue id that this filter expresses")
    p.add_argument("--lr", type=float, help="likelihood ratio for the matches (default: the clue's cap)")

    p = add("lookup", "offline lookups")
    p.add_argument("kind", choices=["phone", "barcode", "country", "plug", "plugs", "currency", "tld", "text"])
    p.add_argument("value", nargs="*", default=[])
    p.add_argument("--region", help="assumed country for local phone numbers")

    p = add("geo", "online geodata (keyless public services)")
    gsub = p.add_subparsers(dest="geo_cmd", required=True)
    g = gsub.add_parser("search", help="geocode a name/address (Nominatim, Photon fallback)")
    g.add_argument("query")
    g.add_argument("--country", help="ISO code filter")
    g.add_argument("--near", help="lat,lon bias")
    g.add_argument("--limit", type=int, default=8)
    g.add_argument("--case")
    g.add_argument("--add", help="add results as candidates at this level")
    g.add_argument("--parent", help="parent candidate for added results")
    g.add_argument("--save", action="store_true", help="save results JSON as evidence")
    g = gsub.add_parser("reverse", help="coordinates -> address")
    g.add_argument("--at", required=True)
    g.add_argument("--case")
    g = gsub.add_parser("poi", help="OSM features by tag/name/brand in an area (Overpass)")
    g.add_argument("--tag", action="append", help="key=value (repeatable), e.g. tourism=hotel, shop=supermarket")
    g.add_argument("--name", help="name regex (case-insensitive)")
    g.add_argument("--brand", help="brand regex")
    g.add_argument("--area", help="place name resolved to a bounding box")
    g.add_argument("--country", help="ISO code to disambiguate --area")
    g.add_argument("--bbox", help="s,w,n,e")
    g.add_argument("--around", help="lat,lon,radius_m")
    g.add_argument("--near-tag", action="append", help="co-location: only features within DIST m of TAG, "
                                                       "e.g. amenity=cafe@100 (repeat to chain)")
    g.add_argument("--limit", type=int, default=100)
    g.add_argument("--case")
    g.add_argument("--add")
    g.add_argument("--parent")
    g.add_argument("--save", action="store_true")
    g = gsub.add_parser("photos", help="Wikimedia Commons photos near a point / in a category / by text")
    g.add_argument("--at")
    g.add_argument("--radius", type=int, default=400)
    g.add_argument("--category")
    g.add_argument("--text")
    g.add_argument("--limit", type=int, default=30)
    g.add_argument("--sheet", type=int, default=0, help="with --case: contact sheet of the first N thumbnails")
    g.add_argument("--case")
    g = gsub.add_parser("wikidata", help="Wikidata search or entity (Q-id) facts")
    g.add_argument("query")
    g.add_argument("--lang", default="en")
    g.add_argument("--limit", type=int, default=8)
    g.add_argument("--details", action="store_true", help="also fetch facts of the first hit")
    g.add_argument("--case")
    g = gsub.add_parser("sparql", help="Wikidata SPARQL query (enumerate venues, artworks, stations ...)")
    g.add_argument("query", help="SPARQL text, or @file.rq")
    g.add_argument("--limit", type=int, default=50, help="rows to print (default 50)")
    g.add_argument("--case")
    g.add_argument("--add", help="add rows with ?item ?itemLabel ?coord as candidates at this level")
    g.add_argument("--parent")
    g.add_argument("--save", action="store_true")
    g = gsub.add_parser("timezone", help="time zone at a point (+ consistency with the EXIF offset)")
    g.add_argument("--at", required=True)
    g.add_argument("--time", help="local ISO time (default: EXIF capture time of --case)")
    g.add_argument("--case")
    g = gsub.add_parser("wigle", help="Wi-Fi network locations by SSID (WiGLE; needs the user's free API key)")
    g.add_argument("--ssid", required=True)
    g.add_argument("--like", action="store_true", help="treat --ssid as a pattern (%% and _ wildcards)")
    g.add_argument("--near", help="lat,lon: restrict to a box around this point")
    g.add_argument("--box", type=float, default=0.5, help="half-size of the box in degrees (default 0.5)")
    g.add_argument("--limit", type=int, default=30)
    g.add_argument("--case")
    g.add_argument("--add")
    g.add_argument("--parent")
    g = gsub.add_parser("weather", help="historical weather at a point on a date (Open-Meteo, consistency check)")
    g.add_argument("--at", required=True, help="lat,lon")
    g.add_argument("--date", help="YYYY-MM-DD (default: EXIF capture date of --case)")
    g.add_argument("--time", help="local ISO time: also report the weather at that hour")
    g.add_argument("--case")

    p = add("sun", "solar azimuth/elevation (offline NOAA algorithm)")
    p.add_argument("--at", required=True, help="lat,lon")
    p.add_argument("--time", required=True, help="ISO time with offset, e.g. 2024-05-01T15:30+02:00")

    p = add("bearing", "distance and initial bearing between two points (window views, qibla)")
    p.add_argument("--from", dest="frm", required=True, help="lat,lon, e.g. the candidate building")
    p.add_argument("--to", required=True, help="lat,lon of a landmark seen through the window, or 'qibla'")
    p.add_argument("--facing", type=float, help="azimuth the window faces (deg): is the target inside the view?")

    p = add("revsearch", "reverse image search (headless where possible)")
    p.add_argument("case")
    region(p)
    p.add_argument("--image", action="append", help="evidence id or file to search (repeatable)")
    p.add_argument("--full", action="store_true", help="also search the full frame when --image/--cell is given")
    p.add_argument("--flip", action="store_true", help="also search a mirrored copy")
    p.add_argument("--engines", default="yandex,tineye", help="comma list of yandex,tineye,bing,lens or 'all'")
    p.add_argument("--top", type=int, default=8)

    p = add("social", "social media and community photos, searched for the place (never for people)")
    ssub = p.add_subparsers(dest="social_cmd", required=True)
    s = ssub.add_parser("search", help="keyless open APIs: Bluesky, Flickr tags, Openverse, Mastodon tags, Lemmy")
    s.add_argument("query", help="venue name, distinctive text or a short description, in the local language too")
    s.add_argument("--sources", default="bluesky,flickr,openverse,mastodon,lemmy", help="comma list, or 'all'")
    s.add_argument("--tag", help="hashtag for Mastodon / comma tags for Flickr (default: derived from the query)")
    s.add_argument("--lang", help="Bluesky language filter, e.g. ja")
    s.add_argument("--instance", default="mastodon.social", help="Mastodon instance for the hashtag timeline")
    s.add_argument("--limit", type=int, default=15, help="items per source (default 15)")
    s.add_argument("--images-only", action="store_true", help="only items that carry images")
    s.add_argument("--sheet", type=int, default=0, help="with --case: contact sheet of the first N images")
    s.add_argument("--case")
    s.add_argument("--save", action="store_true", help="with --case: keep the result list as evidence")
    s = ssub.add_parser("links", help="ready-to-open search URLs: Instagram, TikTok, X, Reddit, Xiaohongshu, ...")
    s.add_argument("query")
    s.add_argument("--tag", help="hashtag (default: derived from the query)")
    s.add_argument("--at", help="lat,lon: add map-based photo search around a candidate")
    s.add_argument("--only", help="comma list of platforms, e.g. instagram,tiktok,xiaohongshu")

    p = add("snapshot", "save a web page as evidence (screenshot + text)")
    p.add_argument("case")
    p.add_argument("url")
    p.add_argument("--label")

    p = add("compare", "side-by-side sheet of the photo (or a crop) and reference images")
    p.add_argument("case")
    region(p)
    p.add_argument("--query", help="evidence id of a crop to use as the query")
    p.add_argument("--ref", action="append", required=True, help="reference image URL, file or evidence id (repeatable)")
    p.add_argument("--label")

    p = add("note", "record a clue")
    p.add_argument("case")
    p.add_argument("text")
    p.add_argument("--kind", required=True, help="hypothesis, scene, metadata, text, code, standard, architecture, "
                                                 "style, product, culture, personal-item, language, window-view, "
                                                 "light-time, provenance, match, negative, contradiction, context, other")
    p.add_argument("--status", required=True, help="inferred | observed | reported | metadata | read | computed | matched")
    p.add_argument("--source", required=True, help="image | text | metadata | table | web | engine | map | reference | "
                                                   "geometry | user")
    p.add_argument("--file", action="append", help="evidence id(s) or file path(s)")
    p.add_argument("--box", help="where in the photo: x0,y0,x1,y1")
    p.add_argument("--url")
    p.add_argument("--resolves", action="append", help="clue id(s) this result settles (e.g. a contradiction)")

    p = add("cand", "add a candidate (or update one: pass its id instead of a name)")
    p.add_argument("case")
    p.add_argument("name")
    p.add_argument("--level", help="country | region | city | district | site | room")
    p.add_argument("--parent")
    p.add_argument("--at", help="lat,lon")
    p.add_argument("--lat", type=float)
    p.add_argument("--lon", type=float)
    p.add_argument("--address")
    p.add_argument("--osm")
    p.add_argument("--url")
    p.add_argument("--wikidata")
    p.add_argument("--falsify", help="the observation that would rule this candidate out (write it BEFORE comparing)")
    p.add_argument("--note")
    p.add_argument("--file", action="append")

    p = add("link", "link a clue to candidates with likelihood ratios")
    p.add_argument("case")
    p.add_argument("clue")
    p.add_argument("--for", dest="for_", action="append", help="C#:LR (LR >= 1), repeatable")
    p.add_argument("--against", action="append", help="C#:LR (LR < 1, or give 3 for 1/3), repeatable")
    p.add_argument("--why", required=True)
    p.add_argument("--file", action="append")

    p = add("exclude", "exclude a candidate with decisive evidence")
    p.add_argument("case")
    p.add_argument("candidate")
    p.add_argument("--by", required=True, help="clue id (status read / computed / matched)")
    p.add_argument("--why", required=True)
    p.add_argument("--file", action="append")

    p = add("log", "record a method attempt (coverage ledger)")
    p.add_argument("case")
    p.add_argument("method", help="metadata visual_sweep text_ocr codes standards culture_style reverse_search "
                                  "text_search social_search candidate_enum reference_match window_view consistency | "
                                  "provenance_hunt listing_search map_photos sun_light wifi_ssid ai_estimate other")
    p.add_argument("--status", required=True, help="results | no_results | blocked | unavailable | not_applicable | skipped")
    p.add_argument("--detail")
    p.add_argument("--engine")
    p.add_argument("--query")
    p.add_argument("--url")
    p.add_argument("--file", action="append")

    p = add("rank", "rank candidates per level")
    p.add_argument("case")
    p.add_argument("--level")
    p.add_argument("--limit", type=int, default=25)

    p = add("check", "pre-report audit (exit 1 on FAIL)")
    p.add_argument("case")

    p = add("answer", "record the final answer")
    p.add_argument("case")
    p.add_argument("candidate")
    p.add_argument("--confidence", choices=["low", "medium", "high"], help="default: the rules cap")
    p.add_argument("--at", help="override coordinates lat,lon")
    p.add_argument("--address")
    p.add_argument("--name", help="display name override")
    p.add_argument("--radius", type=int, help="error radius in metres")
    p.add_argument("--summary", help="2-6 sentences: the decisive reasoning chain")
    p.add_argument("--open-questions")
    p.add_argument("--file", action="append")
    p.add_argument("--no-network", action="store_true", help="do not reverse-geocode a missing address")

    p = add("report", "write REPORT.md and result.json")
    p.add_argument("case")

    p = add("finalize", "check, write the report, delete scratch and unreferenced files")
    p.add_argument("case")
    p.add_argument("--force", action="store_true", help="finalize despite FAIL items (they are listed in the report)")
    p.add_argument("--keep-work", action="store_true")
    p.add_argument("--keep-all", action="store_true", help="keep unreferenced evidence files")

    p = add("status", "overview of a case")
    p.add_argument("case")

    p = add("doctor", "check the environment and service reachability")
    p.add_argument("--offline", action="store_true", help="skip network probes")
    return ap


_NEG_LIST = re.compile(r"^-\d+(?:\.\d+)?(?:\s*,\s*-?\d+(?:\.\d+)?)+$")


def join_negative_values(argv: list[str]) -> list[str]:
    """argparse reads '--at -33.86,151.21' as two options; rewrite it as '--at=-33.86,151.21' so that
    southern / western coordinates and boxes work without the '=' trick."""
    out: list[str] = []
    for tok in argv:
        if out and _NEG_LIST.match(tok) and out[-1].startswith("--") and "=" not in out[-1]:
            out[-1] = f"{out[-1]}={tok}"
        else:
            out.append(tok)
    return out


def main(argv=None) -> int:
    utf8_console()
    args = build_parser().parse_args(join_negative_values(list(sys.argv[1:] if argv is None else argv)))
    from iglib import commands, doctor
    if args.cmd == "doctor":
        return doctor.run(network=not args.offline)
    fn = getattr(commands, f"cmd_{args.cmd}")
    try:
        return fn(args) or 0
    except IglError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:      # output piped into `head` etc.
        return 0


if __name__ == "__main__":
    sys.exit(main())
