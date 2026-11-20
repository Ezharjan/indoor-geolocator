"""Location signals hidden in text (OCR lines, decoded codes, text you typed from a crop).

Finds: writing systems and Latin diacritics, phone numbers, URLs/e-mails/ccTLDs, prices and currencies
(current and historical), dates and calendar eras, 12/24-hour times, postcodes with distinctive
formats, units, company-form suffixes, tax words, address words. Every finding is a HINT (machine
suggestion) until you confirm the text on a zoomed crop and record it with `igl.py note`.
"""
from __future__ import annotations

import re
import unicodedata

from . import knowledge
from .ocr import scripts_in

DIACRITIC_HINTS = [
    ("ß", "German"), ("ä|ö|ü", "German/Swedish/Finnish/Estonian/Hungarian/Turkish (ö,ü)"),
    ("ł|ą|ę|ż|ź|ś|ć|ń", "Polish"), ("ř|ě|ů", "Czech"), ("ľ|ĺ|ŕ|ô", "Slovak"), ("ő|ű", "Hungarian"),
    ("ñ", "Spanish (or Basque/Galician/Filipino)"), ("ã|õ", "Portuguese"),
    ("ç", "French/Portuguese/Catalan/Turkish/Albanian"), ("ğ|ş|ı|İ", "Turkish/Azerbaijani"),
    ("ș|ț|ă|î|â", "Romanian"), ("đ|ơ|ư|ạ|ả|ấ|ầ|ẩ|ậ|ắ|ằ|ẳ|ẵ|ặ|ẹ|ẻ|ẽ|ế|ề|ể|ễ|ệ|ỉ|ị|ọ|ỏ|ố|ồ|ổ|ỗ|ộ|ớ|ờ|ở|ỡ|ợ|ụ|ủ|ứ|ừ|ử|ữ|ự|ỳ|ỵ|ỷ|ỹ",
                                   "Vietnamese"),
    ("å|ø|æ", "Danish/Norwegian (å also Swedish/Finnish)"), ("þ|ð", "Icelandic (ð also Faroese)"),
    ("č|š|ž", "Czech/Slovak/Slovenian/Croatian/Lithuanian/Latvian/Bosnian"), ("ė|ų|į|ū", "Lithuanian"),
    ("ā|ē|ī|ū|ķ|ļ|ņ|ģ", "Latvian (macrons also Māori/Hawaiian)"), ("õ", "Estonian/Portuguese"),
    ("ğ", "Turkish"), ("ł", "Polish/Sorbian"), ("ŵ|ŷ", "Welsh"), ("ċ|ġ|ħ|ż", "Maltese"),
    ("à|è|ì|ò|ù", "Italian/French/Catalan"), ("ê|ë|ï|î|û|œ|ÿ", "French"),
]
COMPANY_FORMS = [
    (r"\bGmbH\b|\bAG\b(?= |$)|\bKG\b|\be\.\s?V\.", "DE/AT/CH company form"), (r"\bS\.?A\.?R\.?L\.?\b|\bSAS\b|\bEURL\b", "FR (or LU/BE/MA/TN)"),
    (r"\bS\.p\.A\.|\bS\.r\.l\.|\bS\.n\.c\.", "IT"), (r"\bB\.V\.|\bN\.V\.|\bV\.O\.F\.", "NL/BE"),
    (r"\bLtd\.?\b|\bPLC\b|\bLLP\b", "UK/IE/Commonwealth"), (r"\bLLC\b|\bInc\.?\b|\bCorp\.?\b", "US (also CA/PH)"),
    (r"\bPty\.? Ltd\b", "AU/ZA"), (r"\bPvt\.? Ltd\b|\bPrivate Limited\b", "IN/PK/BD/LK/NP"),
    (r"\bSdn\.? Bhd\b|\bBhd\b", "MY"), (r"\bPte\.? Ltd\b", "SG"), (r"\bPT\b(?= [A-Z])|\bTbk\b", "ID"),
    (r"\bS\.A\. de C\.V\.|\bS\. de R\.L\.", "MX/Central America"), (r"\bLtda\.?\b", "BR/PT/CO/CL"),
    (r"\bA/S\b|\bApS\b", "DK/NO"), (r"\bAB\b(?= |$)", "SE"), (r"\bOy\b|\bOyj\b", "FI"), (r"\bAS\b(?= |$)", "NO/EE"),
    (r"\bSp\. z o\.o\.|\bS\.A\.\b", "PL (S.A. many)"), (r"\bs\.r\.o\.|\ba\.s\.\b", "CZ/SK"),
    (r"\bKft\.?\b|\bZrt\.?\b|\bBt\.?\b", "HU"), (r"\bd\.o\.o\.|\bd\.d\.", "SI/HR/BA/RS/ME"), (r"\bOOO\b|\bООО\b|\bАО\b", "RU/CIS"),
    (r"株式会社|有限会社|\(株\)|㈱", "JP"), (r"有限公司|股份有限公司", "CN/HK/TW/MO"), (r"\(주\)|주식회사", "KR"),
    (r"\bA\.Ş\.|\bLtd\. Şti\.", "TR"), (r"\bS\.A\.S\.\b", "CO/FR"), (r"\bS\.R\.L\.\b", "RO/IT/AR/MD"),
    (r"\bCo\.,? Ltd\.?", "East/Southeast Asia (also generic)"),
]
TAX_WORDS = [
    (r"\bMwSt\.?|\bUSt\.?|inkl\. MwSt", "DE/AT (VAT word)"), (r"\bTVA\b|\bHT\b|\bTTC\b", "FR/BE/LU/CH (fr)"),
    (r"\bIVA\b", "ES/IT/PT/LatAm"), (r"\bBTW\b", "NL/BE"), (r"\bMOMS\b|\bmoms\b", "DK/SE/NO"),
    (r"\bALV\b", "FI"), (r"\bGST\b", "AU/NZ/SG/IN/CA/MY"), (r"\bHST\b|\bPST\b|\bQST\b|\bTPS\b|\bTVQ\b", "CA"),
    (r"\bsales tax\b", "US"), (r"税込|税抜|内税|外税", "JP"), (r"含税|不含税|增值税|发票", "CN"), (r"부가세|부가가치세", "KR"),
    (r"\bKDV\b", "TR"), (r"\bНДС\b", "RU/CIS"), (r"\bDPH\b", "CZ/SK"), (r"\bPDV\b", "HR/RS/BA/ME/SI"),
    (r"\bPTU\b", "PL"), (r"\bÁFA\b", "HU"), (r"\bΦΠΑ\b", "GR/CY"), (r"\bVAT\b", "VAT-using country (UK/EU/many)"),
]
ADDRESS_WORDS = [
    (r"\b\w*(straße|strasse|str\.|gasse|platz|weg)\b", "German-speaking"), (r"\b(rue|avenue|boulevard|bd\.?|allée|impasse)\b", "French-speaking"),
    (r"\b(calle|avenida|avda\.?|plaza|carrera|paseo)\b", "Spanish-speaking"), (r"\b(rua|travessa|largo|praça)\b", "Portuguese-speaking"),
    (r"\b(via|viale|piazza|corso|vicolo)\b", "Italian"), (r"\b(straat|laan|plein|gracht|weg)\b", "Dutch"),
    (r"\b(ul\.|ulica|aleja|al\.|plac)\b", "Polish"), (r"\b(ул\.|улица|проспект|пр\.|пер\.)", "Russian/CIS"),
    (r"\b(gatan|vägen|gata)\b", "Swedish"), (r"\b(gade|vej|gata|gaten|veien)\b", "Danish/Norwegian"),
    (r"丁目|番地|[0-9０-９]+番[0-9０-９]+号|〒", "Japanese address"), (r"[路街道巷弄]\d*号|[省市区县镇]", "Chinese address"),
    (r"(?:-gu|-dong|-ro|-gil)\b|[구동로길]\s*\d", "Korean address"), (r"\b(soi|thanon|tambon|amphoe)\b|ซอย|ถนน", "Thai address"),
    (r"\b(jalan|jl\.|gang|kelurahan|kecamatan)\b", "Indonesian/Malay address"), (r"\b(đường|phường|quận)\b", "Vietnamese address"),
    (r"\b(sokak|sok\.|caddesi|cad\.|mahallesi|mah\.)\b", "Turkish address"), (r"\b(utca|út|tér)\b", "Hungarian address"),
    (r"\b(ulice|náměstí|třída)\b", "Czech address"), (r"\b(odos|οδός|λεωφ\.)", "Greek address"),
]
POSTCODES = [   # (regex, label, iso) - only formats distinctive enough to be useful
    (r"\b(GIR 0AA|[A-PR-UWYZ][A-HK-Y]?\d[A-Z\d]? ?\d[ABD-HJLNP-UW-Z]{2})\b", "UK postcode", "GB"),
    (r"\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z] ?\d[ABCEGHJ-NPRSTV-Z]\d\b", "Canadian postal code", "CA"),
    (r"\b[1-9]\d{3} ?(?!SA|SD|SS)[A-Z]{2}\b", "Dutch postcode", "NL"),
    (r"〒\s?\d{3}-\d{4}|\b\d{3}-\d{4}\b(?=.*[都道府県市区町村])", "Japanese postcode", "JP"),
    (r"\b\d{5}-\d{3}\b", "Brazilian CEP", "BR"), (r"\b\d{2}-\d{3}\b(?= [A-ZŁŚŻŹ])", "Polish postcode", "PL"),
    (r"\b\d{4}-\d{3}\b(?= [A-Z])", "Portuguese postcode", "PT"),
    (r"\b[AC-FHKNPRTV-Y]\d{2} ?[AC-FHKNPRTV-Y0-9]{4}\b", "Irish Eircode", "IE"),
    (r"\b\d{5}-\d{4}\b", "US ZIP+4", "US"), (r"\b\d{3} \d{2}\b(?= [A-ZÅÄÖ][a-zåäö])", "SE/CZ/SK/GR postcode", ""),
]
CURRENCY_TOKENS = ["R$", "US$", "CA$", "A$", "AU$", "NZ$", "HK$", "NT$", "S$", "MX$", "RD$", "€", "£", "¥", "￥", "₩",
                   "₹", "₽", "₺", "₫", "฿", "₪", "₱", "₦", "₴", "₸", "₼", "₾", "₡", "₲", "₵", "₭", "₮", "₨", "৳", "zł",
                   "Kč", "Ft", "lei", "лв", "kr", "Fr.", "CHF", "RM", "Rp", "KSh", "TSh", "USh", "MAD", "AED", "SAR",
                   "QAR", "د.إ", "ر.س", "₹", "元", "円", "원", "$"]
ERA = [(r"令和\s?(\d{1,2}|元)年", "Japanese era Reiwa (2019-)", "JP"), (r"平成\s?(\d{1,2}|元)年", "Japanese era Heisei (1989-2019)", "JP"),
       (r"昭和\s?\d{1,2}年", "Japanese era Showa", "JP"), (r"民國\s?\d{2,3}年|民国\s?\d{2,3}年", "ROC calendar (Taiwan)", "TW"),
       (r"พ\.ศ\.\s?25\d\d|\b25[5-7]\d\b(?=.*[฀-๿])", "Thai Buddhist Era", "TH"),
       (r"\b(13|14)\d\d\s?(ه\.ش|هـ\.ش|ش\.)", "Persian/Solar Hijri year (IR/AF)", "IR"),
       (r"\b14[0-4]\d\s?(هـ|AH)\b", "Islamic Hijri year", ""), (r"\b57[89]\d\b(?=.*[֐-׿])", "Hebrew calendar year", "IL"),
       (r"단기\s?43\d\d", "Korean Dangi year", "KR"), (r"\b20[0-9]{2}\s?년\s?\d{1,2}\s?월", "Korean date", "KR"),
       (r"\b20[0-9]{2}\s?年\s?\d{1,2}\s?月\s?\d{1,2}\s?日", "CJK date (Y年M月D日)", "")]


def _ascii_digits(text: str) -> str:
    """NFKC (full-width ０-９ ￥ ，, ㋿ -> 令和, ㎡ -> m2) plus every other decimal digit (Arabic-Indic, Persian,
    Devanagari, Thai ...) mapped to ASCII, so numeric patterns work in any script."""
    t = unicodedata.normalize("NFKC", text)
    return "".join(str(unicodedata.decimal(c)) if (not c.isascii() and unicodedata.decimal(c, None) is not None)
                   else c for c in t)


def mine(lines: list[str], phone_regions: list[str] | None = None) -> dict:
    raw = "\n".join(lines)
    text = _ascii_digits(raw)            # numeric patterns, prices, dates, units, domains
    sc_text = raw                        # scripts and diacritics are read from the original characters
    out: dict[str, list] = {"scripts": [], "language_hints": [], "phones": [], "domains": [], "emails": [],
                            "currencies": [], "dates": [], "times": [], "postcodes": [], "units": [],
                            "company_forms": [], "tax_words": [], "address_words": [], "notes": []}
    sc = scripts_in(sc_text)
    for name, n in sorted(sc.items(), key=lambda kv: -kv[1]):
        out["scripts"].append({"script": name, "chars": n})
    low = text.lower()
    for pat, lang in DIACRITIC_HINTS:
        hits = sorted(set(re.findall(pat, sc_text)))
        if hits:
            out["language_hints"].append({"chars": "".join(hits)[:20], "suggests": lang})
    # phones
    phones = []
    try:
        import phonenumbers  # type: ignore
        from phonenumbers import carrier, geocoder, timezone
        regions = [None] + [r.upper() for r in (phone_regions or [])]
        seen = set()
        for reg in regions:
            for m in phonenumbers.PhoneNumberMatcher(text, reg or "ZZ", leniency=phonenumbers.Leniency.VALID):
                n = m.number
                e164 = phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)
                if e164 in seen:
                    continue
                seen.add(e164)
                phones.append({"raw": m.raw_string, "e164": e164,
                               "country": phonenumbers.region_code_for_number(n),
                               "area": geocoder.description_for_number(n, "en") or "",
                               "carrier": carrier.name_for_number(n, "en") or "",
                               "timezones": list(timezone.time_zones_for_number(n)),
                               "assumed_region": reg or "international format"})
    except ImportError:
        out["notes"].append("`pip install phonenumbers` for offline phone-number geolocation (area/city level)")
        for m in re.finditer(r"(?:\+|00)\s?(\d{1,3})[\s.\-()]*\d[\d\s.\-()]{5,}\d", text):
            cc = m.group(1)
            for k in (cc[:3], cc[:2], cc[:1]):
                isos = knowledge.calling_code_countries(k)
                if isos:
                    # +44 is shared by GB, GG, JE, IM and +1 by the whole NANP: name a country only when unique
                    phones.append({"raw": m.group(0).strip(), "calling_code": "+" + k, "countries": isos,
                                   "country": isos[0] if len(isos) == 1 else None,
                                   "note": "calling code only (install phonenumbers for area/city)"})
                    break
    out["phones"] = phones
    # domains / e-mails
    for m in re.finditer(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+([a-z]{2,24}))(?:/[^\s]*)?", low):
        host, tld = m.group(1), m.group(2)
        labels = host.split(".")
        if re.fullmatch(r"\d+(\.\d+)*", host) or tld in ("jpg", "png", "pdf", "html", "php", "pix", "gov") \
                or any(len(l) > 40 or (sum(c.isdigit() for c in l) > 8) for l in labels[:-1]):
            continue
        iso = knowledge.tld_country(tld) if len(tld) == 2 else None
        rec = {"domain": host, "tld": "." + tld, "country": iso}
        if rec not in out["domains"]:
            out["domains"].append(rec)
    for m in re.finditer(r"\b[\w.+-]+@((?:[\w-]+\.)+([a-z]{2,24}))\b", low):
        tld = m.group(2)
        out["emails"].append({"domain": m.group(1), "tld": "." + tld,
                              "country": knowledge.tld_country(tld) if len(tld) == 2 else None})
    # currencies (symbols near numbers) and amount formatting
    spans: list[tuple[int, int]] = []
    for tok in CURRENCY_TOKENS:
        esc = re.escape(tok)
        # symbol first ("€12.50", "R$ 10"), else amount first ("12,50 €", "1200円"); an amount must not be the
        # tail of a time or a longer number ("22:00 ¥1,200" -> "¥1,200", not "00 ¥")
        m = re.search(rf"{esc}\s?\d(?:[\d.,' ]*\d)?", text) or \
            re.search(rf"(?<![\d:.,])\d(?:[\d.,' ]*\d)?\s?{esc}", text)
        if not m or any(x["token"] == tok for x in out["currencies"]):
            continue
        if any(m.start() < e and s0 < m.end() for s0, e in spans):     # "$" inside "R$ 10" is not a second currency
            continue
        spans.append((m.start(), m.end()))
        isos = knowledge.currency_countries(tok)
        former = knowledge.former_currency(tok)
        item = {"token": tok, "sample": m.group(0).strip()[:24], "countries": isos[:30], "n_countries": len(isos)}
        if former:
            item["former_currency_of"] = [f"{iso} until {c.get('until')}" for iso, c in former][:6]
        out["currencies"].append(item)
    for m in re.finditer(r"\b(EUR|GBP|USD|JPY|CNY|RMB|KRW|INR|RUB|TRY|CHF|SEK|NOK|DKK|PLN|CZK|HUF|RON|BGN|THB|VND|IDR|MYR|"
                         r"SGD|HKD|TWD|AUD|NZD|CAD|MXN|BRL|ARS|CLP|COP|PEN|ZAR|EGP|MAD|AED|SAR|QAR|ILS|PHP|NGN|KES|UAH|KZT|"
                         r"DEM|FRF|ITL|ESP|NLG|BEF|ATS|PTE|GRD|FIM|IEP)\b", text):
        code = m.group(1)
        if any(x["token"] == code for x in out["currencies"]):
            continue
        isos = knowledge.currency_countries("CNY" if code == "RMB" else code)
        former = knowledge.former_currency(code)
        out["currencies"].append({"token": code, "countries": isos[:30], "n_countries": len(isos),
                                  **({"former_currency_of": [f"{i} until {c.get('until')}" for i, c in former][:6]}
                                     if former else {})})
    if re.search(r"\d{1,3}(?:\.\d{3})+,\d{2}\b", text):
        out["notes"].append("amounts like 1.234,56 (decimal comma, dot thousands): continental Europe/LatAm/Indonesia...")
    if re.search(r"\d{1,3}(?:,\d{3})+\.\d{2}\b", text):
        out["notes"].append("amounts like 1,234.56 (decimal point): UK/US/IE/Asia/AU...")
    if re.search(r"\d{1,3}(?:'\d{3})+(?:[.,]\d{2})?\b", text):
        out["notes"].append("apostrophe thousands separator (1'234.50): Switzerland/Liechtenstein")
    if re.search(r"\b\d{1,2},\d{2}\s?€", text):
        out["notes"].append("price written '12,50 €' (symbol after, comma): FR/DE/ES/IT/AT/BE... (not IE/NL style)")
    # dates and eras
    for pat, label, iso in ERA:
        for m in re.finditer(pat, text):
            out["dates"].append({"sample": m.group(0)[:30], "type": label, "country": iso or None})
            break
    for m in re.finditer(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b", text):
        a, b = int(m.group(1)), int(m.group(2))
        kind = "D.M.Y" if a > 12 else ("M/D/Y" if b > 12 else "ambiguous D/M vs M/D")
        sep = "dots (DE/AT/CH/RU/PL/CZ/FI/NO/TR...)" if "." in m.group(0) else "slashes"
        out["dates"].append({"sample": m.group(0), "type": f"{kind}, {sep}"})
    for m in re.finditer(r"\b(19|20)\d{2}[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b", text):
        out["dates"].append({"sample": m.group(0), "type": "Y-M-D (ISO; common in East Asia, Sweden, Lithuania, Canada)"})
    out["dates"] = out["dates"][:15]
    # times
    if re.search(r"\b(1[0-2]|0?[1-9])(:[0-5]\d)?\s?(am|pm|a\.m\.|p\.m\.)(?!\w)", low) or re.search(r"(午前|午後|上午|下午|오전|오후)", text):
        out["times"].append("12-hour clock in use")
    if re.search(r"\b(1[3-9]|2[0-3]):[0-5]\d\b", text):
        out["times"].append("24-hour times (13:00-23:59)")
    if re.search(r"\b([01]?\d|2[0-3])h[0-5]\d\b", low):
        out["times"].append("'14h30' style: FR/PT/BR/ES-speaking/Quebec")
    # postcodes
    for pat, label, iso in POSTCODES:
        for m in re.finditer(pat, text):
            out["postcodes"].append({"sample": m.group(0), "format": label, "country": iso or None})
            break
    # units
    for pat, label in [(r"°\s?F\b", "Fahrenheit (US, LR, some Caribbean)"), (r"°\s?C\b", "Celsius"),
                       (r"\bmph\b", "miles per hour (US/UK)"), (r"\bkm/h\b", "km/h"), (r"\b\d+\s?(lbs?|oz)\b", "pounds/ounces (US; UK for body weight)"),
                       (r"\bsq\.? ?ft\b|\bsqft\b", "square feet (US/UK/IN/HK/SG/AE listings)"), (r"\d\s?坪", "tsubo/ping (JP/TW real estate)"),
                       (r"\d\s?평", "pyeong (Korea real estate)"), (r"\bm²|\bm2\b|㎡", "square metres"), (r"\bfl\.? ?oz\b", "fluid ounces (US)"),
                       (r"\bgal(lon)?s?\b", "gallons"), (r"\b\d+\s?(?:pt|pint)s?\b", "pints (UK/IE pubs)")]:
        if re.search(pat, text, re.I):
            out["units"].append(label)
    for pat, label in COMPANY_FORMS:
        m = re.search(pat, text)
        if m:
            out["company_forms"].append({"sample": m.group(0), "suggests": label})
    for pat, label in TAX_WORDS:
        m = re.search(pat, text)
        if m:
            out["tax_words"].append({"sample": m.group(0), "suggests": label})
    for pat, label in ADDRESS_WORDS:
        m = re.search(pat, text, re.I)
        if m:
            out["address_words"].append({"sample": m.group(0)[:30], "suggests": label})
    return {k: v for k, v in out.items() if v}
