"""Image-to-image tests behind `compare` (near-duplicate, same photograph, same structure, mirrored room),
the `compare` command itself, the by-URL search links of `share`, redaction and the C2PA reader. Offline:
the test images are synthetic."""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from conftest import run
from PIL import Image, ImageDraw, ImageOps

from iglib import match, revsearch, share
from iglib.metadata import _c2pa_info
from iglib.util import redact

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")


def scene(seed: int, size=(900, 600)) -> Image.Image:
    """A textured 'room': random rectangles, circles and lines (plenty of corners for SIFT)."""
    rnd = random.Random(seed)
    im = Image.new("RGB", size, (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)))
    d = ImageDraw.Draw(im)
    for _ in range(260):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        w, h = rnd.randrange(8, 90), rnd.randrange(8, 90)
        c = (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
        kind = rnd.random()
        if kind < 0.45:
            d.rectangle([x, y, x + w, y + h], fill=c, outline=(0, 0, 0))
        elif kind < 0.8:
            d.ellipse([x, y, x + w, y + h], fill=c, outline=(255, 255, 255))
        else:
            d.line([x, y, x + w, y + h], fill=c, width=3)
    return im


def new_view(im: Image.Image) -> Image.Image:
    """The same planar scene from another viewpoint (perspective warp) with a little lighting change."""
    w, h = im.size
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[60, 30], [w - 20, 0], [w - 90, h - 10], [10, h - 60]])
    H = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(np.asarray(im), H, (w, h), borderValue=(40, 40, 40))
    return Image.fromarray(np.clip(out.astype(np.int16) + 18, 0, 255).astype(np.uint8))


def test_near_duplicate_and_mirror():
    q = scene(1)
    d = match.duplicate(q, q.resize((450, 300)))
    assert d["near_duplicate"] and not d["mirrored_duplicate"]
    d = match.duplicate(q, ImageOps.mirror(q))
    assert d["mirrored_duplicate"] and not d["near_duplicate"]
    assert not match.duplicate(q, scene(2))["near_duplicate"]


def test_same_photo_crop_is_provenance_not_match():
    q = scene(3)
    g = match.geometric(q, q.crop((200, 100, 800, 560)))
    assert g["available"] and g["same_photo"]
    assert match.verdict(match.duplicate(q, q.crop((200, 100, 800, 560))), g).startswith("SAME PHOTOGRAPH")


def test_new_viewpoint_is_strong_unrelated_is_none():
    q = scene(4)
    g = match.geometric(q, new_view(q))
    assert g["level"] == "strong" and not g["same_photo"] and not g["mirrored"]
    assert match.verdict(match.duplicate(q, new_view(q)), g).startswith("STRONG")
    g2 = match.geometric(q, scene(5))
    assert g2["level"] == "none"


def test_mirror_image_room_is_detected():
    q = scene(6)
    g = match.geometric(q, ImageOps.mirror(new_view(q)))
    assert g["level"] == "strong" and g["mirrored"]
    assert "MIRRORED" in match.verdict(match.duplicate(q, ImageOps.mirror(new_view(q))), g)


def test_compare_command_writes_sheet_inliers_and_json(tmp_path: Path):
    photo = tmp_path / "room.jpg"
    scene(7).save(photo, quality=92)
    ref = tmp_path / "ref.jpg"
    new_view(scene(7)).save(ref, quality=92)
    other = tmp_path / "other.jpg"
    scene(8).save(other, quality=92)
    case = tmp_path / "case"
    assert run("init", photo, "--out", case, "--no-probe")[0] == 0
    code, out = run("compare", case, "--ref", ref, "--ref", other, "--label", "t")
    assert code == 0, out
    assert "STRONG geometric agreement" in out and "no geometric agreement" in out
    data = json.loads((case / "case.json").read_text(encoding="utf-8"))
    whats = " ".join(f["what"] for f in data["files"].values())
    assert "side-by-side" in whats and "inlier correspondences" in whats and "automatic match tests" in whats


def test_compare_flags_references_that_are_one_photograph(tmp_path: Path):
    photo = tmp_path / "room.jpg"
    scene(9).save(photo, quality=92)
    view = new_view(scene(9))
    ref = tmp_path / "ref.jpg"
    view.save(ref, quality=92)
    crop = tmp_path / "ref-crop.jpg"
    view.crop((100, 80, 800, 560)).save(crop, quality=92)          # the same reference photo, cropped
    case = tmp_path / "case"
    assert run("init", photo, "--out", case, "--no-probe")[0] == 0
    code, out = run("compare", case, "--ref", ref, "--ref", crop)
    assert code == 0 and "R2 and R1 are the SAME PHOTOGRAPH" in out


def test_by_url_links_and_multipart(tmp_path: Path):
    links = revsearch.by_url_links("https://h.example.org/a b.jpg")
    assert links["lens"].startswith("https://lens.google.com/uploadbyurl?url=https%3A%2F%2Fh.example.org%2Fa%20b.jpg")
    assert "imgurl:https%3A%2F%2F" in links["bing"] and "rpt=imageview&url=" in links["yandex"]
    assert links["tineye"].startswith("https://tineye.com/search?url=")
    f = tmp_path / "x.jpg"
    Image.new("RGB", (4, 4)).save(f)
    body, ctype = share._multipart({"time": "1h"}, "fileToUpload", f)
    boundary = ctype.split("boundary=")[1]
    assert body.startswith(f"--{boundary}".encode()) and body.rstrip().endswith(f"--{boundary}--".encode())
    assert b'name="fileToUpload"; filename="x.jpg"' in body and b'name="time"\r\n\r\n1h' in body
    assert share.upload(None, f, host="nope")["ok"] is False


def test_redact():
    assert "violet" not in redact("QR WIFI:T:WPA;S:Larkspur-Guest;P:violet-lamp-42;; seen")
    assert "Larkspur-Guest" in redact("WIFI:T:WPA;S:Larkspur-Guest;P:violet-lamp-42;;")
    assert redact("Password: hunter22 thanks") == "Password: <redacted> thanks"
    assert redact("IBAN DE89 3704 0044 0532 0130 00") == "IBAN DE89****"
    assert redact("Room 1205, 12:30") == "Room 1205, 12:30"


def test_c2pa_reader():
    blob = (b"\x00jumdc2pa\x00c2pa.actions.v2\x00c2pa.created\x00digitalSourceType\x00"
            b"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia\x00claim_generator\x00"
            b"OpenAI-API\x00")
    info = _c2pa_info(blob)
    assert info["ai_generated"] and "OpenAI" in info["signers"] and "created" in info["actions"]
