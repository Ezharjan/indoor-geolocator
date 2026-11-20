"""Image views for the agent: upright loading, labelled overview grid, crops/enhancement, tiles,
reverse-search variants, annotation and contact sheets. Pillow only; numpy/OpenCV are optional extras."""
from __future__ import annotations

import math
import re
from pathlib import Path

from .util import IglError

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
except ImportError as e:  # pragma: no cover - reported by doctor
    raise IglError("Pillow is required: pip install pillow") from e

try:  # HEIC/HEIF photos from iPhones
    import pillow_heif  # type: ignore

    pillow_heif.register_heif_opener()
except Exception:  # noqa: BLE001
    pass

Image.MAX_IMAGE_PIXELS = 400_000_000
VIEW_MAX = 1600          # long side of images produced for viewing


def font(size: int = 16):
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "Arial.ttf", "arial.ttf", "LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def open_image(path: Path) -> tuple["Image.Image", dict]:
    """Open a photo upright (EXIF orientation applied), first frame, RGB. Pixel coordinates used by every
    command refer to this upright frame."""
    try:
        im = Image.open(path)
    except Exception as e:  # noqa: BLE001
        raise IglError(f"Cannot open {path} as an image ({e}). HEIC needs `pip install pillow-heif`.") from e
    info = {"format": im.format, "mode": im.mode, "stored_size": list(im.size),
            "frames": getattr(im, "n_frames", 1)}
    try:
        orient = im.getexif().get(0x0112, 1)
    except Exception:  # noqa: BLE001
        orient = 1
    info["orientation"] = orient
    if info["frames"] > 1:
        im.seek(0)
    up = flatten(ImageOps.exif_transpose(im))
    info["size"] = list(up.size)
    return up, info


def flatten(im: "Image.Image") -> "Image.Image":
    """Any Pillow mode -> RGB (transparency over white), so every later step sees the same pixels."""
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        rgba = im.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return im if im.mode == "RGB" else im.convert("RGB")


def fit(im: "Image.Image", max_side: int = VIEW_MAX, min_side: int = 0) -> "Image.Image":
    w, h = im.size
    s = 1.0
    if max(w, h) > max_side:
        s = max_side / max(w, h)
    elif min_side and max(w, h) < min_side:
        s = min(4.0, min_side / max(w, h))
    if s == 1.0:
        return im
    return im.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)


# ---------------------------------------------------------------- grid
def grid_spec(size: tuple[int, int], target_cols: int = 8) -> dict:
    w, h = size
    if w >= h:
        cols = target_cols
        rows = max(2, round(cols * h / w))
    else:
        rows = target_cols
        cols = max(2, round(rows * w / h))
    return {"cols": cols, "rows": rows, "width": w, "height": h}


def _col_label(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def cell_box(spec: dict, ref: str) -> tuple[int, int, int, int]:
    """'C3' -> pixel box of that cell; 'C3:E5' -> box spanning both cells (upright pixels)."""
    parts = ref.upper().replace(" ", "").split(":")
    boxes = []
    for p in parts:
        m = re.fullmatch(r"([A-Z]+)(\d+)", p)
        if not m:
            raise IglError(f"Bad grid cell {p!r}: use e.g. C3 or C3:E5 (letters = columns, numbers = rows)")
        col = 0
        for ch in m.group(1):
            col = col * 26 + (ord(ch) - 64)
        col -= 1
        row = int(m.group(2)) - 1
        if not (0 <= col < spec["cols"] and 0 <= row < spec["rows"]):
            raise IglError(f"Cell {p} is outside the grid ({_col_label(spec['cols'] - 1)}{spec['rows']} is the last)")
        cw, ch_ = spec["width"] / spec["cols"], spec["height"] / spec["rows"]
        boxes.append((col * cw, row * ch_, (col + 1) * cw, (row + 1) * ch_))
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    return int(x0), int(y0), int(math.ceil(x1)), int(math.ceil(y1))


def draw_grid(im: "Image.Image", spec: dict) -> "Image.Image":
    view = fit(im, VIEW_MAX)
    sx, sy = view.width / spec["width"], view.height / spec["height"]
    over = view.convert("RGBA")
    layer = Image.new("RGBA", over.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cw, ch = spec["width"] / spec["cols"], spec["height"] / spec["rows"]
    f = font(max(12, int(min(cw * sx, ch * sy) / 6)))
    for i in range(1, spec["cols"]):
        x = i * cw * sx
        d.line([(x, 0), (x, view.height)], fill=(255, 255, 0, 150), width=1)
    for j in range(1, spec["rows"]):
        y = j * ch * sy
        d.line([(0, y), (view.width, y)], fill=(255, 255, 0, 150), width=1)
    for i in range(spec["cols"]):
        for j in range(spec["rows"]):
            label = f"{_col_label(i)}{j + 1}"
            x, y = i * cw * sx + 3, j * ch * sy + 2
            tb = d.textbbox((x, y), label, font=f)
            d.rectangle([tb[0] - 2, tb[1] - 1, tb[2] + 2, tb[3] + 1], fill=(0, 0, 0, 130))
            d.text((x, y), label, font=f, fill=(255, 255, 0, 230))
    return Image.alpha_composite(over, layer).convert("RGB")


# ---------------------------------------------------------------- crops and enhancement
ENHANCERS = ("auto", "sharpen", "contrast", "gray", "clahe", "denoise", "binarize", "invert", "brighten")


def enhance(im: "Image.Image", ops: list[str]) -> "Image.Image":
    for op in ops:
        op = op.strip().lower()
        if not op:
            continue
        if op not in ENHANCERS:
            raise IglError(f"Unknown enhancement {op!r}: choose from {', '.join(ENHANCERS)}")
        if op == "auto":
            im = ImageOps.autocontrast(im, cutoff=1)
            im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=2))
        elif op == "sharpen":
            im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=1))
        elif op == "contrast":
            im = ImageOps.autocontrast(im, cutoff=2)
        elif op == "gray":
            im = ImageOps.grayscale(im).convert("RGB")
        elif op == "denoise":
            im = im.filter(ImageFilter.MedianFilter(3))
        elif op == "invert":
            im = ImageOps.invert(im.convert("RGB"))
        elif op == "brighten":
            im = im.point(lambda v: int(255 * ((v / 255) ** 0.6)))
        elif op == "clahe":
            im = _clahe(im)
        elif op == "binarize":
            g = ImageOps.grayscale(im)
            thr = _otsu(g)
            im = g.point(lambda v, t=thr: 255 if v > t else 0).convert("RGB")
    return im


def _clahe(im: "Image.Image") -> "Image.Image":
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        lab = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2LAB)
        l_, a, b = cv2.split(lab)
        l_ = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(l_)
        return Image.fromarray(cv2.cvtColor(cv2.merge((l_, a, b)), cv2.COLOR_LAB2RGB))
    except Exception:  # noqa: BLE001 - OpenCV missing: global equalisation instead
        return ImageOps.equalize(im)


def _otsu(g: "Image.Image") -> int:
    hist = g.histogram()
    total = sum(hist)
    s = sum(i * h for i, h in enumerate(hist))
    sb = wb = 0
    best, thr = 0.0, 128
    for t in range(256):
        wb += hist[t]
        if wb == 0:
            continue
        wf = total - wb
        if wf == 0:
            break
        sb += t * hist[t]
        mb, mf = sb / wb, (s - sb) / wf
        between = wb * wf * (mb - mf) ** 2
        if between > best:
            best, thr = between, t
    return thr


def crop(im: "Image.Image", box: tuple[int, int, int, int], pad: float = 0.0) -> "Image.Image":
    w, h = im.size
    x0, y0, x1, y1 = box
    if pad:
        px, py = (x1 - x0) * pad, (y1 - y0) * pad
        x0, y0, x1, y1 = x0 - px, y0 - py, x1 + px, y1 + py
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(w, int(math.ceil(x1))), min(h, int(math.ceil(y1)))
    if x1 - x0 < 2 or y1 - y0 < 2:
        raise IglError(f"Box {box} is empty or outside the image ({w}x{h})")
    return im.crop((x0, y0, x1, y1))


def view_of(part: "Image.Image", scale: float | None = None, min_side: int = 900) -> "Image.Image":
    """Upscale small crops so details are legible (x1..x4), never beyond VIEW_MAX."""
    if scale:
        w, h = part.size
        s = min(scale, VIEW_MAX / max(w, h)) if max(w, h) * scale > VIEW_MAX else scale
        return part.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    return fit(part, VIEW_MAX, min_side=min_side)


def tiles(size: tuple[int, int], cols: int = 3, rows: int = 3, overlap: float = 0.15) -> list[tuple[str, tuple]]:
    w, h = size
    tw, th = w / (cols - (cols - 1) * overlap), h / (rows - (rows - 1) * overlap)
    out = []
    for j in range(rows):
        for i in range(cols):
            x0 = i * tw * (1 - overlap)
            y0 = j * th * (1 - overlap)
            out.append((f"r{j + 1}c{i + 1}", (int(x0), int(y0), int(min(w, x0 + tw)), int(min(h, y0 + th)))))
    return out


def annotate(im: "Image.Image", items: list[tuple[str, tuple]], color=(255, 40, 40)) -> "Image.Image":
    view = fit(im, VIEW_MAX).copy()
    s = view.width / im.width
    d = ImageDraw.Draw(view)
    f = font(13)
    for label, (x0, y0, x1, y1) in items:
        b = [x0 * s, y0 * s, x1 * s, y1 * s]
        d.rectangle(b, outline=color, width=2)
        tb = d.textbbox((b[0], max(0, b[1] - 15)), label, font=f)
        d.rectangle(tb, fill=(0, 0, 0))
        d.text((b[0], max(0, b[1] - 15)), label, font=f, fill=color)
    return view


def contact_sheet(images: list[tuple[str, "Image.Image"]], cols: int = 4, cell: int = 360) -> "Image.Image":
    rows = max(1, math.ceil(len(images) / cols))
    cap = 34
    sheet = Image.new("RGB", (cols * cell, rows * (cell + cap)), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    f = font(13)
    for k, (label, im) in enumerate(images):
        t = im.copy()
        t.thumbnail((cell - 8, cell - 8))
        x, y = (k % cols) * cell, (k // cols) * (cell + cap)
        sheet.paste(t, (x + (cell - t.width) // 2, y + 4 + (cell - 8 - t.height) // 2))
        text = label
        while text and d.textlength(text, font=f) > cell - 12:
            text = text[:-2]
        if text != label:
            text = text.rstrip() + "…"
        d.text((x + 6, y + cell + 2), text, font=f, fill=(235, 235, 235))
    return sheet


def variants(im: "Image.Image", box: tuple | None = None) -> list[tuple[str, "Image.Image"]]:
    """Reverse-search variants: the frame (<= 1600 px), a horizontal flip (reposts are often mirrored),
    and a tight crop when a box is given (engines match objects better without clutter)."""
    base = fit(im, VIEW_MAX)
    out = [("full", base), ("flip", ImageOps.mirror(base))]
    if box:
        out.append(("crop", fit(crop(im, box), VIEW_MAX, min_side=600)))
    return out
