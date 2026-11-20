"""Visual similarity, used for one thing: the ORDER in which reference pictures are shown.

Feature matching (match.py) is a reliable positive and a useless negative: two photos of one room taken
years apart or from another corner score like unrelated rooms. A self-supervised image model is the
opposite instrument. It cannot prove that two pictures show the same place, but it ranks "this looks
like the same room" far better than the order a search engine returns. Measured on a real case (a hotel
bar; 3 photos of it among 12 look-alike bars from a reverse search): feature-match inliers put the real
photos at ranks 5, 8 and 14 of 15; this similarity puts them at ranks 1 to 3.

So `refs` and `revsearch` sort the pictures the feature test left unconfirmed by this similarity, most
alike first, and the agent compares the top of the sheet by eye. The number never classifies anything:
look-alikes score high too.

Model: DINOv2 ViT-S/14 (Meta AI, Apache-2.0), 8-bit ONNX export `Xenova/dinov2-small`, 24 MB. It is not
shipped with the skill: the first use downloads it from huggingface.co into the user cache
(`IGL_MODEL_DIR` overrides the folder) and checks its SHA-256. Needs `onnxruntime` and `numpy`. Without
them, without the download, or with `IGL_NO_EMBED=1`, callers keep the source's own order.

Score: both images are resized to 224x224 (whole frame), giving 16x16 patch tokens. For every patch of
one image take its best cosine match in the other, average the better half, in both directions. Matching
patches instead of one global vector keeps the score high when only part of the room is shared.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path

MODEL = {
    "name": "dinov2-small-q8.onnx",
    "url": "https://huggingface.co/Xenova/dinov2-small/resolve/c2bb04a51fab207c420665f1946016107bffc701/"
           "onnx/model_quantized.onnx",
    "sha256": "3afdc8bc63b50558d6e5770f5b799bb82455c2311183a2de43803f343a29d917",
    "bytes": 24_451_943,
    "what": "DINOv2 ViT-S/14 (Meta AI, Apache-2.0), ONNX export Xenova/dinov2-small",
}
SIDE = 224
_MEAN = (0.485, 0.456, 0.406)
_STD = (0.229, 0.224, 0.225)
_session = None                       # one model per process
_failed = ""                          # why the model could not be used (so a run asks only once)


def model_dir() -> Path:
    if os.environ.get("IGL_MODEL_DIR"):
        return Path(os.environ["IGL_MODEL_DIR"]).expanduser()
    base = os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")
    return Path(base) / "indoor-geolocator"


def model_path() -> Path:
    return model_dir() / MODEL["name"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def state() -> dict:
    """{state: ready | download | off | unavailable, note}: what `doctor` and `init` report."""
    if os.environ.get("IGL_NO_EMBED"):
        return {"state": "off", "note": "switched off (IGL_NO_EMBED is set)"}
    missing = [m for m in ("onnxruntime", "numpy") if importlib.util.find_spec(m) is None]
    if missing:
        return {"state": "unavailable", "note": f"{' and '.join(missing)} missing: pip install onnxruntime numpy"}
    if model_path().exists():
        return {"state": "ready", "note": f"model in {model_dir()}"}
    return {"state": "download", "note": f"model ({MODEL['bytes'] // 1_000_000} MB) is fetched from huggingface.co on "
                                         f"first use, into {model_dir()}"}


def ensure(http=None) -> Path | None:
    """The verified model file, downloading it once when `http` is given. None when it cannot be had."""
    global _failed
    p = model_path()
    if p.exists():
        return p
    if http is None or getattr(http, "dry", False) or _failed:
        return None
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        part = p.with_suffix(".part")
        if not http.download(MODEL["url"], part, max_bytes=MODEL["bytes"] + 1_000_000, retries=1, timeout=120):
            _failed = f"model download failed ({http.last_error or 'unreachable'})"
            return None
        if _sha256(part) != MODEL["sha256"]:
            part.unlink(missing_ok=True)
            _failed = "model download did not match its checksum"
            return None
        part.replace(p)
        return p
    except OSError as e:
        _failed = f"model could not be stored ({e})"
        return None


def why_not() -> str:
    """Why the last `similarities` call returned None ('' when it never failed)."""
    return _failed or state()["note"]


def _load(http=None):
    global _session, _failed
    if _session is not None:
        return _session
    if os.environ.get("IGL_NO_EMBED") or _failed:
        return None
    try:
        import onnxruntime as ort
    except ImportError:
        return None
    path = ensure(http)
    if path is None:
        return None
    try:
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = max(1, min(8, os.cpu_count() or 2))
        opts.log_severity_level = 3
        _session = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
    except Exception as e:  # noqa: BLE001 - a damaged file or an incompatible runtime: fall back to the source order
        _failed = f"model could not be loaded ({type(e).__name__})"
        return None
    return _session


def small(im):
    """The 224x224 RGB copy the model sees (the whole frame; the aspect ratio is not kept). Callers that
    rank many pictures keep these instead of the originals."""
    from PIL import Image
    return im if (im.size == (SIDE, SIDE) and im.mode == "RGB") else im.convert("RGB").resize((SIDE, SIDE), Image.BICUBIC)


def _pixels(im):
    import numpy as np
    a = np.asarray(small(im), dtype=np.float32) / 255.0
    return ((a - np.array(_MEAN, dtype=np.float32)) / np.array(_STD, dtype=np.float32)).transpose(2, 0, 1)


def _tokens(session, images: list) -> "object":
    """L2-normalised patch tokens, shape (n, 256, 384)."""
    import numpy as np
    out = session.run(None, {session.get_inputs()[0].name: np.stack([_pixels(im) for im in images])})[0][:, 1:]
    return out / (np.linalg.norm(out, axis=-1, keepdims=True) + 1e-9)


def patch_score(a, b, keep: float = 0.5) -> float:
    """Symmetric best-match similarity of two sets of normalised patch tokens (see the module docstring)."""
    import numpy as np
    s = a @ b.T
    fwd, back = np.sort(s.max(axis=1))[::-1], np.sort(s.max(axis=0))[::-1]
    return float((fwd[:max(1, int(len(fwd) * keep))].mean() + back[:max(1, int(len(back) * keep))].mean()) / 2)


def similarities(q, images: list, http=None, batch: int = 16) -> list[float | None] | None:
    """Similarity of each image to the query photo (roughly: below 0.5 not a comparable picture, 0.6-0.8
    another interior, 0.8 and more the same room from a similar side), None for entries that are None.
    Returns None when the model is not available: keep the source order."""
    session = _load(http)
    if session is None:
        return None
    qt = _tokens(session, [q])[0]
    out: list[float | None] = [None] * len(images)
    todo = [i for i, im in enumerate(images) if im is not None]
    for k in range(0, len(todo), batch):
        idx = todo[k:k + batch]
        for i, t in zip(idx, _tokens(session, [images[i] for i in idx])):
            out[i] = round(patch_score(qt, t), 3)
    return out
