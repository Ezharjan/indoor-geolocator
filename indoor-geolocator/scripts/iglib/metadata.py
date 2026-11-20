"""Everything the file itself says: EXIF (incl. GPS and time offset), XMP, IPTC, ICC profile, JPEG
structure and quality, PNG text chunks, embedded thumbnail, C2PA / AI-generation markers, filename
patterns and social-platform fingerprints. Pillow + standard library; uses exiftool when installed.

Metadata is a HYPOTHESIS: it can be stripped, edited or spoofed. The image content wins on conflict.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import ExifTags, Image

NS = {
    "http://ns.adobe.com/xap/1.0/": "xmp", "http://purl.org/dc/elements/1.1/": "dc",
    "http://ns.adobe.com/photoshop/1.0/": "photoshop", "http://ns.adobe.com/exif/1.0/": "exif",
    "http://ns.adobe.com/tiff/1.0/": "tiff", "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/": "Iptc4xmpCore",
    "http://iptc.org/std/Iptc4xmpExt/2008-02-29/": "Iptc4xmpExt", "http://ns.adobe.com/xap/1.0/mm/": "xmpMM",
    "http://ns.adobe.com/xap/1.0/sType/ResourceEvent#": "stEvt", "http://ns.google.com/photos/1.0/panorama/": "GPano",
    "http://ns.adobe.com/lightroom/1.0/": "lr", "http://ns.adobe.com/camera-raw-settings/1.0/": "crs",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf", "http://ns.apple.com/faceinfo/1.0/": "apple-fi",
    "http://ns.google.com/photos/1.0/camera/": "GCamera", "http://cipa.jp/exif/1.0/": "exifEX",
    "http://ns.adobe.com/xmp/1.0/DynamicMedia/": "xmpDM", "http://www.digikam.org/ns/1.0/": "digiKam",
    "http://ns.microsoft.com/photo/1.0/": "MicrosoftPhoto", "http://ns.adobe.com/xap/1.0/rights/": "xmpRights",
}
AI_WORDS = ["trainedAlgorithmicMedia", "compositeWithTrainedAlgorithmicMedia", "algorithmicMedia", "c2pa",
            "Firefly", "DALL-E", "DALL·E", "Midjourney", "Stable Diffusion", "ComfyUI", "AUTOMATIC1111", "NovelAI",
            "Imagen", "Gemini", "GPT-4o", "Generative Fill", "Leonardo.Ai", "Ideogram", "Flux", "sdxl"]
EDIT_WORDS = ["Photoshop", "Lightroom", "GIMP", "Snapseed", "Picsart", "Meitu", "Canva", "FaceApp", "VSCO",
              "Facetune", "Affinity", "Pixelmator", "Luminar", "Capture One", "darktable", "Paint.NET", "Photopea"]
FILENAME_PATTERNS = [
    (r"^WhatsApp Image (\d{4})-(\d{2})-(\d{2}) at (\d{1,2})\.(\d{2})\.(\d{2})", "WhatsApp (received/saved)"),
    (r"^IMG-(\d{4})(\d{2})(\d{2})-WA\d+", "WhatsApp (Android)"),
    (r"^photo_(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})", "Telegram"),
    (r"^signal-(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})", "Signal"),
    (r"^PXL_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", "Google Pixel camera (UTC time in name)"),
    (r"^Screenshot_(\d{4})(\d{2})(\d{2})[-_](\d{2})(\d{2})(\d{2})", "Android screenshot"),
    (r"^Screenshot[ _](\d{4})-(\d{2})-(\d{2})[ _a-z]+(\d{1,2})[.:](\d{2})[.:](\d{2})", "Desktop/phone screenshot"),
    (r"^Screen Shot (\d{4})-(\d{2})-(\d{2}) at (\d{1,2})\.(\d{2})\.(\d{2})", "macOS screenshot (pre-2020)"),
    (r"^Bildschirmfoto (\d{4})-(\d{2})-(\d{2}) um (\d{1,2})\.(\d{2})\.(\d{2})", "macOS screenshot, German UI"),
    (r"^Captura de pantalla (\d{4})-(\d{2})-(\d{2})", "screenshot, Spanish UI"),
    (r"^Capture d.écran (\d{4})-(\d{2})-(\d{2})", "screenshot, French UI"),
    (r"^スクリーンショット (\d{4})-(\d{2})-(\d{2})", "screenshot, Japanese UI"),
    (r"^(?:截屏|屏幕截图)", "screenshot, Chinese UI"),
    (r"^IMG_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", "Android camera (Xiaomi/Huawei/OnePlus style)"),
    (r"^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", "Samsung camera"),
    (r"^IMG_\d{4}\b", "iPhone/Canon style counter"), (r"^DSC_\d{4}", "Nikon/Sony camera"),
    (r"^DSCF\d{4}", "Fujifilm camera"), (r"^_MG_\d{4}|^_DSC\d{4}", "Canon/Sony camera (Adobe RGB)"),
    (r"^P\d{7}", "Olympus/Panasonic camera"), (r"^GOPR\d{4}|^GX\d{6}", "GoPro"),
    (r"^DJI_\d{4}", "DJI drone/camera"), (r"^FB_IMG_\d+", "Facebook app save"),
    (r"^received_\d+", "Facebook Messenger"), (r"^MicrosoftTeams-image", "Microsoft Teams"),
    (r"^image\d*\.(?:png|jpe?g)$", "generic paste/upload name (Discord, clipboard, web)"),
    (r"^Snapchat-\d+", "Snapchat"), (r"^mmexport\d+", "WeChat export"), (r"^wx_camera_\d+", "WeChat camera"),
    (r"^Image_\d{8}", "LINE / web download"), (r"^unknown(?:\s*\(\d+\))?\.", "Discord/web download"),
]


def _ratio(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError, ZeroDivisionError):
        try:
            return float(v.numerator) / float(v.denominator)
        except Exception:  # noqa: BLE001
            return None


def _deg(v, ref) -> float | None:
    """EXIF degrees/minutes/seconds (or a single decimal value) + N/S/E/W reference -> signed degrees."""
    try:
        parts = [_ratio(x) for x in v] if isinstance(v, (tuple, list)) else [_ratio(v)]
        parts = (parts + [0.0, 0.0])[:3]
        if any(p is None for p in parts):
            return None
        d, m, s = parts
        val = abs(d) + abs(m) / 60 + abs(s) / 3600
        r = (ref.decode("ascii", "ignore") if isinstance(ref, bytes) else str(ref or "")).strip("\x00 ").upper()
        if r.startswith(("S", "W")) or (d < 0 and not r):
            val = -val
        return val
    except Exception:  # noqa: BLE001
        return None


def _clean(v):
    if isinstance(v, bytes):
        txt = v.decode("utf-8", "ignore").strip("\x00 ").strip()
        if v.startswith(b"ASCII\x00\x00\x00"):
            txt = v[8:].decode("ascii", "ignore").strip("\x00 ")
        elif v.startswith(b"UNICODE\x00"):
            txt = v[8:].decode("utf-16", "ignore").strip("\x00 ")
        return txt if txt and all(ch.isprintable() or ch in "\n\t" for ch in txt) else f"<{len(v)} bytes>"
    if isinstance(v, tuple):
        return [_clean(x) for x in v]
    r = _ratio(v) if not isinstance(v, (int, str)) else None
    if r is not None and not isinstance(v, (int, str)):
        return round(r, 6)
    if isinstance(v, str):
        return v.strip("\x00 ").strip()
    return v


def _exif(im: Image.Image) -> tuple[dict, dict | None, bytes | None]:
    out, gps = {}, None
    try:
        ex = im.getexif()
    except Exception:  # noqa: BLE001
        return out, None, None
    for k, v in ex.items():
        name = ExifTags.TAGS.get(k, f"0x{k:04x}")
        if name in ("ExifOffset", "GPSInfo", "MakerNote", "PrintImageMatching"):
            continue
        out[name] = _clean(v)
    for ifd_id in (0x8769, 0xA005):  # Exif IFD, Interop
        try:
            for k, v in ex.get_ifd(ifd_id).items():
                name = ExifTags.TAGS.get(k, f"0x{k:04x}")
                if name in ("MakerNote", "ComponentsConfiguration"):
                    continue
                out[name] = _clean(v)
        except Exception:  # noqa: BLE001
            pass
    for key in ("XPComment", "XPKeywords", "XPTitle", "XPSubject", "XPAuthor"):
        if key in out and isinstance(out[key], (list, str)):
            try:
                raw = bytes(out[key]) if isinstance(out[key], list) else None
                if raw:
                    out[key] = raw.decode("utf-16-le", "ignore").strip("\x00")
            except Exception:  # noqa: BLE001
                pass
    try:
        g = ex.get_ifd(0x8825)
    except Exception:  # noqa: BLE001
        g = {}
    if g:
        gt = {ExifTags.GPSTAGS.get(k, k): v for k, v in g.items()}
        lat = _deg(gt.get("GPSLatitude"), gt.get("GPSLatitudeRef", "N")) if gt.get("GPSLatitude") else None
        lon = _deg(gt.get("GPSLongitude"), gt.get("GPSLongitudeRef", "E")) if gt.get("GPSLongitude") else None
        gps = {"raw": {str(k): _clean(v) for k, v in gt.items() if k not in ("GPSLatitude", "GPSLongitude")}}
        if lat is not None and lon is not None:
            gps["lat"], gps["lon"] = round(lat, 7), round(lon, 7)
            gps["valid"] = not (abs(lat) < 1e-6 and abs(lon) < 1e-6)
        if gt.get("GPSAltitude") is not None:
            alt = _ratio(gt["GPSAltitude"])
            ref = gt.get("GPSAltitudeRef", 0)
            ref = ref[0] if isinstance(ref, (bytes, tuple)) and ref else ref
            gps["alt_m"] = -alt if ref == 1 and alt else alt
        if gt.get("GPSImgDirection") is not None:
            gps["img_direction_deg"] = _ratio(gt["GPSImgDirection"])
            gps["img_direction_ref"] = str(gt.get("GPSImgDirectionRef", "")).strip("\x00")
        if gt.get("GPSDateStamp") and gt.get("GPSTimeStamp"):
            try:
                h, m, s = (_ratio(x) for x in gt["GPSTimeStamp"])
                gps["utc"] = f"{str(gt['GPSDateStamp']).replace(':', '-')}T{int(h):02d}:{int(m):02d}:{int(s):02d}Z"
            except Exception:  # noqa: BLE001
                pass
        if gt.get("GPSHPositioningError") is not None:
            gps["h_error_m"] = _ratio(gt["GPSHPositioningError"])
    return out, gps, None


def _segments(data: bytes) -> list[tuple[int, bytes]]:
    """JPEG marker segments up to SOS: [(marker, payload)]."""
    segs, i = [], 2
    if not data.startswith(b"\xff\xd8"):
        return segs
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        ln = int.from_bytes(data[i + 2:i + 4], "big")
        segs.append((marker, data[i + 4:i + 2 + ln]))
        if marker == 0xDA:
            break
        i += 2 + ln
    return segs


STD_LUMA = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
            14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
            49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]


def _jpeg_quality(im: Image.Image) -> int | None:
    q = getattr(im, "quantization", None)
    if not q or 0 not in q:
        return None
    actual = list(q[0])
    best, best_q = None, None
    for quality in range(1, 101):
        scale = 5000 / quality if quality < 50 else 200 - 2 * quality
        table = [min(255, max(1, (v * scale + 50) // 100)) for v in STD_LUMA]
        diff = sum(abs(a - b) for a, b in zip(sorted(actual), sorted(table)))
        if best is None or diff < best:
            best, best_q = diff, quality
    return best_q


def _xmp(data: bytes) -> dict:
    m = re.search(rb"<x:xmpmeta.*?</x:xmpmeta>", data, re.S)
    if not m:
        m = re.search(rb"<rdf:RDF.*?</rdf:RDF>", data, re.S)
    if not m:
        return {}
    raw = m.group(0)
    fields: dict[str, list[str]] = {}
    try:
        root = ET.fromstring(raw)

        def q(tag: str) -> str:
            if tag.startswith("{"):
                uri, local = tag[1:].split("}", 1)
                return f"{NS.get(uri, uri.rstrip('/#').rsplit('/', 1)[-1])}:{local}"
            return tag

        for el in root.iter():
            for k, v in el.attrib.items():
                key = q(k)
                if key.startswith(("rdf:", "xmlns")) or key == "x:xmptk":
                    continue
                fields.setdefault(key, []).append(v)
            name = q(el.tag)
            text = (el.text or "").strip()
            if text and not name.startswith(("rdf:", "x:")):
                fields.setdefault(name, []).append(text)
            elif text and name == "rdf:li":
                parent_key = getattr(el, "_parent_key", None)
                fields.setdefault(parent_key or "rdf:li", []).append(text)
        # rdf:li values belong to the nearest named ancestor (Bag/Seq/Alt containers)
        for parent in root.iter():
            pname = q(parent.tag)
            if pname.startswith(("rdf:", "x:")):
                continue
            for li in parent.iter("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li"):
                t = (li.text or "").strip()
                if t:
                    fields.setdefault(pname, [])
                    if t not in fields[pname]:
                        fields[pname].append(t)
        fields.pop("rdf:li", None)
    except ET.ParseError:
        for k, v in re.findall(rb'([A-Za-z0-9]+:[A-Za-z0-9]+)="([^"]*)"', raw):
            fields.setdefault(k.decode(), []).append(v.decode("utf-8", "ignore"))
    flat = {k: (v[0] if len(v) == 1 else v) for k, v in fields.items()}
    return {"fields": flat, "bytes": len(raw), "raw_text": raw.decode("utf-8", "ignore")[:20000]}


def _iptc(im: Image.Image) -> dict:
    try:
        from PIL import IptcImagePlugin
        info = IptcImagePlugin.getiptcinfo(im) or {}
    except Exception:  # noqa: BLE001
        return {}
    names = {(2, 5): "ObjectName", (2, 25): "Keywords", (2, 40): "SpecialInstructions", (2, 55): "DateCreated",
             (2, 60): "TimeCreated", (2, 80): "Byline", (2, 85): "BylineTitle", (2, 90): "City",
             (2, 92): "Sublocation", (2, 95): "ProvinceState", (2, 100): "CountryCode", (2, 101): "CountryName",
             (2, 103): "TransmissionReference", (2, 105): "Headline", (2, 110): "Credit", (2, 115): "Source",
             (2, 116): "Copyright", (2, 120): "Caption", (2, 122): "Writer"}
    out = {}
    for k, v in info.items():
        key = names.get(k, f"{k[0]}:{k[1]}")
        vals = v if isinstance(v, list) else [v]
        vals = [x.decode("utf-8", "ignore") if isinstance(x, bytes) else str(x) for x in vals]
        out[key] = vals[0] if len(vals) == 1 else vals
    return out


def _icc_desc(im: Image.Image) -> str | None:
    icc = im.info.get("icc_profile")
    if not icc:
        return None
    try:
        from PIL import ImageCms
        return ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc))).strip()
    except Exception:  # noqa: BLE001
        m = re.search(rb"desc.{8}([\x20-\x7e]{4,64})", icc)
        return m.group(1).decode() if m else f"<{len(icc)} bytes>"


def _thumbnail(data: bytes, segs: list[tuple[int, bytes]]) -> bytes | None:
    for marker, payload in segs:
        if marker == 0xE1 and payload.startswith(b"Exif\x00\x00"):
            body = payload[6:]
            s = body.find(b"\xff\xd8", 8)
            if s != -1:
                e = body.find(b"\xff\xd9", s)
                if e != -1:
                    return body[s:e + 2]
    return None


def _compare_thumb(main: Image.Image, thumb_bytes: bytes) -> dict:
    try:
        from PIL import ImageOps
        th = Image.open(io.BytesIO(thumb_bytes))
        th = ImageOps.exif_transpose(th).convert("L")
        mi = ImageOps.exif_transpose(main).convert("L")
        ar_m, ar_t = mi.width / mi.height, th.width / th.height
        a = list(mi.resize((24, 24)).tobytes())
        b = list(th.resize((24, 24)).tobytes())
        mad = sum(abs(x - y) for x, y in zip(a, b)) / len(a)
        return {"size": [th.width, th.height], "aspect_main": round(ar_m, 4), "aspect_thumb": round(ar_t, 4),
                "mean_abs_diff": round(mad, 1),
                "differs": abs(ar_m - ar_t) / ar_m > 0.03 or mad > 28}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def _filename(name: str) -> dict:
    for pat, label in FILENAME_PATTERNS:
        m = re.match(pat, name, re.I)
        if m:
            out = {"pattern": pat, "hint": label}
            g = [x for x in m.groups() if x is not None]
            if len(g) >= 3:
                try:
                    parts = [int(x) for x in g[:6]] + [0] * (6 - len(g[:6]))
                    out["datetime_in_name"] = dt.datetime(*parts).isoformat()
                except ValueError:
                    pass
            return out
    return {}


def _offset_zones(local_iso: str | None, offset: str | None) -> list[str]:
    """Time zones (with country codes) whose UTC offset equals EXIF OffsetTimeOriginal at that date."""
    if not offset or not re.fullmatch(r"[+-]\d{2}:\d{2}", offset):
        return []
    try:
        from zoneinfo import ZoneInfo, available_timezones
    except ImportError:
        return []
    sign = 1 if offset[0] == "+" else -1
    target = sign * (int(offset[1:3]) * 60 + int(offset[4:6]))
    try:
        when = dt.datetime.fromisoformat(local_iso) if local_iso else dt.datetime.now()
    except ValueError:
        when = dt.datetime.now()
    cc = _zone_countries()
    hits = []
    for z in sorted(available_timezones()):
        if z.startswith(("Etc/", "SystemV/", "US/", "posix", "right")) or "/" not in z:
            continue
        try:
            off = ZoneInfo(z).utcoffset(when.replace(tzinfo=None))
        except Exception:  # noqa: BLE001
            continue
        if off is not None and int(off.total_seconds() // 60) == target:
            hits.append(f"{z}" + (f" ({','.join(cc[z])})" if z in cc else ""))
    return hits


def _zone_countries() -> dict[str, list[str]]:
    for p in ("/usr/share/zoneinfo/zone1970.tab", "/usr/share/zoneinfo/zone.tab"):
        try:
            out = {}
            for line in Path(p).read_text(encoding="utf-8").splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    out[parts[2]] = parts[0].split(",")
            return out
        except OSError:
            continue
    try:  # the tzdata package ships zone1970.tab too
        import importlib.resources as ir
        txt = ir.files("tzdata").joinpath("zoneinfo/zone1970.tab").read_text(encoding="utf-8")
        return {p[2]: p[0].split(",") for p in (ln.split("\t") for ln in txt.splitlines() if ln and ln[0] != "#")
                if len(p) >= 3}
    except Exception:  # noqa: BLE001
        return {}


C2PA_SIGNERS = ["Adobe", "OpenAI", "Google", "Microsoft", "Anthropic", "Meta", "TikTok", "LinkedIn", "Truepic",
                "Leica", "Sony", "Nikon", "Canon", "Fujifilm", "Samsung", "Qualcomm", "BBC", "Midjourney", "Stability",
                "Shutterstock", "Getty", "Amazon", "Nvidia", "Runway", "Pixel"]


def _c2pa_info(blob: bytes) -> dict:
    """A light reading of a C2PA manifest (no signature check): who produced it, which actions it records,
    and whether it declares AI generation (IPTC digitalSourceType trainedAlgorithmicMedia)."""
    txt = " ".join(t.decode("latin-1") for t in re.findall(rb"[\x20-\x7e]{4,}", blob[:400000]))
    signers = sorted({s for s in C2PA_SIGNERS if re.search(rf"\b{s}", txt)})
    actions = sorted(set(re.findall(r"c2pa\.(created|opened|edited|converted|placed|cropped|resized|"
                                    r"color_adjustments|filtered|drawing|published|transcoded|repackaged)", txt)))
    out = {"signers": signers, "actions": actions,
           "ai_generated": "trainedAlgorithmicMedia" in txt and "compositeWithTrainedAlgorithmicMedia" not in txt,
           "ai_composite": "compositeWithTrainedAlgorithmicMedia" in txt}
    m = re.search(r"description\S{0,3}?([A-Z][\w'’-]*(?: [\w,'’()-]+){3,60}\.?)", txt)
    if m:
        out["statement"] = m.group(1).strip()[:240]
    return out


def _exiftool(path: Path) -> dict | None:
    exe = shutil.which("exiftool")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-j", "-G1", "-a", "-u", "-n", str(path)], capture_output=True, timeout=60)
        if r.returncode == 0:
            return json.loads(r.stdout.decode("utf-8", "ignore"))[0]
    except Exception:  # noqa: BLE001
        return None
    return None


def extract(path: Path) -> dict:
    path = Path(path)
    data = path.read_bytes()
    meta: dict = {"file": {"name": path.name, "bytes": len(data)}}
    try:
        im = Image.open(path)
    except Exception as e:  # noqa: BLE001
        meta["error"] = f"not readable as an image: {e}"
        return meta
    meta["file"].update({"format": im.format, "mode": im.mode, "size": list(im.size),
                         "frames": getattr(im, "n_frames", 1)})
    exif, gps, _ = _exif(im)
    meta["exif"] = exif
    meta["gps"] = gps
    meta["xmp"] = _xmp(data)
    meta["iptc"] = _iptc(im)
    meta["icc_profile"] = _icc_desc(im)
    container: dict = {}
    if im.format == "JPEG":
        segs = _segments(data)
        markers = []
        for marker, payload in segs:
            tag = f"APP{marker - 0xE0}" if 0xE0 <= marker <= 0xEF else {0xDB: "DQT", 0xC0: "SOF0", 0xC2: "SOF2",
                                                                       0xC4: "DHT", 0xDA: "SOS", 0xFE: "COM",
                                                                       0xDD: "DRI"}.get(marker, f"0x{marker:02X}")
            ident = payload[:12].split(b"\x00")[0].decode("latin-1", "ignore") if 0xE0 <= marker <= 0xEF else ""
            markers.append(f"{tag}:{ident}" if ident else tag)
            if marker == 0xFE:
                container.setdefault("comments", []).append(payload.decode("utf-8", "ignore")[:500])
        container["markers"] = markers
        container["progressive"] = any(m.startswith("SOF2") for m in markers)
        container["quality_estimate"] = _jpeg_quality(im)
        try:
            from PIL import JpegImagePlugin
            container["subsampling"] = {0: "4:4:4", 1: "4:2:2", 2: "4:2:0"}.get(
                JpegImagePlugin.get_sampling(im), "unknown")
        except Exception:  # noqa: BLE001
            pass
        container["c2pa"] = any(m.startswith("APP11") for m in markers) and (b"c2pa" in data or b"jumb" in data)
        if container["c2pa"]:
            container["c2pa_info"] = _c2pa_info(b"".join(pl for mk, pl in segs if mk == 0xEB))
        th = _thumbnail(data, segs)
        if th:
            meta["thumbnail"] = _compare_thumb(im, th)
            meta["_thumbnail_bytes"] = th
    elif im.format == "PNG":
        texts = {k: (v if isinstance(v, str) else str(v))[:4000] for k, v in im.info.items()
                 if isinstance(v, (str, bytes)) and k not in ("icc_profile", "exif")}
        container["png_text"] = texts
        container["c2pa"] = b"caBX" in data or b"c2pa" in data
    else:
        container["c2pa"] = b"c2pa" in data
    if container.get("c2pa") and "c2pa_info" not in container:
        container["c2pa_info"] = _c2pa_info(data)
    meta["container"] = container
    meta["filename"] = _filename(path.name)
    when = exif.get("DateTimeOriginal") or exif.get("DateTimeDigitized") or exif.get("DateTime")
    local_iso = None
    if isinstance(when, str) and re.match(r"\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}", when):
        local_iso = when[:10].replace(":", "-") + "T" + when[11:19]
    offset = exif.get("OffsetTimeOriginal") or exif.get("OffsetTime")
    meta["time"] = {"local": local_iso, "offset": offset, "zones_with_offset": _offset_zones(local_iso, offset)}
    blob = " ".join([json.dumps(exif, ensure_ascii=False, default=str), meta["xmp"].get("raw_text", ""),
                     json.dumps(container.get("png_text", {}), ensure_ascii=False)])
    meta["ai_markers"] = sorted({w for w in AI_WORDS if w.lower() in blob.lower()})
    if "parameters" in container.get("png_text", {}):
        meta["ai_markers"].append("PNG 'parameters' chunk (Stable Diffusion style prompt)")
    meta["edit_markers"] = sorted({w for w in EDIT_WORDS if w.lower() in blob.lower()})
    et = _exiftool(path)
    if et:
        meta["exiftool"] = et
    meta["flags"] = flags(meta)
    return meta


def flags(meta: dict) -> list[str]:
    """Notable findings, each with what it means for geolocation."""
    out = []
    ex, gps, xmp = meta.get("exif") or {}, meta.get("gps") or {}, (meta.get("xmp") or {}).get("fields", {})
    if gps.get("lat") is not None:
        if gps.get("valid"):
            out.append(f"GPS {gps['lat']}, {gps['lon']} embedded - strong but editable: verify against the content")
        else:
            out.append("GPS fields present but 0,0 - placeholder, not a position")
    if not ex:
        out.append("no EXIF - stripped (messaging/social upload, screenshot, export) or synthetic; absence proves nothing")
    if ex.get("Make") or ex.get("Model"):
        out.append(f"camera: {ex.get('Make', '')} {ex.get('Model', '')}".strip() +
                   " (device market can hint at region, weakly)")
    t = meta.get("time") or {}
    if t.get("local"):
        out.append(f"capture time (camera clock, local): {t['local']}" + (f" offset {t['offset']}" if t.get("offset") else ""))
    if t.get("zones_with_offset"):
        z = t["zones_with_offset"]
        out.append(f"UTC offset {t['offset']} at that date matches {len(z)} zones, e.g. {', '.join(z[:6])}")
    if ex.get("Software"):
        out.append(f"software: {ex['Software']}")
    if ex.get("DateTime") and ex.get("DateTimeOriginal") and ex["DateTime"] != ex["DateTimeOriginal"]:
        out.append(f"modified {ex['DateTime']} after capture {ex['DateTimeOriginal']} - edited/exported later")
    for key in ("photoshop:City", "photoshop:State", "photoshop:Country", "Iptc4xmpCore:Location",
                "Iptc4xmpCore:CountryCode", "exif:GPSLatitude", "dc:title", "dc:description", "dc:subject"):
        if key in xmp:
            out.append(f"XMP {key} = {str(xmp[key])[:120]}")
    for k in ("City", "Sublocation", "ProvinceState", "CountryName", "CountryCode", "Caption", "Keywords",
              "Headline", "ObjectName"):
        if k in (meta.get("iptc") or {}):
            out.append(f"IPTC {k} = {str(meta['iptc'][k])[:120]}")
    if "FBMD" in str((meta.get("iptc") or {}).get("SpecialInstructions", "")):
        out.append("IPTC FBMD marker - the file passed through Facebook/Instagram")
    if any(k.startswith("GPano:") for k in xmp):
        out.append("GPano XMP - a 360 photosphere: compare with map photospheres")
    if meta.get("ai_markers"):
        out.append(f"AI/provenance markers: {', '.join(meta['ai_markers'])} - check whether the scene is synthetic")
    if meta.get("edit_markers"):
        out.append(f"editing software traces: {', '.join(meta['edit_markers'])}")
    c = meta.get("container") or {}
    if c.get("c2pa"):
        ci = c.get("c2pa_info") or {}
        bits = []
        if ci.get("signers"):
            bits.append("issued by " + "/".join(ci["signers"]))
        if ci.get("actions"):
            bits.append("actions " + ", ".join(ci["actions"]))
        if ci.get("statement"):
            bits.append(f"'{ci['statement'][:140]}'")
        if ci.get("ai_generated"):
            bits.append("DECLARES AI GENERATION (trainedAlgorithmicMedia): the scene may not exist")
        elif ci.get("ai_composite"):
            bits.append("declares AI-assisted compositing: parts of the scene may be synthetic")
        out.append("C2PA content credentials present" + (f" ({'; '.join(bits)})" if bits else "") +
                   " - a re-saved or relayed file can carry the relayer's credentials; verify with a C2PA verifier")
    if c.get("quality_estimate"):
        out.append(f"JPEG quality ~{c['quality_estimate']}" + (", progressive" if c.get("progressive") else ""))
    th = meta.get("thumbnail") or {}
    if th.get("differs"):
        out.append("embedded EXIF thumbnail DIFFERS from the image (crop/edit after capture) - look at it: it may "
                   "show the original framing")
    fn = meta.get("filename") or {}
    if fn.get("hint"):
        out.append(f"filename pattern: {fn['hint']}" + (f", time in name {fn['datetime_in_name']}"
                                                         if fn.get("datetime_in_name") else ""))
    if meta.get("icc_profile"):
        out.append(f"ICC profile: {meta['icc_profile']}")
    w, h = (meta.get("file") or {}).get("size", [0, 0])
    if w and h and not ex and (w in (1080, 1440, 2048, 1200, 1600) or h in (1080, 1440, 2048, 1350)):
        out.append(f"{w}x{h} without EXIF fits social-media recompression sizes (weak)")
    return out
