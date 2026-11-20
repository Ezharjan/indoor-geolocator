"""Geometry against external references, and the network parsers fed with recorded-style payloads
through a fake HTTP client (no network)."""
from __future__ import annotations

import datetime as dt
import urllib.parse

import pytest
from iglib import geo, imaging, social
from iglib.net import _reason

# NREL SPA via pvlib (apparent elevation), computed once with pvlib 0.13: (lat, lon, time, azimuth, elevation)
SUN_REF = [
    (48.2085, 16.3731, "2024-05-01T15:30+02:00", 238.44, 43.82),
    (51.4769, 0.0, "2024-06-21T12:00+00:00", 179.06, 61.97),
    (-33.8688, 151.2093, "2024-12-21T13:00+11:00", 351.50, 79.47),
    (35.6762, 139.6503, "2025-01-15T08:10+09:00", 128.24, 12.93),
    (64.1466, -21.9426, "2024-03-20T17:45+00:00", 244.99, 11.91),
    (1.3521, 103.8198, "2024-09-01T18:50+08:00", 277.94, 3.99),
    (40.7128, -74.0060, "2023-11-05T07:00-05:00", 114.95, 4.45),
    (-22.9068, -43.1729, "2024-07-10T16:00-03:00", 303.04, 15.99),
]


@pytest.mark.parametrize("lat,lon,t,az_ref,el_ref", SUN_REF)
def test_sun_matches_nrel_spa(lat, lon, t, az_ref, el_ref):
    az, el = geo.sun_position(lat, lon, dt.datetime.fromisoformat(t))
    assert abs((az - az_ref + 180) % 360 - 180) < 0.1 and abs(el - el_ref) < 0.1


# WGS84 geodesic initial azimuths (geographiclib); the spherical formula stays within 0.2 degrees
@pytest.mark.parametrize("a,b,ref", [((48.2085, 16.3731), (48.2166, 16.3958), 61.89),
                                     ((51.5074, -0.1278), geo.KAABA, 118.87),
                                     ((40.7128, -74.0060), geo.KAABA, 58.40),
                                     ((-33.8688, 151.2093), (-33.8568, 151.2153), 22.64)])
def test_bearing_close_to_wgs84(a, b, ref):
    assert abs(geo.bearing_deg(*a, *b) - ref) < 0.2


def test_compass():
    assert [geo.compass(x) for x in (0, 44, 46, 180, 292, 359)] == ["N", "NE", "NE", "S", "WNW", "N"]


def test_poi_ql_and_colocation():
    ql = geo.build_poi_ql(["tourism=hotel"], None, "Hampton", {"around": [48.2, 16.37, 800]},
                          near=["amenity=place_of_worship@150"])
    assert '["tourism"="hotel"]' in ql and '["brand"~"Hampton",i]' in ql and "around.n0:150" in ql


class FakeHttp:
    cache_dir = None

    def __init__(self, routes: dict):
        self.routes, self.calls = routes, []

    def get(self, url, params=None, headers=None, as_json=True, **kw):
        self.calls.append((url, params, headers))
        for key, payload in self.routes.items():
            if key in url:
                return {"ok": True, "status": 200, **({"data": payload} if as_json else {"text": payload})}
        return {"ok": False, "status": 0, "error": "unreachable"}


def test_sparql_rows_to_places():
    res = {"vars": ["item", "itemLabel", "coord"],
           "rows": [{"item": "http://www.wikidata.org/entity/Q1", "itemLabel": "A", "coord": "Point(16.3 48.2)"},
                    {"item": "http://www.wikidata.org/entity/Q1", "itemLabel": "A", "coord": "Point(16.3 48.2)"},
                    {"item": "http://www.wikidata.org/entity/Q2", "itemLabel": "B", "coord": "Point(-74.0 40.7)"}]}
    places = geo.sparql_places(res)
    assert [(p["wikidata"], p["lat"], p["lon"]) for p in places] == [("Q1", 48.2, 16.3), ("Q2", 40.7, -74.0)]


def test_weather_parser_picks_capture_hour():
    payload = {"latitude": 48.2, "longitude": 16.4, "timezone": "Europe/Vienna",
               "daily_units": {"temperature_2m_max": "°C"},
               "daily": {"time": ["2024-01-15"], "weather_code": [71], "temperature_2m_max": [1.2]},
               "hourly_units": {"snow_depth": "m"},
               "hourly": {"time": ["2024-01-15T13:00", "2024-01-15T14:00"], "weather_code": [3, 73],
                          "snow_depth": [0.04, 0.05], "cloud_cover": [100, 98]}}
    r = geo.weather_at(FakeHttp({"open-meteo.com": payload}), 48.2, 16.37, "2024-01-15", 14)
    assert r["ok"] and r["daily_text"] == "slight snowfall"
    assert r["at_hour"]["weather_text"] == "snowfall" and r["at_hour"]["snow_depth"] == 0.05


def test_weather_quota_error_is_reported():
    r = geo.weather_at(FakeHttp({"open-meteo.com": {"error": True, "reason": "Daily API request limit exceeded"}}),
                       48.2, 16.37, "2024-01-15")
    assert not r["ok"] and "limit" in r["error"]


def test_http_error_reason():
    assert _reason('{"error":true,"reason":"Daily API request limit exceeded."}').startswith("Daily")
    assert _reason("<html>nope</html>") == ""


def test_social_links_are_well_formed():
    rows = social.links("Hotel Sacher Wien", at=(48.2039, 16.3696))
    assert len(rows) > 25
    for r in rows:
        u = urllib.parse.urlparse(r["url"])
        assert u.scheme == "https" and u.netloc and r["kind"] in ("engine", "native")
    ig = [r for r in rows if r["platform"] == "instagram" and "explore/tags" in r["url"]]
    assert ig and ig[0]["url"].endswith("/hotelsacherwien/")
    only = social.links("x", only=["xiaohongshu"])
    assert {r["platform"] for r in only} == {"xiaohongshu"}


def test_social_parsers():
    bsky = {"posts": [{"uri": "at://did:plc:abc/app.bsky.feed.post/3k", "author": {"handle": "a.bsky.social"},
                       "record": {"text": "Lobby", "createdAt": "2026-01-01T10:00:00Z"},
                       "embed": {"$type": "app.bsky.embed.recordWithMedia#view",
                                 "media": {"images": [{"thumb": "https://cdn/t.jpg", "fullsize": "https://cdn/f.jpg",
                                                       "alt": "marble lobby"}]}}}]}
    flickr = ('{"items":[{"title":"Lobby\\\'s view","link":"https://www.flickr.com/photos/x/1/",'
              '"media":{"m":"https://live.staticflickr.com/1_m.jpg"},"date_taken":"2025-05-14T10:00:00","tags":"hotel"}]}')
    masto = [{"url": "https://m.social/@a/1", "created_at": "2026-01-02T00:00:00Z", "content": "<p>Bar &amp; lobby</p>",
              "media_attachments": [{"preview_url": "https://m/p.jpg", "url": "https://m/f.jpg", "description": "bar"}]}]
    http = FakeHttp({"bsky.app": bsky, "flickr.com": flickr, "/timelines/tag/": masto})
    r = social.search(http, "hotel lobby", ["bluesky", "flickr", "mastodon"])
    b = r["bluesky"]["items"][0]
    assert b["url"] == "https://bsky.app/profile/a.bsky.social/post/3k" and "marble lobby" in b["text"]
    assert b["thumbs"] == ["https://cdn/t.jpg"]
    f = r["flickr"]["items"][0]
    assert f["images"] == ["https://live.staticflickr.com/1_b.jpg"] and "Lobby's view" in f["text"]
    assert r["mastodon"]["items"][0]["text"].startswith("Bar & lobby") and r["mastodon"]["tag"] == "hotellobby"


def test_wigle_requires_key(monkeypatch):
    monkeypatch.delenv("WIGLE_API_NAME", raising=False)
    monkeypatch.delenv("WIGLE_API_TOKEN", raising=False)
    r = geo.wigle_ssid(FakeHttp({}), "CafeX")
    assert not r["ok"] and r.get("unavailable")


def test_grid_cells_and_contact_sheet():
    spec = imaging.grid_spec((1600, 1200))
    x0, y0, x1, y1 = imaging.cell_box(spec, "B2:C3")
    assert 0 < x0 < x1 <= 1600 and 0 < y0 < y1 <= 1200
    from PIL import Image
    sheet = imaging.contact_sheet([("a", Image.new("RGB", (300, 200))), ("b", Image.new("RGB", (200, 300)))])
    assert sheet.size[0] > 0 and sheet.size[1] > 0
