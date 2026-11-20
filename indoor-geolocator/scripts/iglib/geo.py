"""Public geodata: geocoding and reverse geocoding (Nominatim, Photon fallback), OpenStreetMap Overpass
(mirrors tried in turn), Wikimedia Commons photos near a point or by text, Wikidata entities and SPARQL,
time zone at a point, historical weather (Open-Meteo), and offline geometry: solar position (NOAA
algorithm), great-circle bearing/distance and the qibla direction. All keyless; policies respected:
Nominatim <= 1 request/s with an identifying User-Agent; Overpass queries bounded by area/timeout.
"""
from __future__ import annotations

import datetime as dt
import math
import re

from .net import Http

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass.private.coffee/api/interpreter"]


def _nom_item(it: dict) -> dict:
    return {"name": it.get("name") or it.get("display_name", "").split(",")[0], "display": it.get("display_name"),
            "lat": float(it["lat"]), "lon": float(it["lon"]), "class": it.get("class") or it.get("category"),
            "type": it.get("type") or it.get("addresstype"), "osm": f"{it.get('osm_type')}/{it.get('osm_id')}",
            "address": it.get("address", {}), "bbox": [float(x) for x in it.get("boundingbox", [])] or None,
            "importance": it.get("importance"), "source": "nominatim"}


def _photon_item(f: dict) -> dict:
    p = f.get("properties", {})
    lon, lat = f["geometry"]["coordinates"][:2]
    parts = [p.get(k) for k in ("name", "housenumber", "street", "district", "city", "state", "postcode",
                                "country") if p.get(k)]
    ext = p.get("extent")
    return {"name": p.get("name") or (p.get("street") or ""), "display": ", ".join(str(x) for x in parts),
            "lat": float(lat), "lon": float(lon), "class": p.get("osm_key"), "type": p.get("osm_value"),
            "osm": f"{ {'N': 'node', 'W': 'way', 'R': 'relation'}.get(p.get('osm_type'), p.get('osm_type'))}/{p.get('osm_id')}",
            "address": {k: p[k] for k in ("housenumber", "street", "district", "city", "state", "postcode",
                                          "country", "countrycode") if k in p},
            "bbox": [ext[3], ext[1], ext[0], ext[2]] if ext and len(ext) == 4 else None, "source": "photon"}


def geocode(http: Http, query: str, country: str | None = None, limit: int = 8,
            near: tuple[float, float] | None = None) -> dict:
    params = {"q": query, "format": "jsonv2", "addressdetails": 1, "limit": limit, "extratags": 1}
    if country:
        params["countrycodes"] = country.lower()
    if near:
        lat, lon = near
        params["viewbox"] = f"{lon - 0.5},{lat + 0.5},{lon + 0.5},{lat - 0.5}"
    r = http.get("https://nominatim.openstreetmap.org/search", params)
    if r["ok"] and isinstance(r.get("data"), list):
        return {"ok": True, "service": "nominatim", "results": [_nom_item(x) for x in r["data"]]}
    p = {"q": query, "limit": limit}
    if near:
        p["lat"], p["lon"] = near
    r2 = http.get("https://photon.komoot.io/api/", p)
    if r2["ok"] and isinstance(r2.get("data"), dict):
        res = [_photon_item(f) for f in r2["data"].get("features", [])]
        if country:
            res = [x for x in res if (x["address"].get("countrycode") or "").lower() == country.lower()] or res
        return {"ok": True, "service": "photon (Nominatim unavailable: " + str(r.get("error")) + ")", "results": res}
    return {"ok": False, "service": "nominatim+photon", "error": f"nominatim: {r.get('error')}; photon: {r2.get('error')}",
            "results": []}


def reverse(http: Http, lat: float, lon: float, zoom: int = 18) -> dict:
    r = http.get("https://nominatim.openstreetmap.org/reverse",
                 {"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1, "zoom": zoom, "namedetails": 1})
    if r["ok"] and isinstance(r.get("data"), dict) and "lat" in r["data"]:
        return {"ok": True, "service": "nominatim", **_nom_item(r["data"])}
    r2 = http.get("https://photon.komoot.io/reverse", {"lat": lat, "lon": lon, "limit": 1})
    if r2["ok"] and r2.get("data", {}).get("features"):
        return {"ok": True, "service": "photon", **_photon_item(r2["data"]["features"][0])}
    return {"ok": False, "error": f"nominatim: {r.get('error')}; photon: {r2.get('error')}"}


def overpass(http: Http, ql: str, timeout: int = 60, deadline: float = 150.0) -> dict:
    """Try each mirror once (no retries: a failing mirror is skipped, not hammered) within an overall deadline."""
    import time
    errors, t0 = [], time.time()
    once = Http(cache_dir=http.cache_dir, timeout=timeout, retries=0)
    for url in OVERPASS:
        if time.time() - t0 > deadline:
            errors.append(f"{url.split('/')[2]}: skipped (overall deadline {deadline:.0f} s reached)")
            continue
        r = once.get(url, data=("data=" + _q(ql)).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"},
                     method="POST")
        if r["ok"] and isinstance(r.get("data"), dict):
            remark = r["data"].get("remark", "")
            out = {"ok": True, "server": url, "elements": r["data"].get("elements", [])}
            if remark:
                out["warning"] = f"server remark: {remark} (result may be incomplete)"
            return out
        errors.append(f"{url.split('/')[2]}: {r.get('error')}")
    return {"ok": False, "error": "; ".join(errors), "elements": []}


def _q(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(s)


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def build_poi_ql(tags: list[str], name: str | None, brand: str | None, area: dict, near: list[str] | None = None,
                 limit: int = 200) -> str:
    """area: {'bbox': [s,w,n,e]} or {'around': [lat, lon, radius_m]}."""
    if "bbox" in area:
        s, w, n, e = area["bbox"]
        scope = f"({s},{w},{n},{e})"
    else:
        lat, lon, r = area["around"]
        scope = f"(around:{int(r)},{lat},{lon})"
    sel = ""
    for t in tags:
        if "=" in t:
            k, v = t.split("=", 1)
            sel += f'["{_esc(k)}"="{_esc(v)}"]' if v != "*" else f'["{_esc(k)}"]'
        else:
            sel += f'["{_esc(t)}"]'
    if name:
        sel += f'["name"~"{_esc(name)}",i]'
    if brand:
        sel += f'["brand"~"{_esc(brand)}",i]'
    if not sel:
        raise ValueError("give at least one --tag, --name or --brand")
    lines = ["[out:json][timeout:55];"]
    prev = None
    for i, nt in enumerate(near or []):
        m = re.match(r"^(.+?)(?:@(\d+))?$", nt)
        tag, dist = m.group(1), int(m.group(2) or 150)
        k, _, v = tag.partition("=")
        f = f'["{_esc(k)}"="{_esc(v)}"]' if v and v != "*" else f'["{_esc(k)}"]'
        if prev is None:
            lines.append(f"nwr{f}{scope}->.n{i};")
        else:
            lines.append(f"nwr{f}(around.{prev}:{dist}){scope}->.n{i};")
        prev, last_dist = f".n{i}", dist
    if prev:
        lines.append(f"nwr{sel}(around{prev}:{last_dist}){scope};")
    else:
        lines.append(f"nwr{sel}{scope};")
    lines.append(f"out center tags {int(limit)};")
    return "\n".join(lines)


def elements_to_places(elements: list[dict]) -> list[dict]:
    out = []
    for el in elements:
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None:
            continue
        t = el.get("tags", {})
        addr = ", ".join(x for x in [" ".join(filter(None, [t.get("addr:housenumber"), t.get("addr:street")])),
                                     t.get("addr:city"), t.get("addr:postcode"), t.get("addr:country")] if x)
        out.append({"name": t.get("name") or t.get("brand") or "(unnamed)", "lat": lat, "lon": lon,
                    "osm": f"{el['type']}/{el['id']}", "address": addr,
                    "tags": {k: v for k, v in t.items() if k in ("tourism", "amenity", "shop", "brand", "operator",
                                                               "stars", "website", "contact:website", "phone",
                                                               "building:levels", "level", "wikidata", "wikipedia",
                                                               "opening_hours", "name:en", "branch")}})
    return out


def commons_geosearch(http: Http, lat: float, lon: float, radius: int = 500, limit: int = 30) -> dict:
    r = http.get("https://commons.wikimedia.org/w/api.php",
                 {"action": "query", "list": "geosearch", "gscoord": f"{lat}|{lon}", "gsradius": min(10000, radius),
                  "gsnamespace": 6, "gslimit": min(100, limit), "format": "json"})
    if not r["ok"]:
        return {"ok": False, "error": r.get("error"), "files": []}
    files = [{"title": g["title"], "lat": g["lat"], "lon": g["lon"], "dist_m": g.get("dist")}
             for g in r["data"].get("query", {}).get("geosearch", [])]
    return {"ok": True, "files": _commons_info(http, files)}


def commons_search(http: Http, text: str, limit: int = 30) -> dict:
    q = text if "filetype:" in text else f"{text} filetype:bitmap"      # photos, not scanned PDFs/DjVu
    r = http.get("https://commons.wikimedia.org/w/api.php",
                 {"action": "query", "list": "search", "srsearch": q, "srnamespace": 6, "srlimit": min(50, limit),
                  "format": "json"})
    if not r["ok"]:
        return {"ok": False, "error": r.get("error"), "files": []}
    files = [{"title": s["title"]} for s in r["data"].get("query", {}).get("search", [])]
    return {"ok": True, "files": _commons_info(http, files)}


def commons_category(http: Http, category: str, limit: int = 50) -> dict:
    cat = category if category.lower().startswith("category:") else f"Category:{category}"
    r = http.get("https://commons.wikimedia.org/w/api.php",
                 {"action": "query", "list": "categorymembers", "cmtitle": cat, "cmtype": "file",
                  "cmlimit": min(100, limit), "format": "json"})
    if not r["ok"]:
        return {"ok": False, "error": r.get("error"), "files": []}
    files = [{"title": m["title"]} for m in r["data"].get("query", {}).get("categorymembers", [])]
    return {"ok": True, "files": _commons_info(http, files)}


def _commons_info(http: Http, files: list[dict]) -> list[dict]:
    for i in range(0, len(files), 40):
        batch = files[i:i + 40]
        r = http.get("https://commons.wikimedia.org/w/api.php",
                     {"action": "query", "titles": "|".join(f["title"] for f in batch), "prop": "imageinfo|coordinates",
                      "iiprop": "url|extmetadata|size", "iiurlwidth": 640, "format": "json"})
        if not r["ok"]:
            continue
        pages = {p.get("title"): p for p in r["data"].get("query", {}).get("pages", {}).values()}
        for f in batch:
            p = pages.get(f["title"], {})
            ii = (p.get("imageinfo") or [{}])[0]
            em = ii.get("extmetadata", {})
            f["thumb"] = ii.get("thumburl")
            f["page"] = ii.get("descriptionurl")
            f["date"] = re.sub(r"<[^>]+>", "", em.get("DateTimeOriginal", {}).get("value", ""))[:40]
            f["description"] = re.sub(r"<[^>]+>", "", em.get("ImageDescription", {}).get("value", ""))[:200]
            f["author"] = re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))[:60]
            f["license"] = em.get("LicenseShortName", {}).get("value", "")
            if "lat" not in f and p.get("coordinates"):
                f["lat"], f["lon"] = p["coordinates"][0]["lat"], p["coordinates"][0]["lon"]
    return files


def wikidata_search(http: Http, text: str, lang: str = "en", limit: int = 8) -> dict:
    r = http.get("https://www.wikidata.org/w/api.php",
                 {"action": "wbsearchentities", "search": text, "language": lang, "uselang": lang, "limit": limit,
                  "format": "json", "type": "item"})
    if not r["ok"]:
        return {"ok": False, "error": r.get("error"), "results": []}
    return {"ok": True, "results": [{"qid": s["id"], "label": s.get("label"), "description": s.get("description")}
                                    for s in r["data"].get("search", [])]}


def wikidata_entity(http: Http, qid: str, lang: str = "en") -> dict:
    r = http.get("https://www.wikidata.org/w/api.php",
                 {"action": "wbgetentities", "ids": qid, "props": "labels|descriptions|claims|sitelinks",
                  "languages": f"{lang}|en", "format": "json"})
    if not r["ok"]:
        return {"ok": False, "error": r.get("error")}
    ent = r["data"].get("entities", {}).get(qid, {})
    claims = ent.get("claims", {})

    def vals(p):
        out = []
        for c in claims.get(p, []):
            v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(v, dict) and "id" in v:
                out.append(v["id"])
            elif isinstance(v, dict) and "latitude" in v:
                out.append([v["latitude"], v["longitude"]])
            elif isinstance(v, dict) and "text" in v:
                out.append(v["text"])
            elif v is not None:
                out.append(v)
        return out

    res = {"ok": True, "qid": qid, "label": (ent.get("labels", {}).get(lang) or ent.get("labels", {}).get("en", {})).get("value"),
           "description": (ent.get("descriptions", {}).get(lang) or ent.get("descriptions", {}).get("en", {})).get("value"),
           "coords": (vals("P625") or [None])[0], "instance_of": vals("P31"), "country": vals("P17"),
           "located_in": vals("P131"), "address": vals("P6375"), "postal_code": vals("P281"),
           "website": vals("P856"), "image": vals("P18"), "commons_category": vals("P373"),
           "inception": vals("P571"), "enwiki": ent.get("sitelinks", {}).get("enwiki", {}).get("title")}
    ids = [x for k in ("instance_of", "country", "located_in") for x in res[k] if isinstance(x, str)]
    if ids:
        lr = http.get("https://www.wikidata.org/w/api.php",
                      {"action": "wbgetentities", "ids": "|".join(ids[:40]), "props": "labels", "languages": "en",
                       "format": "json"})
        if lr["ok"]:
            labels = {k: v.get("labels", {}).get("en", {}).get("value", k)
                      for k, v in lr["data"].get("entities", {}).items()}
            for k in ("instance_of", "country", "located_in"):
                res[k] = [f"{labels.get(x, x)} ({x})" for x in res[k]]
    return res


def wikidata_sparql(http: Http, query: str) -> dict:
    """Run a SPARQL query on the Wikidata Query Service; rows are {var: value} dicts."""
    r = http.get("https://query.wikidata.org/sparql", {"query": query, "format": "json"},
                 headers={"Accept": "application/sparql-results+json"})
    if not r["ok"]:
        return {"ok": False, "error": r.get("error"), "vars": [], "rows": []}
    d = r.get("data") or {}
    names = d.get("head", {}).get("vars", [])
    rows = [{v: b[v].get("value") for v in names if v in b} for b in d.get("results", {}).get("bindings", [])]
    return {"ok": True, "vars": names, "rows": rows}


_POINT = re.compile(r"Point\(\s*(-?[\d.]+(?:[eE]-?\d+)?)\s+(-?[\d.]+(?:[eE]-?\d+)?)\s*\)")


def sparql_places(res: dict) -> list[dict]:
    """Rows with an item URI, a label and a WKT point -> place dicts (name, lat, lon, wikidata)."""
    names = res.get("vars", [])
    coord_v = next((v for v in names if any(_POINT.search(str(r.get(v, ""))) for r in res["rows"][:20])), None)
    item_v = next((v for v in names if any(str(r.get(v, "")).startswith("http://www.wikidata.org/entity/Q")
                                           for r in res["rows"][:20])), None)
    label_v = next((v for v in names if v.lower().endswith("label")), None)
    out, seen = [], set()
    for r in res["rows"]:
        m = _POINT.search(str(r.get(coord_v, ""))) if coord_v else None
        if not m:
            continue
        qid = str(r.get(item_v, "")).rsplit("/", 1)[-1] if item_v else None
        key = (qid, m.group(1), m.group(2))
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": r.get(label_v) or qid or "?", "lat": float(m.group(2)), "lon": float(m.group(1)),
                    "wikidata": qid, "address": None, "osm": None})
    return out


WMO_CODES = {0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "rime fog",
             51: "light drizzle", 53: "drizzle", 55: "dense drizzle", 56: "light freezing drizzle",
             57: "freezing drizzle", 61: "slight rain", 63: "rain", 65: "heavy rain", 66: "light freezing rain",
             67: "freezing rain", 71: "slight snowfall", 73: "snowfall", 75: "heavy snowfall", 77: "snow grains",
             80: "slight rain showers", 81: "rain showers", 82: "violent rain showers", 85: "slight snow showers",
             86: "heavy snow showers", 95: "thunderstorm", 96: "thunderstorm with slight hail",
             99: "thunderstorm with heavy hail"}
_DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,sunshine_duration,"
          "sunrise,sunset")
_HOURLY = "weather_code,temperature_2m,cloud_cover,precipitation,snow_depth,is_day"


def weather_at(http: Http, lat: float, lon: float, day: str, hour: int | None = None) -> dict:
    """Daily (and, with `hour`, hourly) weather on a past date from Open-Meteo: ERA5 reanalysis archive for
    dates older than ~6 days, the forecast API's recent past otherwise. Grid cells are ~10-25 km wide, so
    this is regional weather, not the street."""
    d = dt.date.fromisoformat(day)
    recent = (dt.date.today() - d).days < 6
    url = "https://api.open-meteo.com/v1/forecast" if recent else "https://archive-api.open-meteo.com/v1/archive"
    params = {"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "start_date": day, "end_date": day,
              "daily": _DAILY, "hourly": _HOURLY, "timezone": "auto"}
    r = http.get(url, params)
    if not r["ok"] and "snow_depth" in str(r.get("error", "")):
        params["hourly"] = _HOURLY.replace(",snow_depth", "")
        r = http.get(url, params)
    if not r["ok"]:
        return {"ok": False, "error": r.get("error"), "service": url.split("/")[2]}
    j = r.get("data") or {}
    if j.get("error"):
        return {"ok": False, "error": j.get("reason") or "error", "service": url.split("/")[2]}
    daily = {k: (v[0] if isinstance(v, list) and v else None) for k, v in (j.get("daily") or {}).items()}
    out = {"ok": True, "service": url.split("/")[2], "grid_lat": j.get("latitude"), "grid_lon": j.get("longitude"),
           "timezone": j.get("timezone"), "date": day, "daily": daily,
           "daily_text": WMO_CODES.get(daily.get("weather_code"), str(daily.get("weather_code"))),
           "units": j.get("daily_units")}
    hourly = j.get("hourly") or {}
    if hour is not None and hourly.get("time"):
        idx = next((i for i, t in enumerate(hourly["time"]) if t.endswith(f"T{hour:02d}:00")), None)
        if idx is not None:
            h = {k: (v[idx] if isinstance(v, list) and len(v) > idx else None) for k, v in hourly.items()}
            h["weather_text"] = WMO_CODES.get(h.get("weather_code"), str(h.get("weather_code")))
            out["at_hour"] = h
            out["hourly_units"] = j.get("hourly_units")
    return out


def wigle_ssid(http: Http, ssid: str, near: tuple[float, float] | None = None, box_deg: float = 0.5,
               like: bool = False) -> dict:
    """Wi-Fi networks by SSID from WiGLE (needs the user's own free API name + token in WIGLE_API_NAME /
    WIGLE_API_TOKEN). Returns places; access-point MAC addresses are not reported."""
    import base64
    import os
    name, token = os.environ.get("WIGLE_API_NAME"), os.environ.get("WIGLE_API_TOKEN")
    if not (name and token):
        return {"ok": False, "unavailable": True, "results": [],
                "error": "no WiGLE key: the user can create a free account at wigle.net, copy the API name and "
                         "token (Account page) and set WIGLE_API_NAME and WIGLE_API_TOKEN"}
    p: dict = {("ssidlike" if like else "ssid"): ssid, "resultsPerPage": 100}
    if near:
        lat, lon = near
        p.update({"latrange1": round(lat - box_deg, 6), "latrange2": round(lat + box_deg, 6),
                  "longrange1": round(lon - box_deg, 6), "longrange2": round(lon + box_deg, 6)})
    auth = base64.b64encode(f"{name}:{token}".encode()).decode()
    r = http.get("https://api.wigle.net/api/v2/network/search", p, headers={"Authorization": f"Basic {auth}"})
    if not r["ok"]:
        return {"ok": False, "error": r.get("error"), "results": []}
    d = r.get("data") or {}
    if not d.get("success", False):
        return {"ok": False, "error": d.get("message") or "WiGLE refused the query", "results": []}
    out = []
    for it in d.get("results", []):
        if it.get("trilat") is None or it.get("trilong") is None:
            continue
        where = ", ".join(str(x) for x in (it.get("road"), it.get("city"), it.get("region"), it.get("country")) if x)
        out.append({"name": f"{it.get('ssid') or ssid}" + (f" ({it.get('city')})" if it.get("city") else ""),
                    "ssid": it.get("ssid"), "lat": float(it["trilat"]), "lon": float(it["trilong"]),
                    "address": where, "last_seen": it.get("lastupdt") or it.get("lasttime"), "osm": None})
    return {"ok": True, "total": d.get("totalResults", len(out)), "results": out}


KAABA = (21.422487, 39.826206)
_COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from point 1 to point 2, degrees clockwise from true north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return round((math.degrees(math.atan2(x, y)) + 360.0) % 360.0, 2)


def compass(deg: float) -> str:
    return _COMPASS[int((deg % 360) / 22.5 + 0.5) % 16]


def timezone_at(http: Http, lat: float, lon: float, when: str | None = None) -> dict:
    r = http.get("https://timeapi.io/api/TimeZone/coordinate", {"latitude": lat, "longitude": lon})
    if not r["ok"]:
        return {"ok": False, "error": r.get("error")}
    d = r["data"]
    out = {"ok": True, "zone": d.get("timeZone"), "current_offset": d.get("currentUtcOffset", {}).get("seconds"),
           "standard_offset": d.get("standardUtcOffset", {}).get("seconds"), "dst": d.get("hasDayLightSaving")}
    if when and out["zone"]:
        try:
            from zoneinfo import ZoneInfo
            t = dt.datetime.fromisoformat(when.replace("Z", "")).replace(tzinfo=None)
            off = ZoneInfo(out["zone"]).utcoffset(t)
            if off is not None:
                mins = int(off.total_seconds() // 60)
                out["offset_at_time"] = f"{'+' if mins >= 0 else '-'}{abs(mins) // 60:02d}:{abs(mins) % 60:02d}"
        except Exception:  # noqa: BLE001
            pass
    return out


def sun_position(lat: float, lon: float, when_utc: dt.datetime) -> tuple[float, float]:
    """(azimuth from true north clockwise, apparent-ish elevation) in degrees - NOAA solar equations."""
    t = when_utc.astimezone(dt.timezone.utc) if when_utc.tzinfo else when_utc.replace(tzinfo=dt.timezone.utc)
    jd = t.timestamp() / 86400.0 + 2440587.5
    jc = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360
    m = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    e = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    c = (math.sin(math.radians(m)) * (1.914602 - jc * (0.004817 + 0.000014 * jc)) +
         math.sin(math.radians(2 * m)) * (0.019993 - 0.000101 * jc) + math.sin(math.radians(3 * m)) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * jc
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + ((21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813)))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app_long))))
    y = math.tan(math.radians(eps / 2)) ** 2
    eot = 4 * math.degrees(y * math.sin(2 * math.radians(l0)) - 2 * e * math.sin(math.radians(m)) +
                           4 * e * y * math.sin(math.radians(m)) * math.cos(2 * math.radians(l0)) -
                           0.5 * y * y * math.sin(4 * math.radians(l0)) - 1.25 * e * e * math.sin(2 * math.radians(m)))
    minutes = t.hour * 60 + t.minute + t.second / 60
    tst = (minutes + eot + 4 * lon) % 1440
    ha = tst / 4 - 180 if tst / 4 >= 0 else tst / 4 + 180
    zen = math.degrees(math.acos(max(-1, min(1, math.sin(math.radians(lat)) * math.sin(math.radians(decl)) +
                                             math.cos(math.radians(lat)) * math.cos(math.radians(decl)) *
                                             math.cos(math.radians(ha))))))
    elev = 90 - zen
    az_den = math.cos(math.radians(lat)) * math.sin(math.radians(zen))
    if abs(az_den) < 1e-9:
        az = 180.0
    else:
        az_cos = ((math.sin(math.radians(lat)) * math.cos(math.radians(zen))) - math.sin(math.radians(decl))) / az_den
        az = math.degrees(math.acos(max(-1, min(1, az_cos))))
        az = (az + 180) % 360 if ha > 0 else (540 - az) % 360
    if elev > -0.575:   # rough refraction correction
        elev += 1.02 / math.tan(math.radians(elev + 10.3 / (elev + 5.11))) / 60
    return round(az, 2), round(elev, 2)
