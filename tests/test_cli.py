"""Command-line plumbing: argument parsing, negative coordinates, offline geometry commands."""
from __future__ import annotations

import json

import igl
import pytest
from conftest import run


def test_join_negative_values():
    j = igl.join_negative_values
    assert j(["sun", "--at", "-33.86,151.21", "--time", "x"]) == ["sun", "--at=-33.86,151.21", "--time", "x"]
    assert j(["geo", "poi", "--bbox", "-34.1,150.9,-33.7,151.3"]) == ["geo", "poi", "--bbox=-34.1,150.9,-33.7,151.3"]
    assert j(["crop", "c", "--rotate", "-5"]) == ["crop", "c", "--rotate", "-5"]          # plain numbers untouched
    assert j(["note", "c", "-33.8,151.2 is in the caption"]) == ["note", "c", "-33.8,151.2 is in the caption"]
    assert j(["x", "--at=-1,2"]) == ["x", "--at=-1,2"]


def test_every_command_has_help():
    parser = igl.build_parser()
    sub = next(a for a in parser._actions if a.dest == "cmd")
    for name in sub.choices:
        with pytest.raises(SystemExit) as e:
            parser.parse_args([name, "-h"])
        assert e.value.code == 0


def test_bearing_southern_hemisphere_and_qibla():
    code, out = run("bearing", "--from", "-6.2088,106.8456", "--to", "qibla")
    assert code == 0
    d = json.loads(out)
    assert abs(d["bearing_deg"] - 295.0) < 0.3 and d["compass"] == "WNW"      # WGS84 reference: 295.02


def test_bearing_facing():
    code, out = run("bearing", "--from", "48.2085,16.3731", "--to", "48.2166,16.3958", "--facing", "60")
    d = json.loads(out)
    assert 1850 < d["distance_m"] < 1950 and d["in_view"].startswith("yes")
    code, out = run("bearing", "--from", "48.2085,16.3731", "--to", "48.2166,16.3958", "--facing", "240")
    assert json.loads(out)["in_view"].startswith("no")


def test_sun_command_needs_offset():
    code, out = run("sun", "--at", "48.2,16.37", "--time", "2024-05-01T15:30")
    assert code == 2


def test_countries_intersection_offline():
    code, out = run("countries", "--plug", "G", "--currency", "£", "--drive", "left")
    assert code == 0
    assert "GB" in out and "Ireland" not in out              # Ireland: Type G and left, but the euro


def test_lookup_plugs_and_barcode():
    code, out = run("lookup", "plugs")
    assert "Type K" in out and "Type O" in out
    code, out = run("lookup", "barcode", "4006381333931")      # valid EAN-13, GS1 Germany
    d = json.loads(out)
    assert d["valid_checksum"] is True and "Germany" in d["gs1"]["org"]
