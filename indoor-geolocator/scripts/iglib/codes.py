"""QR codes and barcodes: detection (OpenCV, optionally pyzbar) and payload interpretation.

A decoded payload is often the single most precise clue indoors: a URL names the business, an EMVCo
payment QR carries the merchant NAME and CITY, a Swiss QR-bill or EPC transfer code carries an
address or an IBAN (country), vCards carry addresses, Wi-Fi codes carry an SSID (WiGLE-searchable).
Secrets (Wi-Fi passwords, full IBANs, personal names) are redacted in what we store and print.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse

from PIL import Image

from . import imaging

EMV_NETWORKS = {   # merchant-account GUIDs inside EMVCo QR (tags 26-51) -> scheme, country
    "br.gov.bcb.pix": ("Pix", "BR"), "sg.paynow": ("PayNow", "SG"), "sg.com.nets": ("NETS", "SG"),
    "a000000677010111": ("PromptPay", "TH"), "a000000677010112": ("PromptPay", "TH"),
    "a000000677010114": ("PromptPay", "TH"), "id.co.qris.www": ("QRIS", "ID"), "id.or.gpnqr.www": ("QRIS", "ID"),
    "hk.com.hkicl": ("FPS", "HK"), "my.com.paynet": ("DuitNow", "MY"), "a0000006150001": ("DuitNow", "MY"),
    "ph.ppmi.p2m": ("QR Ph", "PH"), "com.p2pqrpay": ("QR Ph", "PH"), "vn.napas": ("VietQR", "VN"),
    "a000000727": ("VietQR/NAPAS", "VN"), "jp.or.paymentsjapan": ("JPQR", "JP"), "in.org.npci": ("UPI/BharatQR", "IN"),
    "mx.com.banxico": ("CoDi", "MX"), "ke.go.qr": ("KE-QR", "KE"), "lk.com.lankapay": ("LankaQR", "LK"),
    "kh.gov.nbc.bakong": ("Bakong/KHQR", "KH"), "np.com.nepalpay": ("NepalPay", "NP"),
    "pk.gov.sbp": ("Raast", "PK"), "a000000333010101": ("UnionPay", "CN"),
}


def _bgr(im: Image.Image):
    import numpy as np  # type: ignore
    a = np.array(im.convert("RGB"))
    return a[:, :, ::-1].copy()


def detect(img: Image.Image) -> dict:
    """Find and decode QR codes and 1D barcodes on the full frame, a 2x upscale and overlapping tiles."""
    out: list[dict] = []
    notes: list[str] = []
    try:
        import cv2  # type: ignore
    except ImportError:
        cv2 = None
        notes.append("OpenCV missing (pip install opencv-python-headless): QR/barcode decoding skipped - look "
                     "for codes yourself and decode a crop with any QR app if needed")
    views = [("full", img, 1.0, (0, 0))]
    W, H = img.size
    if max(W, H) < 2600:
        s = 2.0
        views.append(("up2", img.resize((W * 2, H * 2), Image.LANCZOS), s, (0, 0)))
    for label, box in imaging.tiles((W, H), 3, 3, overlap=0.2):
        part = img.crop(box)
        s = min(3.0, max(1.0, 1400 / max(part.size)))
        views.append((f"tile-{label}", part.resize((round(part.width * s), round(part.height * s)), Image.LANCZOS),
                      s, (box[0], box[1])))

    def add(kind, data, pts, scale, off, method):
        if not data:
            return
        xs = [p[0] / scale + off[0] for p in pts] if pts is not None and len(pts) else [0]
        ys = [p[1] / scale + off[1] for p in pts] if pts is not None and len(pts) else [0]
        box = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
        for o in out:
            if o["raw"] == data:
                return
        out.append({"type": kind, "raw": data, "box": box, "method": method})

    if cv2 is not None:
        detectors = []
        try:
            detectors.append(("qr-aruco", cv2.QRCodeDetectorAruco()))
        except Exception:  # noqa: BLE001
            pass
        detectors.append(("qr", cv2.QRCodeDetector()))
        try:
            bd = cv2.barcode.BarcodeDetector()
        except Exception:  # noqa: BLE001
            try:
                bd = cv2.barcode_BarcodeDetector()
            except Exception:  # noqa: BLE001
                bd = None
        for label, view, scale, off in views:
            arr = _bgr(view)
            for dname, det in detectors:
                try:
                    ok, texts, pts, _ = det.detectAndDecodeMulti(arr)
                except Exception:  # noqa: BLE001
                    ok, texts, pts = False, [], None
                if ok:
                    for i, t in enumerate(texts):
                        add("QR", t, pts[i] if pts is not None else None, scale, off, f"{dname}/{label}")
            if bd is not None:
                try:
                    ok, texts, types, pts = bd.detectAndDecodeWithType(arr)
                except Exception:  # noqa: BLE001
                    ok, texts, types, pts = False, [], [], None
                if ok:
                    for i, t in enumerate(texts):
                        if t:
                            add(str(types[i]) if types is not None and i < len(types) else "barcode", t,
                                pts[i] if pts is not None else None, scale, off, f"barcode/{label}")
    try:
        from pyzbar import pyzbar  # type: ignore
        for label, view, scale, off in views[:2]:
            for sym in pyzbar.decode(view):
                pts = [(p.x, p.y) for p in sym.polygon]
                add(sym.type, sym.data.decode("utf-8", "ignore"), pts, scale, off, f"pyzbar/{label}")
    except Exception:  # noqa: BLE001
        pass
    for o in out:
        o.update(interpret(o["raw"], o["type"]))
        o["display"] = o.pop("redacted", None) or o["raw"]
        if o.get("secret"):
            o["raw"] = o["display"]
    return {"codes": out, "notes": notes}


def _tlv(s: str) -> dict[str, str]:
    out, i = {}, 0
    while i + 4 <= len(s):
        tag, ln = s[i:i + 2], s[i + 2:i + 4]
        if not ln.isdigit():
            break
        n = int(ln)
        out[tag] = s[i + 4:i + 4 + n]
        i += 4 + n
    return out


def _ean_ok(code: str) -> bool:
    if not re.fullmatch(r"\d{8}|\d{12,14}", code):
        return False
    digits = [int(c) for c in code]
    check = digits.pop()
    # GTIN: weights 3,1,3,1... starting from the digit just left of the check digit
    total = sum(d * (3 if (len(digits) - i) % 2 == 1 else 1) for i, d in enumerate(digits))
    return (10 - total % 10) % 10 == check


def interpret(data: str, kind: str = "") -> dict:
    """Classify a decoded payload and pull out location-relevant fields."""
    d = data.strip()
    low = d.lower()
    if re.match(r"^https?://", low) or re.match(r"^www\.", low):
        u = urlparse(d if "://" in d else "http://" + d)
        host = (u.hostname or "").lower()
        res = {"kind": "url", "domain": host, "tld": "." + host.rsplit(".", 1)[-1] if "." in host else ""}
        qs = parse_qs(u.query)
        for key in ("q", "query", "place", "address", "ll", "center", "loc"):
            if key in qs:
                res.setdefault("params", {})[key] = qs[key][0][:200]
        if any(k in host for k in ("maps.google", "goo.gl", "maps.app.goo.gl", "maps.apple", "openstreetmap",
                                   "waze", "amap", "map.baidu", "map.naver", "kakaomap", "2gis")):
            res["note"] = "map link: open it - it may give the exact place"
        return res
    if low.startswith("upi://"):
        q = parse_qs(urlparse(d).query)
        return {"kind": "upi-payment", "country": "IN", "payee_vpa_domain": (q.get("pa", [""])[0].split("@")[-1]),
                "payee_name": unquote(q.get("pn", [""])[0])[:80], "note": "UPI payment QR (India); payee name is "
                "usually the shop"}
    if low.startswith("wifi:"):
        ssid = re.search(r"(?:^|;)S:((?:\\;|[^;])*)", d[5:])
        red = re.sub(r"(?i)((?:^WIFI:|;)P:)((?:\\;|[^;])*)", r"\1<redacted>", d)
        return {"kind": "wifi", "ssid": ssid.group(1).replace("\\;", ";") if ssid else "", "secret": True,
                "redacted": red, "note": "Wi-Fi SSID: venue name often; searchable on WiGLE (user key)"}
    if low.startswith("geo:"):
        m = re.match(r"geo:(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", low)
        if m:
            return {"kind": "geo-uri", "lat": float(m.group(1)), "lon": float(m.group(2))}
    if low.startswith(("begin:vcard", "mecard:")):
        fields = {}
        for key, pat in (("org", r"(?:^|\n)ORG[^:]*:(.+)"), ("adr", r"(?:^|\n)ADR[^:]*:(.+)"),
                         ("tel", r"(?:^|\n)TEL[^:]*:(.+)"), ("url", r"(?:^|\n)URL[^:]*:(.+)"),
                         ("mecard_adr", r"ADR:([^;]+)"), ("mecard_url", r"URL:([^;]+)")):
            m = re.search(pat, d, re.I)
            if m:
                fields[key] = m.group(1).strip()[:200]
        red = re.sub(r"(?im)^(N|FN|NICKNAME)([^:]*):.*$", r"\1\2:<redacted>", d)            # vCard lines
        red = re.sub(r"(?i)((?:^MECARD:|;)(?:N|NICKNAME|SOUND):)([^;]*)", r"\1<redacted>", red)  # MECARD fields
        red = re.sub(r"(?i)([\w.+-]+)@((?:[\w-]+\.)+[a-z]{2,24})", r"<redacted>@\2", red)       # keep the domain
        return {"kind": "contact-card", **fields, "secret": True, "redacted": red,
                "note": "contact card: ORG/ADR/URL locate the business; personal names redacted"}
    if d.startswith("SPC\n") or d.startswith("SPC\r\n"):
        lines = d.splitlines()
        iban = lines[3] if len(lines) > 3 else ""
        return {"kind": "swiss-qr-bill", "country": iban[:2] or "CH/LI",
                "creditor_lines": [x for x in lines[4:11] if x][:6], "secret": True,
                "redacted": f"SPC ... IBAN {iban[:4]}**** ...",
                "note": "Swiss QR-bill: creditor name/address = the business (CH/LI)"}
    if d.startswith("BCD\n") or d.startswith("BCD\r\n"):
        lines = d.splitlines()
        iban = lines[6] if len(lines) > 6 else ""
        return {"kind": "epc-sepa-transfer", "beneficiary": lines[5] if len(lines) > 5 else "",
                "iban_country": iban[:2], "secret": True, "redacted": f"BCD ... {lines[5] if len(lines) > 5 else ''} "
                f"IBAN {iban[:4]}****", "note": "EPC/SEPA QR: IBAN country = bank country (EU/EEA)"}
    if d.startswith("000201"):
        t = _tlv(d)
        res = {"kind": "emv-payment", "merchant_name": t.get("59", ""), "merchant_city": t.get("60", ""),
               "country": t.get("58", ""), "postal_code": t.get("61", ""), "mcc": t.get("52", ""),
               "currency_numeric": t.get("53", "")}
        for tag in [f"{n:02d}" for n in range(26, 52)]:
            if tag in t:
                sub = _tlv(t[tag])
                guid = (sub.get("00") or "").lower()
                for k, (scheme, cc) in EMV_NETWORKS.items():
                    if guid.startswith(k):
                        res["scheme"], res["scheme_country"] = scheme, cc
        if "64" in t:
            alt = _tlv(t["64"])
            if alt.get("01"):
                res["merchant_name_local"] = alt["01"]
            if alt.get("02"):
                res["merchant_city_local"] = alt["02"]
        res["note"] = "EMVCo merchant QR: merchant NAME + CITY + COUNTRY are printed in the code"
        return res
    if re.fullmatch(r"\d{8}|\d{12,14}", d):
        from . import knowledge
        valid = _ean_ok(d)
        g = knowledge.gs1_lookup(d) if valid else None
        return {"kind": "gtin", "valid_checksum": valid, "gs1": g,
                "note": "GS1 prefix = where the barcode was registered (brand owner), not where it was sold"}
    if re.match(r"^(alipays?://|https://qr\.alipay\.com)", low):
        return {"kind": "alipay", "country": "CN (Alipay)"}
    if low.startswith("wxp://"):
        return {"kind": "wechat-pay", "country": "CN (WeChat Pay)"}
    return {"kind": "text"}
