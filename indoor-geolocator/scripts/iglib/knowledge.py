"""Offline knowledge: per-country standards (data/countries.json) and GS1 barcode prefixes
(data/gs1_prefixes.json), with multi-attribute filtering so independent fixed standards can be
intersected ("Type G socket" x "£ prices" x "drives on the left" -> a handful of countries)."""
from __future__ import annotations

import re
from functools import lru_cache

from .util import DATA_DIR, IglError, read_json

PLUG_SHAPES = {
    "A": "two flat parallel blades, no earth (US/Canada/Mexico/Japan; Japan's are often non-polarised)",
    "B": "two flat blades + round earth pin below (US/Canada/Mexico/Japan/Taiwan/Philippines...)",
    "C": "two round 4.0-4.8 mm pins, no earth: the Europlug; fits most C/E/F/J/K/L/N sockets",
    "D": "three large round pins in a triangle (India, Nepal, Sri Lanka, old British lighting circuits)",
    "E": "two round pins; the SOCKET has a protruding male earth pin (France, Belgium, Poland, Czechia, Slovakia...)",
    "F": "Schuko: two round pins, earthing clips on the sides; round recessed socket (Germany, most of Europe, "
         "Russia, Korea, Indonesia...)",
    "G": "three rectangular pins, fused plug, switched sockets common (UK, Ireland, Malta, Cyprus, Hong Kong, "
         "Singapore, Malaysia, Gulf states...)",
    "H": "three flat or round pins in a V/Y (Israel; the socket also takes Type C)",
    "I": "two flat pins in an inverted V + flat earth (Australia, New Zealand, China, Argentina, Fiji, PNG...)",
    "J": "Swiss: three round pins, earth offset; hexagonal recessed socket, often triple (Switzerland, Liechtenstein)",
    "K": "Danish: two round pins + half-round earth below (a 'surprised face'); Denmark, Greenland",
    "L": "Italian: three round pins in a straight line (Italy, Chile, Uruguay, parts of North Africa)",
    "M": "large three round pins (15 A), triangle like D but bigger (South Africa, Lesotho, Eswatini, India...)",
    "N": "Brazil NBR 14136 / South Africa SANS 164-2: three round pins, socket in a hexagon-shaped recess",
    "O": "Thai TIS 166-2549: three round pins (Thailand); many Thai sockets are multi-standard",
}
SCRIPT_ALIASES = {   # unicodedata name prefix / common names -> ISO 15924 codes used by CLDR data
    "LATIN": ["Latn"], "CYRILLIC": ["Cyrl"], "GREEK": ["Grek"], "ARABIC": ["Arab"], "HEBREW": ["Hebr"],
    "HIRAGANA": ["Jpan"], "KATAKANA": ["Jpan"], "HANGUL": ["Kore", "Hang"], "THAI": ["Thai"], "LAO": ["Laoo"],
    "KHMER": ["Khmr"], "MYANMAR": ["Mymr"], "DEVANAGARI": ["Deva"], "BENGALI": ["Beng"], "TAMIL": ["Taml"],
    "TELUGU": ["Telu"], "KANNADA": ["Knda"], "MALAYALAM": ["Mlym"], "GUJARATI": ["Gujr"], "GURMUKHI": ["Guru"],
    "SINHALA": ["Sinh"], "GEORGIAN": ["Geor"], "ARMENIAN": ["Armn"], "ETHIOPIC": ["Ethi"], "TIBETAN": ["Tibt"],
    "MONGOLIAN": ["Mong"], "CJK": ["Hans", "Hant", "Jpan", "Kore"], "HAN": ["Hans", "Hant", "Jpan", "Kore"],
    "SIMPLIFIED": ["Hans"], "TRADITIONAL": ["Hant"], "THAANA": ["Thaa"], "TIFINAGH": ["Tfng"],
}


# Codes in the data that are not ISO 3166-1 countries. Kosovo (XK) is a de facto country with its own
# conventions, so it belongs to the default universe; the others are minor or overlapping territories
# (Ascension, Clipperton, Sark, Diego Garcia, Ceuta & Melilla, Canary Islands, Tristan da Cunha).
NON_ISO = {"AC", "CP", "CQ", "DG", "EA", "IC", "TA", "XK"}
IN_DEFAULT_UNIVERSE = {"XK"}


def in_universe(iso: str, include_non_iso: bool = False) -> bool:
    return include_non_iso or iso not in NON_ISO or iso in IN_DEFAULT_UNIVERSE


@lru_cache(maxsize=1)
def universe_size() -> int:
    """Number of countries a country-level board implicitly covers (ISO 3166-1 + Kosovo)."""
    return sum(1 for iso in countries() if in_universe(iso))


@lru_cache(maxsize=1)
def countries() -> dict:
    p = DATA_DIR / "countries.json"
    if not p.exists():
        raise IglError(f"Missing {p}: the skill's data folder is incomplete")
    return read_json(p)["countries"]


@lru_cache(maxsize=1)
def countries_meta() -> dict:
    return read_json(DATA_DIR / "countries.json")["_meta"]


@lru_cache(maxsize=1)
def gs1_ranges() -> list[dict]:
    p = DATA_DIR / "gs1_prefixes.json"
    return read_json(p)["ranges"] if p.exists() else []


def gs1_lookup(code: str) -> dict | None:
    digits = re.sub(r"\D", "", code)
    if len(digits) == 12:          # UPC-A is a GTIN-13 with a leading 0
        digits = "0" + digits
    if len(digits) == 14:          # GTIN-14: indicator digit first
        digits = digits[1:]
    if len(digits) == 8:
        return {"prefix": digits[:3], "org": "EAN-8 (short code; prefix ranges differ - treat as unknown)"}
    if len(digits) != 13:
        return None
    p = int(digits[:3])
    if digits.startswith(("978", "979")):
        return {"prefix": digits[:3], "org": "Bookland (ISBN) - a book; the ISBN group identifies language/region"}
    for r in gs1_ranges():
        if r["from"] <= p <= r["to"]:
            return {"prefix": digits[:3], "org": r["org"]}
    return {"prefix": digits[:3], "org": "not in the table"}


def _cur_match(rec: dict, cur: str) -> bool:
    c = cur.strip()
    for item in rec.get("currencies", []):
        if c.upper() == item["code"] or c == item.get("symbol") or c == item.get("narrow_symbol"):
            return True
        if c.lower() == item.get("name", "").lower():
            return True
    return False


OFFICIAL = ("official", "de_facto_official", "official_regional")


def _counts(item: dict, min_pct: float) -> bool:
    """A language counts for signage/menus if it is (regionally) official or spoken by >= min_pct %.
    Second languages spoken by a minority (French in Germany, English almost everywhere) do not."""
    return item.get("official") in OFFICIAL or item["pct"] >= min_pct


def _lang_match(rec: dict, lang: str, min_pct: float) -> bool:
    l = lang.strip().lower()
    for item in rec.get("languages", []):
        code = item["code"].lower()
        if (code == l or code.split("_")[0] == l or item.get("name", "").lower() == l) and _counts(item, min_pct):
            return True
    return False


def _script_match(rec: dict, script: str, min_pct: float) -> bool:
    s = script.strip()
    codes = SCRIPT_ALIASES.get(s.upper(), [s[:1].upper() + s[1:].lower()])
    for item in rec.get("languages", []):
        if item.get("script") in codes and _counts(item, min_pct):
            return True
    return False


def voltage_class(rec: dict) -> set[str]:
    v = rec.get("voltage", "")
    nums = [int(n) for n in re.findall(r"(?<![\d/])(\d{3})(?=\s*(?:/|V))", v)]
    out = set()
    for n in nums:
        if 100 <= n <= 130:
            out.add("100-130")
        elif 200 <= n <= 250:
            out.add("200-250")
    return out


def filter_countries(*, plug_all=None, plug_any=None, calling=None, tld=None, currency=None, drive=None,
                     lang=None, script=None, week=None, clock=None, temp=None, paper=None, emergency=None,
                     freq=None, voltage=None, min_pct: float = 30.0, include_non_iso: bool = False) -> list[dict]:
    rows = []
    for iso, rec in countries().items():
        if not in_universe(iso, include_non_iso):
            continue
        why = []
        if plug_all:
            types = set(rec.get("plug_types", []))
            if not types or not set(plug_all) <= types:
                continue
            why.append("plugs " + ",".join(sorted(types)))
        if plug_any:
            types = set(rec.get("plug_types", []))
            if not types & set(plug_any):
                continue
            why.append("plugs " + ",".join(sorted(types)))
        if calling:
            cc = calling.lstrip("+").strip()
            if cc not in rec.get("calling_codes", []):
                continue
            why.append(f"+{cc}")
        if tld:
            t = "." + tld.lstrip(".").lower()
            if rec.get("cctld") != t:
                continue
            why.append(t)
        if currency:
            if not all(_cur_match(rec, c) for c in currency):
                continue
            why.append("currency " + "/".join(i["code"] for i in rec.get("currencies", [])))
        if drive:
            if rec.get("driving_side") != drive:
                continue
            why.append(f"drives {drive}")
        if lang:
            if not all(_lang_match(rec, l, min_pct) for l in lang):
                continue
            why.append("lang " + ",".join(lang))
        if script:
            if not all(_script_match(rec, s, min_pct) for s in script):
                continue
            why.append("script " + ",".join(script))
        if week:
            if rec.get("week_starts") != week[:3].lower():
                continue
            why.append(f"week starts {rec.get('week_starts')}")
        if clock:
            if rec.get("clock") != clock:
                continue
            why.append(f"{clock} clock")
        if temp:
            if rec.get("temperature") != temp:
                continue
            why.append(temp)
        if paper:
            if rec.get("paper", "A4").lower() != paper.lower():
                continue
            why.append(paper)
        if emergency:
            nums = {n for v in (rec.get("emergency") or {}).values() for n in v}
            if not all(e in nums for e in emergency):
                continue
            why.append("emergency " + ",".join(emergency))
        if freq:
            if f"{freq} Hz" not in rec.get("frequency", "").replace(" ", " "):
                continue
            why.append(f"{freq} Hz")
        if voltage:
            if voltage not in voltage_class(rec):
                continue
            why.append(f"{voltage} V")
        rows.append({"iso": iso, "name": rec["name"], "why": "; ".join(why), "rec": rec})
    rows.sort(key=lambda r: r["name"])
    return rows


def country(code_or_name: str) -> tuple[str, dict]:
    q = code_or_name.strip()
    cs = countries()
    if q.upper() in cs:
        return q.upper(), cs[q.upper()]
    for iso, rec in cs.items():
        if rec["name"].lower() == q.lower() or q.lower() in [a.lower() for a in rec.get("alt_names", [])]:
            return iso, rec
    hits = [(iso, rec) for iso, rec in cs.items() if q.lower() in rec["name"].lower()]
    if len(hits) == 1:
        return hits[0]
    raise IglError(f"Unknown country {q!r}" + (f"; did you mean {', '.join(r['name'] for _, r in hits[:6])}?"
                                               if hits else ""))


def tld_country(tld: str) -> str | None:
    t = "." + tld.lstrip(".").lower()
    for iso, rec in countries().items():
        if rec.get("cctld") == t:
            return iso
    return None


def calling_code_countries(cc: str) -> list[str]:
    return [iso for iso, rec in countries().items() if cc in rec.get("calling_codes", [])]


def currency_countries(symbol_or_code: str) -> list[str]:
    """Countries of the board's universe that use the currency: the same set `countries --currency` links
    (minor territories outside that universe, such as Ascension or the Canary Islands, are not counted)."""
    return [iso for iso, rec in countries().items() if in_universe(iso) and _cur_match(rec, symbol_or_code)]


def former_currency(symbol_or_code: str) -> list[tuple[str, dict]]:
    out = []
    for iso, rec in countries().items():
        for item in rec.get("former_currencies", []):
            if symbol_or_code.upper() == item["code"] or symbol_or_code == item.get("symbol"):
                out.append((iso, item))
    return out
