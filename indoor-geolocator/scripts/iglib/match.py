"""Objective image-to-image tests: is a reference image the SAME PHOTO as the query (provenance), the SAME
PHYSICAL SCENE seen again (a match), or neither? Used by `compare`, by `refs` (ranking many reference
photos) and by `revsearch` (sorting engine results into copies, same-scene photos and look-alikes).

  duplicate()  perceptual hashes (pHash + dHash, also against the mirrored reference): a near-duplicate is
               the same photograph re-encoded, resized or flipped - provenance, never a confirmation.
  Matcher      local features of the query computed once (SIFT, ORB without it), then matched against any
               number of references: ratio test + RANSAC, a homography for planar structure (walls,
               floors, pictures) and a fundamental matrix for general two-view geometry, also against the
               mirror image (rooms on either side of a corridor are mirror images; reposts are flipped).
  geometric()  one query against one reference (a thin wrapper around Matcher).
  classify()   copy | same | partial | none | unchecked - the one-word result the other commands print.

What the numbers can and cannot say. A positive is reliable: geometric agreement proves that two images
show the same STRUCTURE, which is the same place only when the inliers lie on fixed architecture (windows,
ceiling, columns, built-ins, the view) or on something unique to the venue. Chain hotels repeat identical
furniture, carpets and art, which match just as well, and one small object (a framed print, a TV, a logo)
can carry every inlier: `spread` reports how much of the photo the inliers cover. A negative says almost
nothing: classical features do not survive a new viewpoint, another lens, other lighting, a renovation or
years between two photos, so real photos of the same room routinely score like strangers (measured: the
same bar, photographed years apart, 8-11 inliers; unrelated bars, 10-14). "unconfirmed" therefore means
"compare by eye", never "different place".

Needs numpy for pHash and OpenCV (opencv-python-headless) for the geometric test; without them the
corresponding part reports `unavailable` and only side-by-side sheets remain.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageOps

DUP_PHASH = 10        # Hamming distance (of 64 bits) at or below which two images are near-duplicates
DUP_DHASH = 12
STRONG_H, STRONG_F, STRONG_RATIO = 25, 50, 0.35
SOME_H, SOME_F = 12, 25
SMALL_SPREAD = 0.03   # inliers covering less than this share of the photo sit on one small object
LABEL = {"copy": "COPY", "same": "SAME SCENE", "partial": "PARTIAL", "none": "unconfirmed", "unchecked": "unchecked",
         "missing": "not fetched"}
RANK = {"copy": 4, "same": 3, "partial": 2, "none": 1, "unchecked": 0}


def _gray(im: Image.Image, size: tuple[int, int]) -> list[int]:
    return list(ImageOps.grayscale(im).resize(size, Image.LANCZOS).tobytes())


def dhash(im: Image.Image) -> int:
    px = _gray(im, (9, 8))
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | (1 if px[y * 9 + x] > px[y * 9 + x + 1] else 0)
    return bits


def phash(im: Image.Image) -> int | None:
    try:
        import numpy as np  # type: ignore
    except ImportError:
        return None
    a = np.asarray(_gray(im, (32, 32)), dtype=np.float64).reshape(32, 32)
    n = 32
    k = np.arange(n)
    basis = np.cos(np.pi * (2 * k[None, :] + 1) * k[:, None] / (2 * n))      # DCT-II basis
    dct = basis @ a @ basis.T
    low = dct[:8, :8].flatten()[1:]                                         # drop the DC term
    med = np.median(low)
    bits = 0
    for v in low:
        bits = (bits << 1) | (1 if v > med else 0)
    return bits


def hamming(a: int | None, b: int | None) -> int | None:
    return None if a is None or b is None else bin(a ^ b).count("1")


def hashes(im: Image.Image) -> dict:
    """Perceptual hashes of an image and of its mirror image (compute once, compare many times)."""
    m = ImageOps.mirror(im)
    return {"phash": phash(im), "dhash": dhash(im), "phash_m": phash(m), "dhash_m": dhash(m),
            "aspect": round(im.width / max(1, im.height), 3)}


def _is_dup(ph: int | None, dh: int) -> bool:
    return (ph is not None and ph <= DUP_PHASH and dh <= DUP_DHASH + 6) or (ph is None and dh <= DUP_DHASH - 4)


def duplicate_from(qh: dict, rh: dict) -> dict:
    """Near-duplicate test from two `hashes()` results (the mirrored comparison uses the mirrored query)."""
    out = {"direct": {"phash": hamming(qh["phash"], rh["phash"]), "dhash": hamming(qh["dhash"], rh["dhash"])},
           "mirrored": {"phash": hamming(qh["phash_m"], rh["phash"]), "dhash": hamming(qh["dhash_m"], rh["dhash"])},
           "aspect_ratio": [qh["aspect"], rh["aspect"]]}
    out["near_duplicate"] = _is_dup(out["direct"]["phash"], out["direct"]["dhash"])
    out["mirrored_duplicate"] = not out["near_duplicate"] and _is_dup(out["mirrored"]["phash"], out["mirrored"]["dhash"])
    return out


def duplicate(q: Image.Image, r: Image.Image) -> dict:
    """Near-duplicate test of the whole frames (also against the mirror image)."""
    return duplicate_from(hashes(q), hashes(r))


def _prep(im: Image.Image, max_side: int):
    import numpy as np  # type: ignore
    g = ImageOps.grayscale(im)
    s = min(1.0, max_side / max(g.size))
    if s < 1:
        g = g.resize((max(1, round(g.width * s)), max(1, round(g.height * s))), Image.LANCZOS)
    return np.asarray(g), s


def _features(cv2, arr, nfeatures: int = 4000):
    try:
        det = cv2.SIFT_create(nfeatures=nfeatures)
        kind = "sift"
    except Exception:  # noqa: BLE001 - very old OpenCV builds
        det = cv2.ORB_create(nfeatures=nfeatures)
        kind = "orb"
    kp, des = det.detectAndCompute(arr, None)
    return kind, kp, des


def _same_photo(cv2, np, H, pq, pr) -> bool:
    """A crop or resize of the same photograph maps by a pure scale + shift (no perspective, no rotation) with
    sub-pixel residuals; a second photo of the same room never does (new viewpoint = perspective change)."""
    if len(pq) < 50:
        return False
    H = H / H[2, 2]
    s = float(np.sqrt(abs(np.linalg.det(H[:2, :2]))))
    if s <= 0:
        return False
    proj = cv2.perspectiveTransform(pq.reshape(-1, 1, 2), H).reshape(-1, 2)
    err = float(np.median(np.linalg.norm(proj - pr, axis=1)))
    return bool(max(abs(H[2, 0]), abs(H[2, 1])) < 2e-5 and abs(H[0, 1]) < 0.005 * s and abs(H[1, 0]) < 0.005 * s
                and abs(H[0, 0] - H[1, 1]) < 0.01 * s and err < 0.25)


def _pairwise(cv2, np, kind: str, kq, dq, kr, dr) -> dict:
    """Ratio-test matches of two feature sets and their geometric consistency (planar and epipolar)."""
    res = {"method": kind, "keypoints": [len(kq), len(kr)], "matches": 0, "h_inliers": 0, "f_inliers": 0,
           "f_ratio": 0.0, "same_photo": False, "pairs": []}
    if dq is None or dr is None or len(kq) < 8 or len(kr) < 8:
        return res
    norm = cv2.NORM_L2 if kind == "sift" else cv2.NORM_HAMMING
    knn = cv2.BFMatcher(norm).knnMatch(dq, dr, k=2)
    ratio = 0.75 if kind == "sift" else 0.8
    good = [m[0] for m in knn if len(m) == 2 and m[0].distance < ratio * m[1].distance]
    res["matches"] = len(good)
    if len(good) < 8:
        return res
    pq = np.float32([kq[g.queryIdx].pt for g in good])
    pr = np.float32([kr[g.trainIdx].pt for g in good])
    best_pairs: list = []
    H, hm = cv2.findHomography(pq, pr, cv2.RANSAC, 5.0)
    if H is not None and hm is not None:
        keep = hm.ravel().astype(bool)
        denom = pq[keep] @ H[2, :2] + H[2, 2]
        orient = np.linalg.det(H) * denom             # > 0 everywhere: no reflection, no fold-over
        distinct = len({(round(float(x)), round(float(y))) for x, y in pr[keep]})
        if keep.sum() and np.all(np.isfinite(orient) & (orient > 0)) and distinct >= keep.sum() / 2:
            res["h_inliers"] = int(keep.sum())
            best_pairs = list(zip(pq[keep].tolist(), pr[keep].tolist()))
            res["same_photo"] = _same_photo(cv2, np, H, pq[keep], pr[keep])
    method = getattr(cv2, "USAC_MAGSAC", None) or cv2.FM_RANSAC
    try:
        F, fm = cv2.findFundamentalMat(pq, pr, method, 1.5, 0.999, 10000)
    except Exception:  # noqa: BLE001 - USAC missing in this build
        F, fm = cv2.findFundamentalMat(pq, pr, cv2.FM_RANSAC, 1.5, 0.999)
    if F is not None and fm is not None and F.shape == (3, 3):
        keep = fm.ravel().astype(bool)
        distinct = len({(round(float(x)), round(float(y))) for x, y in pr[keep]})
        if distinct >= keep.sum() / 2:
            res["f_inliers"] = int(keep.sum())
            res["f_ratio"] = round(res["f_inliers"] / max(1, len(good)), 3)
            if res["f_inliers"] > len(best_pairs):
                best_pairs = list(zip(pq[keep].tolist(), pr[keep].tolist()))
    res["pairs"] = best_pairs
    return res


def _score(d: dict) -> int:
    return max(d["h_inliers"], d["f_inliers"] if d["f_ratio"] >= 0.2 else 0)


def _spread(cv2, np, pts: list, size: tuple[int, int]) -> tuple[float, list[int] | None]:
    """Share of the image covered by the convex hull of the points, and their bounding box."""
    if len(pts) < 3:
        return 0.0, None
    a = np.float32(pts)
    hull = cv2.convexHull(a.reshape(-1, 1, 2))
    area = float(cv2.contourArea(hull))
    x0, y0 = a.min(axis=0)
    x1, y1 = a.max(axis=0)
    return round(area / max(1.0, float(size[0] * size[1])), 3), [int(x0), int(y0), int(x1), int(y1)]


class Matcher:
    """Local features of one query image (and of its mirror image), computed once and matched against as
    many reference images as needed. Raises ImportError when OpenCV or numpy is missing."""

    def __init__(self, q: Image.Image, max_side: int = 1200, nfeatures: int = 4000):
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        self.cv2, self.np = cv2, np
        self.size = q.size
        self.max_side, self.nfeatures = max_side, nfeatures
        qa, self.sq = _prep(q, max_side)
        self.qw = qa.shape[1]
        self.kind, self.kq, self.dq = _features(cv2, qa, nfeatures)
        _, self.kqm, self.dqm = _features(cv2, np.ascontiguousarray(qa[:, ::-1]), nfeatures)
        self.hashes = hashes(q)

    def score(self, r: Image.Image, max_side: int | None = None) -> dict:
        """Geometric agreement of the query with one reference; the better of direct and mirrored."""
        cv2, np = self.cv2, self.np
        ra, sr = _prep(r, max_side or self.max_side)
        kind, kr, dr = _features(cv2, ra, self.nfeatures)
        if kind != self.kind:                       # cannot happen within one OpenCV build
            return {"available": False, "note": "feature type mismatch"}
        direct = _pairwise(cv2, np, kind, self.kq, self.dq, kr, dr)
        mirror = _pairwise(cv2, np, kind, self.kqm, self.dqm, kr, dr)
        use_mirror = _score(mirror) > max(_score(direct), 0) * 1.5 and _score(mirror) >= SOME_H
        best = dict(mirror if use_mirror else direct)
        pairs = best["pairs"]
        if use_mirror:          # mirrored-query x back to the query's own pixels
            pairs = [((self.qw - 1 - a[0], a[1]), b) for a, b in pairs]
        best["pairs"] = [((a[0] / self.sq, a[1] / self.sq), (b[0] / sr, b[1] / sr)) for a, b in pairs]
        h, f, fr = best["h_inliers"], best["f_inliers"], best["f_ratio"]
        if h >= STRONG_H or (f >= STRONG_F and fr >= STRONG_RATIO):
            level = "strong"
        elif h >= SOME_H or (f >= SOME_F and fr >= 0.2):
            level = "some"
        else:
            level = "none"
        spread, box = _spread(cv2, np, [a for a, _ in best["pairs"]], self.size) if level != "none" else (0.0, None)
        keys = ("matches", "h_inliers", "f_inliers", "f_ratio", "same_photo")
        return {"available": True, "mirrored": use_mirror, "level": level, "inliers": _score(best),
                "spread": spread, "query_box": box, **best,
                "direct": {k: direct[k] for k in keys}, "mirror": {k: mirror[k] for k in keys}}

    def test(self, r: Image.Image, max_side: int | None = None) -> dict:
        """Both tests against one reference: {duplicate, geometric, cls, verdict}."""
        dup = duplicate_from(self.hashes, hashes(r))
        geo = self.score(r, max_side)
        return {"duplicate": dup, "geometric": geo, "cls": classify(dup, geo), "verdict": verdict(dup, geo)}


def geometric(q: Image.Image, r: Image.Image, max_side: int = 1200) -> dict:
    """Feature matching of query vs reference, and of the mirrored query vs the reference; the better one is
    reported (pairs are always in each image's own pixel coordinates)."""
    try:
        m = Matcher(q, max_side=max_side)
    except ImportError:
        return {"available": False, "note": "OpenCV/numpy missing (pip install opencv-python-headless): geometric "
                                            "test skipped"}
    return m.score(r, max_side)


def classify(dup: dict, geo: dict) -> str:
    """copy (same photograph) | same (strong agreement) | partial (some) | none | unchecked (no OpenCV)."""
    if dup.get("near_duplicate") or dup.get("mirrored_duplicate") or geo.get("same_photo"):
        return "copy"
    if not geo.get("available"):
        return "unchecked"
    return {"strong": "same", "some": "partial"}.get(geo.get("level"), "none")


def verdict(dup: dict, geo: dict) -> str:
    if dup.get("near_duplicate"):
        return ("NEAR-DUPLICATE: the same photograph (re-encoded or resized) - provenance: read the page it comes "
                "from; it cannot confirm itself")
    if dup.get("mirrored_duplicate"):
        return "MIRRORED COPY of the same photograph - provenance (a flipped repost), not a confirmation"
    if not geo.get("available"):
        return "no automatic test (OpenCV missing): compare invariant features by eye"
    if geo.get("same_photo"):
        return ("SAME PHOTOGRAPH" + (" (mirrored)" if geo.get("mirrored") else "") + ": a crop or resize of it (pure "
                "scale and shift, sub-pixel fit) - provenance: read the page it comes from; it cannot confirm itself")
    side = " against the MIRRORED photo (mirror-image room, or a flipped photo)" if geo.get("mirrored") else ""
    lv = geo["level"]
    nums = f"{geo['h_inliers']} planar / {geo['f_inliers']} epipolar inliers of {geo['matches']} matches"
    small = lv != "none" and geo.get("spread", 1.0) < SMALL_SPREAD
    where = (f"; the inliers cover only {geo.get('spread', 0) * 100:.0f}% of the photo: ONE SMALL OBJECT matches (a "
             "print, a screen, a logo, a product), which proves that object, not the room" if small else
             f"; inliers cover {geo.get('spread', 0) * 100:.0f}% of the photo")
    if lv == "strong":
        return (f"STRONG geometric agreement{side} ({nums}{where}). Open the inlier view: on fixed architecture "
                "(windows, ceiling, built-ins, the view) or venue-specific art it is site evidence; on chain furniture, "
                "carpet or mass-produced decor it proves the design, not the property")
    if lv == "some":
        return (f"SOME geometric agreement{side} ({nums}{where}): check where the inliers lie before counting it; "
                "repetitive textures produce chance inliers")
    return (f"no geometric agreement ({nums}): inconclusive - a different viewpoint, lens, renovation or season "
            "can do this; compare invariant features by eye")


def draw(q: Image.Image, r: Image.Image, pairs: list, height: int = 520, max_lines: int = 120) -> Image.Image:
    """Side-by-side view with the inlier correspondences drawn as lines (query left, reference right)."""
    sq, sr = height / q.height, height / r.height
    qv = q.convert("RGB").resize((max(1, round(q.width * sq)), height), Image.LANCZOS)
    rv = r.convert("RGB").resize((max(1, round(r.width * sr)), height), Image.LANCZOS)
    gap = 12
    canvas = Image.new("RGB", (qv.width + gap + rv.width, height), (24, 24, 28))
    canvas.paste(qv, (0, 0))
    canvas.paste(rv, (qv.width + gap, 0))
    d = ImageDraw.Draw(canvas)
    colours = [(255, 64, 64), (64, 220, 64), (64, 160, 255), (255, 200, 0), (255, 64, 255), (0, 230, 230)]
    step = max(1, len(pairs) // max_lines)
    for i, (a, b) in enumerate(pairs[::step][:max_lines]):
        x0, y0 = a[0] * sq, a[1] * sq
        x1, y1 = qv.width + gap + b[0] * sr, b[1] * sr
        c = colours[i % len(colours)]
        d.line([(x0, y0), (x1, y1)], fill=c, width=1)
        d.ellipse([x0 - 2, y0 - 2, x0 + 2, y0 + 2], outline=c)
        d.ellipse([x1 - 2, y1 - 2, x1 + 2, y1 + 2], outline=c)
    return canvas
