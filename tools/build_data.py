#!/usr/bin/env python3
"""Maintainer tool: rebuild the skill's offline lookup tables in indoor-geolocator/data/.

Not part of the installed skill. Run it only when you want to refresh the data:

    python tools/build_data.py                 # download sources into .data-src/ (cached), build, write data/
    python tools/build_data.py --offline       # rebuild from the cached sources only

Sources (all public; licences recorded in data/README.md and in each file's _meta):
  * Unicode CLDR JSON (cldr-core, cldr-localenames-full, cldr-numbers-full) - Unicode License v3
      territory names, languages per territory, currencies (current and historical), calling codes,
      first day of the week, 12/24-hour preference, measurement system, paper size, likely scripts
  * Wikipedia (CC BY-SA 4.0), via the REST HTML endpoint:
      Mains_electricity_by_country      plug types, voltage, frequency
      Left-_and_right-hand_traffic      driving side
      List_of_emergency_telephone_numbers
      List_of_GS1_country_codes         barcode prefix ranges

Wikimedia rate-limits shared IP ranges aggressively: the downloader waits and retries, and the
build still succeeds without a source (that field is simply absent and _meta says so).
Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".data-src"
OUT = ROOT / "indoor-geolocator" / "data"
UA = "indoor-geolocator-data-builder/1.0 (maintainer tool of an open-source OSINT skill; low volume)"

CLDR = {
    "territories_en": "https://cdn.jsdelivr.net/npm/cldr-localenames-full/main/en/territories.json",
    "languages_en": "https://cdn.jsdelivr.net/npm/cldr-localenames-full/main/en/languages.json",
    "scripts_en": "https://cdn.jsdelivr.net/npm/cldr-localenames-full/main/en/scripts.json",
    "currencies_en": "https://cdn.jsdelivr.net/npm/cldr-numbers-full/main/en/currencies.json",
    "territoryInfo": "https://cdn.jsdelivr.net/npm/cldr-core/supplemental/territoryInfo.json",
    "currencyData": "https://cdn.jsdelivr.net/npm/cldr-core/supplemental/currencyData.json",
    "telephoneCodeData": "https://cdn.jsdelivr.net/npm/cldr-core/supplemental/telephoneCodeData.json",
    "weekData": "https://cdn.jsdelivr.net/npm/cldr-core/supplemental/weekData.json",
    "timeData": "https://cdn.jsdelivr.net/npm/cldr-core/supplemental/timeData.json",
    "measurementData": "https://cdn.jsdelivr.net/npm/cldr-core/supplemental/measurementData.json",
    "likelySubtags": "https://cdn.jsdelivr.net/npm/cldr-core/supplemental/likelySubtags.json",
    "territoryContainment": "https://cdn.jsdelivr.net/npm/cldr-core/supplemental/territoryContainment.json",
    "package": "https://cdn.jsdelivr.net/npm/cldr-core/package.json",
}
WIKI = {
    "mains": "Mains_electricity_by_country",
    "traffic": "Left-_and_right-hand_traffic",
    "emergency": "List_of_emergency_telephone_numbers",
    "gs1": "List_of_GS1_country_codes",
}
WIKI_URL = "https://en.wikipedia.org/api/rest_v1/page/html/{}"

# Wikipedia spellings that CLDR names do not cover (normalised form -> ISO 3166-1 alpha-2)
ALIASES = {
    "bahamas": "BS", "the bahamas": "BS", "gambia": "GM", "the gambia": "GM",
    "ivory coast": "CI", "cote divoire": "CI", "congo": "CG", "republic of the congo": "CG",
    "congo republic": "CG", "congo brazzaville": "CG", "democratic republic of the congo": "CD",
    "dr congo": "CD", "congo kinshasa": "CD", "drc": "CD", "east timor": "TL", "timor leste": "TL",
    "vatican city": "VA", "holy see": "VA", "vatican": "VA", "micronesia": "FM",
    "federated states of micronesia": "FM", "south korea": "KR", "korea south": "KR",
    "republic of korea": "KR", "north korea": "KP", "korea north": "KP",
    "democratic peoples republic of korea": "KP", "burma": "MM", "myanmar burma": "MM",
    "czech republic": "CZ", "czechia": "CZ", "swaziland": "SZ", "eswatini": "SZ",
    "macedonia": "MK", "north macedonia": "MK", "republic of macedonia": "MK",
    "cape verde": "CV", "cabo verde": "CV", "palestine": "PS", "state of palestine": "PS",
    "palestinian territories": "PS", "west bank": "PS", "gaza strip": "PS",
    "united states": "US", "united states of america": "US", "usa": "US",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "britain": "GB",
    "russia": "RU", "russian federation": "RU", "laos": "LA", "lao pdr": "LA", "syria": "SY",
    "iran": "IR", "vietnam": "VN", "viet nam": "VN", "brunei": "BN", "brunei darussalam": "BN",
    "moldova": "MD", "tanzania": "TZ", "bolivia": "BO", "venezuela": "VE", "taiwan": "TW",
    "republic of china": "TW", "hong kong": "HK", "macau": "MO", "macao": "MO",
    "saint helena": "SH", "st helena": "SH", "saint helena ascension and tristan da cunha": "SH",
    "saint kitts and nevis": "KN", "st kitts and nevis": "KN", "saint lucia": "LC", "st lucia": "LC",
    "saint vincent and the grenadines": "VC", "st vincent and the grenadines": "VC",
    "saint pierre and miquelon": "PM", "saint barthelemy": "BL", "saint martin": "MF",
    "sint maarten": "SX", "curacao": "CW", "us virgin islands": "VI",
    "united states virgin islands": "VI", "british virgin islands": "VG",
    "virgin islands british": "VG", "virgin islands us": "VI", "falkland islands": "FK",
    "kosovo": "XK", "sao tome and principe": "ST", "guinea bissau": "GW", "pitcairn islands": "PN",
    "wallis and futuna": "WF", "reunion": "RE", "aland islands": "AX", "aland": "AX",
    "faroe islands": "FO", "faroes": "FO", "caribbean netherlands": "BQ",
    "bonaire": "BQ", "bonaire sint eustatius and saba": "BQ", "turks and caicos islands": "TC",
    "cocos keeling islands": "CC", "cocos islands": "CC", "heard island and mcdonald islands": "HM",
    "svalbard": "SJ", "svalbard and jan mayen": "SJ", "mainland china": "CN",
    "china": "CN", "peoples republic of china": "CN", "western sahara": "EH",
    "sahrawi arab democratic republic": "EH", "ireland": "IE", "republic of ireland": "IE",
    "northern mariana islands": "MP", "american samoa": "AS", "guam": "GU", "puerto rico": "PR",
    "netherlands": "NL", "the netherlands": "NL", "kingdom of the netherlands": "NL",
    "south sudan": "SS", "sudan": "SD", "turkey": "TR", "turkiye": "TR",
    "british indian ocean territory": "IO", "french guiana": "GF", "french polynesia": "PF",
    "new caledonia": "NC", "norfolk island": "NF", "christmas island": "CX", "isle of man": "IM",
    "jersey": "JE", "guernsey": "GG", "gibraltar": "GI", "bermuda": "BM", "montserrat": "MS",
    "anguilla": "AI", "cayman islands": "KY", "greenland": "GL", "aruba": "AW",
    "south georgia and the south sandwich islands": "GS", "tokelau": "TK", "niue": "NU",
    "cook islands": "CK", "marshall islands": "MH", "solomon islands": "SB", "fiji": "FJ",
    "antigua and barbuda": "AG", "trinidad and tobago": "TT", "bosnia and herzegovina": "BA",
    "united arab emirates": "AE", "uae": "AE", "central african republic": "CF",
    "dominican republic": "DO", "equatorial guinea": "GQ", "papua new guinea": "PG",
    "saudi arabia": "SA", "sri lanka": "LK", "el salvador": "SV", "new zealand": "NZ",
    "south africa": "ZA", "costa rica": "CR", "san marino": "SM", "sierra leone": "SL",
    "burkina faso": "BF", "mauritania": "MR", "kyrgyzstan": "KG", "tajikistan": "TJ",
    "liechtenstein": "LI", "luxembourg": "LU", "montenegro": "ME", "serbia": "RS",
    "slovakia": "SK", "slovenia": "SI", "zimbabwe": "ZW", "zambia": "ZM", "mayotte": "YT",
    "martinique": "MQ", "guadeloupe": "GP", "akrotiri and dhekelia": "CY",
    "congo democratic republic of the": "CD", "democratic republic of congo": "CD",
    "congo republic of the": "CG", "turks and caicos": "TC",
    "korea republic of": "KR", "korea democratic peoples republic of": "KP", "micronesia federated states of": "FM",
    "bahamas the": "BS", "gambia the": "GM", "united kingdom and overseas territories": "GB",
}
# Non-ISO / disputed places that appear in the Wikipedia tables: kept under their own keys
SPECIAL = {
    "abkhazia": ("X-ABKHAZIA", "Abkhazia"), "south ossetia": ("X-SOUTH-OSSETIA", "South Ossetia"),
    "transnistria": ("X-TRANSNISTRIA", "Transnistria"), "somaliland": ("X-SOMALILAND", "Somaliland"),
    "northern cyprus": ("X-NORTHERN-CYPRUS", "Northern Cyprus"),
    "artsakh": ("X-ARTSAKH", "Artsakh"), "england": ("GB", "United Kingdom"),
    "scotland": ("GB", "United Kingdom"), "wales": ("GB", "United Kingdom"),
    "northern ireland": ("GB", "United Kingdom"),
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("&", " and ").replace("’", "'")
    s = re.sub(r"\[.*?\]|\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s.replace("'", ""))
    s = re.sub(r"^the ", "", re.sub(r"\s+", " ", s).strip())
    return s


def countries_json(meta: dict, countries: dict) -> str:
    """countries.json with one country per line: readable, diff-friendly and under the 256 KiB that plugin
    directories allow for a single file."""
    rows = ",\n".join(f' {json.dumps(k)}: {json.dumps(v, ensure_ascii=False, separators=(", ", ": "))}'
                      for k, v in countries.items())
    return ('{\n"_meta": ' + json.dumps(meta, ensure_ascii=False, indent=1) + ',\n"countries": {\n' + rows + "\n}\n}\n")


def fetch(name: str, url: str, offline: bool, retries: int = 6, min_bytes: int = 2000) -> Path | None:
    SRC.mkdir(exist_ok=True)
    path = SRC / name
    if path.exists() and path.stat().st_size >= min_bytes:
        return path
    if offline:
        return None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if len(data) >= min_bytes:
                path.write_bytes(data)
                return path
            print(f"  {name}: short reply ({len(data)} bytes), retry {attempt}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - report and retry
            print(f"  {name}: {e}, retry {attempt}", file=sys.stderr)
        time.sleep(min(90, 15 * attempt))
    return None


def cell_text(c: str) -> str:
    c = re.sub(r"<sup.*?</sup>", "", c, flags=re.S)
    c = re.sub(r"<br[^>]*>", " ; ", c)
    c = re.sub(r"</(p|div|li)>", " ; ", c)
    c = re.sub(r"<style.*?</style>", "", c, flags=re.S)
    c = re.sub(r"<[^>]+>", "", c)
    return re.sub(r"\s+", " ", html.unescape(c)).strip()


def wiki_tables(path: Path) -> list[list[list[str]]]:
    src = path.read_text(encoding="utf-8")
    out = []
    for t in re.findall(r"<table[^>]*class=\"[^\"]*wikitable[^\"]*\"[^>]*>(.*?)</table>", src, re.S):
        rows = []
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
            cells = []
            for attrs, c in re.findall(r"<t[hd]([^>]*)>(.*?)</t[hd]>", r, re.S):
                m = re.search(r'colspan="?(\d+)', attrs)
                txt = re.sub(r"(\s*;\s*)+", " ; ", cell_text(c)).strip(" ;")
                cells.extend([txt] * (int(m.group(1)) if m else 1))
            rows.append(cells)
        out.append(rows)
    return out


class Names:
    def __init__(self, territories: dict):
        self.by_norm: dict[str, str] = {}
        self.en: dict[str, str] = {}
        for code, name in territories.items():
            base = code.split("-alt-")[0]
            if not re.fullmatch(r"[A-Z]{2}", base):
                continue
            if "-alt-" not in code:
                self.en[base] = name
            self.by_norm.setdefault(norm(name), base)
        for k, v in ALIASES.items():
            self.by_norm[norm(k)] = v

    def iso(self, name: str) -> str | None:
        n = norm(name)
        if n in SPECIAL:
            return SPECIAL[n][0]
        if n in self.by_norm:
            return self.by_norm[n]
        n2 = re.sub(r"\b(republic of|kingdom of|state of|islamic republic of)\b", "", n).strip()
        return self.by_norm.get(n2)


def parse_mains(path: Path, names: Names, unmatched: list) -> dict:
    out = {}
    for table in wiki_tables(path):
        if not table or "Plug type" not in " ".join(table[0]):
            continue
        for row in table[1:]:
            if len(row) < 5:
                continue
            country, plugs, std, volts, freq = row[:5]
            notes = row[5] if len(row) > 5 else ""
            iso = names.iso(country)
            if not iso:
                unmatched.append(("mains", country))
                continue
            types = sorted(set(re.findall(r"\b([A-O])\b", plugs.replace("&", ","))))
            rec = {"plug_types": types, "plug_types_raw": plugs, "voltage": volts.replace(" ", " "),
                   "frequency": freq.replace(" ", " ")}
            if std:
                rec["plug_standard"] = std
            if notes:
                rec["mains_notes"] = notes[:300]
            if iso in out:      # several rows for one ISO (e.g. GB parts): merge
                prev = out[iso]
                prev["plug_types"] = sorted(set(prev["plug_types"]) | set(types))
                continue
            out[iso] = rec
    return out


def parse_traffic(path: Path, names: Names, unmatched: list) -> dict:
    out = {}
    for table in wiki_tables(path):
        if not table:
            continue
        hdr = [h.lower() for h in table[0]]
        col = next((i for i, h in enumerate(hdr) if "traffic" in h or "driving" in h or "side" in h), None)
        if col is None or not re.search(r"country|territory", hdr[0]):
            continue
        for row in table[1:]:
            if len(row) < 2:
                continue
            iso = names.iso(row[0])
            if not iso:
                unmatched.append(("traffic", row[0]))
                continue
            v = " ".join(row[1:col + 1]).upper()     # rowspans shift sub-rows (e.g. Hong Kong under China) left
            side = "right" if re.search(r"\bRHT\b|RIGHT", v) and not re.search(r"\bLHT\b|LEFT", v) else (
                "left" if re.search(r"\bLHT\b|LEFT", v) and not re.search(r"\bRHT\b|RIGHT", v) else None)
            if side and iso not in out:
                out[iso] = side
    return out


def parse_emergency(path: Path, names: Names, unmatched: list) -> dict:
    out: dict[str, dict] = {}
    for table in wiki_tables(path):
        if not table:
            continue
        hdr = [h.lower() for h in table[0]]
        if not hdr or not re.search(r"country|territory", hdr[0]):
            continue
        for row in table[1:]:
            if len(row) < 2:
                continue
            iso = names.iso(row[0])
            if not iso:
                unmatched.append(("emergency", row[0]))
                continue
            rec = out.setdefault(iso, {})
            for h, c in zip(hdr[1:], row[1:]):
                key = ("police" if "police" in h else "ambulance" if ("ambulance" in h or "medical" in h) else
                       "fire" if "fire" in h else None)
                if key is None:          # "Notes" / "Other numbers": free text, too noisy to tabulate
                    continue
                nums = [n.replace(" ", "").replace("\u00a0", "")
                        for n in re.findall(r"(?<![\d-])(\d{2,3}[ \u00a0]\d{3}|\d{2,5})(?![\d-])", c)]
                if not nums:
                    continue
                rec.setdefault(key, [])
                for n in nums:
                    if n not in rec[key]:
                        rec[key].append(n)
    return out


def parse_gs1(path: Path) -> list[dict]:
    rows = []
    for table in wiki_tables(path):
        if not table:
            continue
        head = " ".join(table[0]).lower()
        if "prefix" not in head and "code" not in head:
            continue
        for row in table[1:]:
            if len(row) < 2:
                continue
            m = re.match(r"^\s*(\d{3})(?:\s*[–-]\s*(\d{3}))?\s*$", row[0])
            if not m:
                continue
            lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
            rows.append({"from": lo, "to": hi, "org": row[1]})
    rows.sort(key=lambda r: r["from"])
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="use cached sources in .data-src/ only")
    a = ap.parse_args()
    today = dt.date.today().isoformat()

    cl = {}
    for key, url in CLDR.items():
        p = fetch(f"cldr_{key}.json", url, a.offline, min_bytes=300)
        if not p:
            print(f"ERROR: CLDR source {key} unavailable; it is required.", file=sys.stderr)
            return 1
        cl[key] = json.loads(p.read_text(encoding="utf-8"))
    cldr_version = cl["package"].get("version", "?")
    names = Names(cl["territories_en"]["main"]["en"]["localeDisplayNames"]["territories"])
    lang_names = cl["languages_en"]["main"]["en"]["localeDisplayNames"]["languages"]
    script_names = cl["scripts_en"]["main"]["en"]["localeDisplayNames"]["scripts"]
    cur_names = cl["currencies_en"]["main"]["en"]["numbers"]["currencies"]
    tinfo = cl["territoryInfo"]["supplemental"]["territoryInfo"]
    curdata = cl["currencyData"]["supplemental"]["currencyData"]["region"]
    tel = cl["telephoneCodeData"]["supplemental"]["telephoneCodeData"]
    week = cl["weekData"]["supplemental"]["weekData"]
    tdata = cl["timeData"]["supplemental"]["timeData"]
    meas = cl["measurementData"]["supplemental"]["measurementData"]
    likely = cl["likelySubtags"]["supplemental"]["likelySubtags"]
    contain = cl["territoryContainment"]["supplemental"]["territoryContainment"]

    region_of: dict[str, str] = {}
    for parent, v in contain.items():
        if parent.isdigit() and len(parent) == 3 and "_contains" in v:
            for child in v["_contains"]:
                if re.fullmatch(r"[A-Z]{2}", child) and parent not in ("001", "002", "009", "019", "142", "150"):
                    region_of.setdefault(child, parent)

    wiki, unmatched, sources_ok = {}, [], {}
    for key, page in WIKI.items():
        p = fetch(f"wiki_{key}.html", WIKI_URL.format(page), a.offline, retries=6, min_bytes=20000)
        sources_ok[key] = bool(p)
        wiki[key] = p
    mains = parse_mains(wiki["mains"], names, unmatched) if wiki["mains"] else {}
    traffic = parse_traffic(wiki["traffic"], names, unmatched) if wiki["traffic"] else {}
    emerg = parse_emergency(wiki["emergency"], names, unmatched) if wiki["emergency"] else {}
    gs1 = parse_gs1(wiki["gs1"]) if wiki["gs1"] else []

    countries = {}
    for iso, name in sorted(names.en.items()):
        if iso in ("EU", "EZ", "UN", "QO", "ZZ", "XA", "XB"):
            continue
        rec: dict = {"name": name}
        alt = [v for k, v in cl["territories_en"]["main"]["en"]["localeDisplayNames"]["territories"].items()
               if k.startswith(iso + "-alt-")]
        if alt:
            rec["alt_names"] = alt
        if iso in region_of:
            rec["un_region"] = names.en.get(region_of[iso]) or region_of[iso]
        if iso in tel:
            rec["calling_codes"] = sorted({d["telephoneCountryCode"] for d in tel[iso]})
        cur_now, cur_old = [], []
        for item in curdata.get(iso, []):
            for code, info in item.items():
                if info.get("_tender") == "false":
                    continue
                c = cur_names.get(code, {})
                entry = {"code": code, "name": c.get("displayName", code), "symbol": c.get("symbol", code)}
                if c.get("symbol-alt-narrow") and c.get("symbol-alt-narrow") != entry["symbol"]:
                    entry["narrow_symbol"] = c["symbol-alt-narrow"]
                if "_to" in info:
                    entry["until"] = info["_to"]
                    if "_from" in info:
                        entry["from"] = info["_from"]
                    cur_old.append(entry)
                else:
                    cur_now.append(entry)
        if cur_now:
            rec["currencies"] = cur_now
        if cur_old:
            rec["former_currencies"] = cur_old
        langs = []
        for lang, info in tinfo.get(iso, {}).get("languagePopulation", {}).items():
            pct = float(info.get("_populationPercent", 0) or 0)
            off = info.get("_officialStatus", "")
            if pct >= 5 or off:
                base = lang.split("_")[0]
                ls = likely.get(base) or likely.get(lang) or ""
                script = lang.split("_")[1] if "_" in lang and len(lang.split("_")[1]) == 4 else (
                    ls.split("-")[1] if ls.count("-") >= 2 else "")
                langs.append({"code": lang, "name": lang_names.get(lang) or lang_names.get(base, lang),
                              "script": script, "script_name": script_names.get(script, script),
                              "pct": pct, "official": off or None})
        if langs:
            rec["languages"] = sorted(langs, key=lambda x: -x["pct"])
        if iso in week.get("firstDay", {}):
            rec["week_starts"] = week["firstDay"][iso]
        else:
            rec["week_starts"] = week["firstDay"].get("001", "mon")
        hc = tdata.get(iso, tdata.get("001", {})).get("_preferred")
        if hc:
            rec["clock"] = "12h" if hc in ("h", "K") else "24h"
        ms = meas.get("measurementSystem", {})
        rec["measurement"] = {"US": "US customary", "UK": "metric + imperial (UK)"}.get(ms.get(iso, ""), "metric")
        temp = meas.get("measurementSystem-category-temperature", {}).get(iso, ms.get(iso, "metric"))
        rec["temperature"] = "fahrenheit" if temp == "US" else "celsius"
        rec["paper"] = meas.get("paperSize", {}).get(iso, "A4")
        rec["cctld"] = "." + ("uk" if iso == "GB" else iso.lower())
        if iso in mains:
            rec.update(mains[iso])
        if iso in traffic:
            rec["driving_side"] = traffic[iso]
        if iso in emerg:
            rec["emergency"] = emerg[iso]
        countries[iso] = rec
    for _key, (code, label) in SPECIAL.items():
        if code.startswith("X-") and (code in mains or code in traffic):
            rec = {"name": label, "non_iso": True}
            rec.update(mains.get(code, {}))
            if code in traffic:
                rec["driving_side"] = traffic[code]
            countries[code] = rec

    meta = {
        "description": "Per-country standards for indoor geolocation (plugs, mains, currencies, languages, calling codes, "
                       "calendar/clock/units conventions, driving side, emergency numbers). Keys are ISO 3166-1 alpha-2.",
        "built": today,
        "sources": {
            "cldr": {"version": cldr_version, "license": "Unicode License v3",
                     "url": "https://github.com/unicode-org/cldr-json",
                     "fields": ["name", "alt_names", "un_region", "calling_codes", "currencies", "former_currencies",
                                "languages", "week_starts", "clock", "measurement", "temperature", "paper"]},
            "wikipedia": {"license": "CC BY-SA 4.0 (derived factual tables; attribution to Wikipedia contributors)",
                          "pages": {k: f"https://en.wikipedia.org/wiki/{v}" for k, v in WIKI.items()},
                          "available": sources_ok,
                          "fields": {"mains": ["plug_types", "plug_types_raw", "plug_standard", "voltage", "frequency",
                                               "mains_notes"], "traffic": ["driving_side"], "emergency": ["emergency"]}},
        },
        "count": len(countries),
        "unmatched_source_rows": sorted({f"{k}: {v}" for k, v in unmatched})[:200],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "countries.json").write_text(countries_json(meta, countries), encoding="utf-8")
    if gs1:
        gmeta = {"description": "GS1 company-prefix ranges (first 3 digits of EAN-13/GTIN-13) -> issuing GS1 member "
                                "organisation. It tells where the barcode was REGISTERED, not where the product "
                                "was made or sold.",
                 "built": today, "source": f"https://en.wikipedia.org/wiki/{WIKI['gs1']}",
                 "license": "CC BY-SA 4.0 (derived factual table)", "count": len(gs1)}
        (OUT / "gs1_prefixes.json").write_text(json.dumps({"_meta": gmeta, "ranges": gs1}, ensure_ascii=False,
                                                          indent=1) + "\n", encoding="utf-8")
    print(f"countries.json: {len(countries)} entries; mains rows {len(mains)}, traffic {len(traffic)}, "
          f"emergency {len(emerg)}; gs1 ranges {len(gs1)}")
    if unmatched:
        print(f"unmatched rows ({len(set(unmatched))}): " + "; ".join(sorted({v for _, v in unmatched}))[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
