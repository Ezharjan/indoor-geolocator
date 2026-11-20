"""Offline tables, code payload interpretation (with privacy redaction) and text mining."""
from __future__ import annotations

from iglib import knowledge
from iglib.codes import _ean_ok, interpret
from iglib.textmine import mine


# ----------------------------------------------------------------------------- tables
def test_universe_and_lookup():
    assert knowledge.universe_size() == 250                      # 249 ISO 3166-1 + Kosovo
    assert knowledge.country("UK")[0] == "GB"
    assert knowledge.country("Japan")[0] == "JP"
    assert knowledge.tld_country(".uk") == "GB"
    assert set(knowledge.calling_code_countries("44")) >= {"GB", "GG", "IM", "JE"}


def test_filters_intersect():
    isos = {r["iso"] for r in knowledge.filter_countries(plug_all=["G"], drive="left", currency=["£"])}
    assert "GB" in isos and "IE" not in isos
    fr = {r["iso"] for r in knowledge.filter_countries(lang=["fr"])}
    assert {"FR", "BE", "CH", "CA"} <= fr and "DE" not in fr      # minority second languages do not count
    hant = {r["iso"] for r in knowledge.filter_countries(script=["Hant"])}
    assert {"TW", "HK", "MO"} <= hant and "CN" not in hant
    us = {r["iso"] for r in knowledge.filter_countries(temp="fahrenheit")}
    assert "US" in us and "CA" not in us


def test_gs1():
    assert "Germany" in knowledge.gs1_lookup("4006381333931")["org"]
    assert "Bookland" in knowledge.gs1_lookup("9783161484100")["org"]


# ----------------------------------------------------------------------------- codes
def _crc16(s: str) -> str:
    crc = 0xFFFF
    for ch in s.encode():
        crc ^= ch << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def _tlv(tag: str, val: str) -> str:
    return f"{tag}{len(val):02d}{val}"


def test_emv_merchant_qr():
    acct = _tlv("00", "br.gov.bcb.pix") + _tlv("01", "key@example.com")
    body = (_tlv("00", "01") + _tlv("26", acct) + _tlv("52", "5812") + _tlv("53", "986") + _tlv("58", "BR")
            + _tlv("59", "PADARIA CENTRAL") + _tlv("60", "SAO PAULO") + "6304")
    r = interpret(body + _crc16(body))
    assert r["kind"] == "emv-payment" and r["merchant_name"] == "PADARIA CENTRAL"
    assert r["merchant_city"] == "SAO PAULO" and r["country"] == "BR" and r["scheme_country"] == "BR"


def test_wifi_password_always_redacted():
    for payload in ("WIFI:T:WPA;S:Cafe Blau;P:hunter2;;", "WIFI:P:hunter2;T:WPA;S:Cafe Blau;;"):
        r = interpret(payload)
        assert r["ssid"] == "Cafe Blau" and "hunter2" not in r["redacted"] and r["secret"]


def test_contact_cards_redact_people_keep_business():
    v = interpret("BEGIN:VCARD\nVERSION:3.0\nN:Doe;John;;;\nFN:John Doe\nORG:Hotel X\nEMAIL:jd@hotel-x.at\n"
                  "ADR:;;Ring 1;Wien;;1010;Austria\nEND:VCARD")
    assert "John" not in v["redacted"] and "@hotel-x.at" in v["redacted"] and v["org"] == "Hotel X"
    m = interpret("MECARD:N:Doe,John;TEL:+431234567;ADR:Ring 1, Wien;;")
    assert "Doe" not in m["redacted"] and "Ring 1" in m["redacted"]


def test_swiss_bill_epc_upi_geo():
    spc = interpret("SPC\n0200\n1\nCH4431999123000889012\nS\nRobert Schneider AG\nRue du Lac\n1268\n2501\nBiel\nCH")
    assert spc["kind"] == "swiss-qr-bill" and spc["country"] == "CH" and "889012" not in spc["redacted"]
    epc = interpret("BCD\n002\n1\nSCT\nBPOTBEB1\nRed Cross of Belgium\nBE72000000001616\nEUR1")
    assert epc["iban_country"] == "BE" and epc["beneficiary"] == "Red Cross of Belgium"
    upi = interpret("upi://pay?pa=shop@okicici&pn=Sharma%20Sweets&cu=INR")
    assert upi["country"] == "IN" and upi["payee_name"] == "Sharma Sweets"
    g = interpret("geo:-33.8568,151.2153")
    assert g["lat"] == -33.8568 and g["lon"] == 151.2153


def test_gtin_checksum():
    assert _ean_ok("4006381333931") and not _ean_ok("4006381333932")
    assert _ean_ok("96385074")                                     # EAN-8
    assert _ean_ok("036000291452")                                 # UPC-A


# ----------------------------------------------------------------------------- text mining
def test_currencies_any_script():
    m = mine(["営業時間 10:00〜22:00 ￥１，２００（税込）"])
    assert [(c["token"], c["sample"]) for c in m["currencies"]] == [("¥", "¥1,200")]
    assert m["tax_words"][0]["suggests"] == "JP"
    m = mine(["R$ 1.234,56"])
    assert [c["token"] for c in m["currencies"]] == ["R$"]          # no duplicate generic "$"


def test_dates_eras_times():
    m = mine(["令和５年１２月", "۱۴۰۲ ه.ش", "Open until 10 p.m.", "Ab 14h30", "Last orders 23:30"])
    types = " ".join(d["type"] for d in m["dates"])
    assert "Reiwa" in types and "Solar Hijri" in types
    assert "12-hour clock in use" in m["times"] and "'14h30' style: FR/PT/BR/ES-speaking/Quebec" in m["times"]


def test_postcodes_phones_domains():
    m = mine(["Visit www.hotel-beispiel.at", "Tel +43 1 234567", "London SW1A 1AA"])
    assert any(d["country"] == "AT" for d in m["domains"])
    assert any(p.get("country") == "AT" for p in m["phones"])
    assert any(p["country"] == "GB" for p in m["postcodes"])


def test_diacritics_and_scripts():
    m = mine(["Straße", "Łódź", "Привет"])
    langs = " ".join(h["suggests"] for h in m["language_hints"])
    assert "German" in langs or "DE" in langs
    assert any(s["script"] == "CYRILLIC" for s in m["scripts"])


def test_ocr_language_suggestion():
    from iglib.ocr import suggest_langs
    signals = mine(["Tel. +43 1 234567", "www.hotel-beispiel.at", "inkl. MwSt"])
    countries, langs = suggest_langs(signals, ["eng"], ["eng", "deu", "fra"])
    assert "AT" in countries and langs == ["deu"]
    assert suggest_langs(signals, ["deu", "eng"], ["eng", "deu"])[1] == []          # already used
    assert suggest_langs(signals, ["eng"], ["eng"])[1] == []                        # not installed
