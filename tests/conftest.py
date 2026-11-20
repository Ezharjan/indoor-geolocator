"""Shared fixtures. The tests are offline: nothing here touches the network."""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "indoor-geolocator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import igl  # noqa: E402


def run(*argv: str) -> tuple[int, str]:
    """Run igl.py in-process and capture what it prints."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = igl.main([str(a) for a in argv])
    return code, buf.getvalue()


def make_jpeg(path: Path, lat: float | None = None, lon: float | None = None, when: str | None = None,
              offset: str | None = None, size=(640, 480), color=(180, 160, 140)) -> Path:
    """A small JPEG with optional EXIF GPS (signed decimal degrees), capture time and UTC offset."""
    from PIL import Image
    im = Image.new("RGB", size, color)
    exif = Image.Exif()
    if when:
        exif.get_ifd(0x8769)[0x9003] = when                      # DateTimeOriginal "YYYY:MM:DD HH:MM:SS"
        if offset:
            exif.get_ifd(0x8769)[0x9011] = offset                # OffsetTimeOriginal "+09:00"
    if lat is not None and lon is not None:
        def dms(v):
            v = abs(v)
            d = int(v)
            m = int((v - d) * 60)
            s = round(((v - d) * 60 - m) * 60, 4)
            return (d, m, s)
        exif.get_ifd(0x8825).update({1: "S" if lat < 0 else "N", 2: dms(lat), 3: "W" if lon < 0 else "E", 4: dms(lon)})
    im.save(path, "JPEG", quality=90, exif=exif.tobytes())
    return path


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    return make_jpeg(tmp_path / "room.jpg")


@pytest.fixture
def case_dir(tmp_path: Path, photo: Path) -> Path:
    out = tmp_path / "case"
    code, _ = run("init", photo, "--out", out)
    assert code == 0
    return out
