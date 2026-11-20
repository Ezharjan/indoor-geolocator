"""The case folder and its ledger (case.json): the single source of truth of an investigation.

Layout of a case folder (nothing is ever written outside it):
    REPORT.md      final human report            (written by `igl.py report` / `finalize`)
    result.json    final machine-readable answer (written by `igl.py report` / `finalize`)
    case.json      the ledger: clues, candidates, evidence, exclusions, method attempts, answer, timeline
    input/         byte-exact copy of the photo + metadata.json
    evidence/      numbered artefacts cited by the ledger (E01_..., E02_...)
    .work/         scratch (tiles, variants, HTTP cache) - deleted by `igl.py finalize`
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import SCHEMA_CASE, __version__
from .util import IglError, now, read_json, slug, write_json

LEVELS = ["country", "region", "city", "district", "site", "room"]
LEVEL_HELP = {
    "country": "country or territory", "region": "state / province / prefecture", "city": "city or town",
    "district": "district / neighbourhood / campus / mall complex", "site": "a specific venue or building",
    "room": "a room, floor or unit inside the site",
}
# How a clue was obtained -> maximum likelihood ratio it may carry (rules as code: inferences can only rank)
STATUS_CAP = {"inferred": 3.0, "observed": 6.0, "reported": 10.0, "metadata": 20.0, "traced": 20.0,
              "read": 50.0, "computed": 50.0, "matched": 100.0}
STATUS_HELP = {
    "inferred": "reasoning or style judgement (\"looks Scandinavian\")",
    "observed": "a feature you can point at in the image (\"Type G socket\")",
    "reported": "a third party says so (web caption, listing, engine label, unverified OCR)",
    "metadata": "embedded in the file (EXIF GPS/time, XMP/IPTC location) - editable, so corroborate",
    "traced": "the SAME photograph found on a page that says where it was taken (a COPY's caption, listing, tag)",
    "read": "text in the image that you verified on a zoomed crop",
    "computed": "deterministic result of a tool or table (QR decode, phone prefix, sun angle)",
    "matched": "same physical place confirmed against independent reference imagery (>=3 invariant features)",
}
GRADE = {"matched": "A", "read": "A", "computed": "A", "metadata": "B", "traced": "B", "observed": "B",
         "reported": "C", "inferred": "D"}
# A reverse-image engine's label, or the title of a "similar" image, is a lead whatever it sounds like: engines
# list look-alikes beside real matches. Its weight stays small until the place is verified another way.
SOURCE_CAP = {"engine": 3.0}
DECISIVE = {"read", "computed", "matched", "metadata", "traced"}     # identify a place when LR >= 10
EXCLUDERS = {"read", "computed", "matched"}                 # may exclude a candidate outright
SOURCES = {
    "image": "visual content of the photo", "text": "text visible in the photo", "metadata": "file metadata",
    "table": "offline standards tables (data/countries.json etc.)", "web": "web pages, captions, listings",
    "engine": "reverse-image / AI engines (machine guesses)", "map": "OSM, geocoders, map data",
    "reference": "independent reference photos of a candidate", "geometry": "sun / geometry computation",
    "user": "hints given by the user",
}
KINDS = ["hypothesis", "scene", "metadata", "text", "code", "standard", "architecture", "style", "product",
         "culture", "personal-item", "language", "window-view", "light-time", "provenance", "match",
         "negative", "contradiction", "context", "other"]
CORE_METHODS = {
    "metadata": "EXIF / XMP / IPTC / thumbnail / filename / provenance markers",
    "visual_sweep": "systematic zone-by-zone inspection of the whole frame (tiles + crops)",
    "text_ocr": "all text: OCR passes + your own zoomed reading",
    "codes": "QR codes and barcodes",
    "standards": "fixed standards (sockets, switches, plumbing, safety signs, units) -> country set",
    "culture_style": "language/script, brands/products, decor/style/patterns, customs, personal items",
    "reverse_search": "reverse image search: >=2 engines (`revsearch`: Yandex, TinEye, Baidu; Google Lens and Bing "
                      "through a browser tool and the by-URL links) on the full image and on tight crops",
    "text_search": "web search of distinctive strings / descriptions in the local language(s)",
    "social_search": "social media and community photos: open APIs, site: queries, platform search (place only)",
    "candidate_enum": "enumerate every candidate of the identified category (all branches, all hotels...)",
    "reference_match": "compare the top candidates AND a rival against independent reference imagery (`refs`, "
                       "`compare`)",
    "window_view": "exterior view through windows/doors/reflections (or not_applicable)",
    "consistency": "final consistency check (time zone, season, sun, language, standards) + one re-run",
}
OPTIONAL_METHODS = {
    "provenance_hunt": "find where the photo was published (watermarks, captions, photographer)",
    "listing_search": "hotel / rental / real-estate / review listings",
    "map_photos": "photos of a candidate on maps, Commons, Flickr, 360 tours",
    "sun_light": "sun direction through windows vs facade orientation",
    "wifi_ssid": "Wi-Fi network names (WiGLE, needs the user's key)",
    "ai_estimate": "AI geolocation estimators (hints only)",
    "other": "anything else (describe it)",
}
ATTEMPT_STATUS = {
    "results": "the method worked and produced relevant findings",
    "no_results": "the method worked but found nothing relevant",
    "blocked": "the service refused (CAPTCHA, 403, login wall)",
    "unavailable": "tool, network or credentials missing",
    "not_applicable": "the method does not apply to this photo (say why)",
    "skipped": "deliberately not done (say why)",
}
RESOLVED = {"results", "no_results", "not_applicable"}
# Methods whose work is visible in the clues themselves need no separate `log` call.
IMPLIED_BY_KIND = {"standards": {"standard"}, "culture_style": {"style", "culture", "language", "product"},
                   "window_view": {"window-view"}}


class Case:
    def __init__(self, root: Path):
        root = Path(root).expanduser().resolve()
        if root.is_file() and root.name == "case.json":
            root = root.parent
        self.root = root
        self.path = root / "case.json"
        if not self.path.exists():
            raise IglError(f"No case at {root}: run `igl.py init <image>` first (or pass the case folder path).")
        self.data = read_json(self.path)
        if self.data.get("schema") != SCHEMA_CASE:
            raise IglError(f"{self.path} is not an {SCHEMA_CASE} ledger")

    # ------------------------------------------------------------------ creation
    @classmethod
    def create(cls, image: Path, out: Path | None = None, parent: Path | None = None) -> "Case":
        image = Path(image).expanduser().resolve()
        if not image.is_file():
            raise IglError(f"Image not found: {image}")
        if out is None:
            parent = Path(parent) if parent else default_parent(image)
            base = f"{slug(image.stem, 48)}-geolocation"
            out = parent / base
            n = 2
            while out.exists():
                out = parent / f"{base}-{n}"
                n += 1
        out = Path(out).expanduser().resolve()
        if out.exists() and any(out.iterdir()):
            raise IglError(f"{out} already exists and is not empty: pick another --out (an existing case is never "
                           "overwritten).")
        (out / "input").mkdir(parents=True, exist_ok=True)
        (out / "evidence").mkdir(exist_ok=True)
        dst = out / "input" / image.name
        shutil.copy2(image, dst)
        data = {
            "schema": SCHEMA_CASE, "tool_version": __version__, "created": now(), "updated": now(),
            "image": {"original_path": str(image), "file": f"input/{image.name}"},
            "counters": {"E": 0, "N": 0, "C": 0, "V": 0, "A": 0},
            "files": {}, "clues": {}, "candidates": {}, "evidence": [], "exclusions": [],
            "attempts": [], "answer": None, "timeline": [], "auto": {},
        }
        write_json(out / "case.json", data)
        c = cls(out)
        c.event("init", f"case created for {image.name}")
        return c

    # ------------------------------------------------------------------ persistence
    def save(self) -> None:
        self.data["updated"] = now()
        write_json(self.path, self.data)

    def event(self, kind: str, text: str, save: bool = True) -> None:
        self.data["timeline"].append({"t": now(), "event": kind, "text": text})
        if save:
            self.save()

    def next_id(self, prefix: str) -> str:
        self.data["counters"][prefix] = self.data["counters"].get(prefix, 0) + 1
        n = self.data["counters"][prefix]
        return f"{prefix}{n:02d}" if prefix == "E" else f"{prefix}{n}"

    # ------------------------------------------------------------------ paths
    @property
    def image_path(self) -> Path:
        return self.root / self.data["image"]["file"]

    @property
    def work(self) -> Path:
        p = self.root / ".work"
        p.mkdir(exist_ok=True)
        return p

    @property
    def evidence_dir(self) -> Path:
        p = self.root / "evidence"
        p.mkdir(exist_ok=True)
        return p

    def reserve_file(self, label: str, ext: str, what: str, pinned: bool = False, tool: str | None = None,
                     meta: dict | None = None) -> tuple[str, Path]:
        """Allocate the next evidence id and path (E07_<label>.<ext>); the caller writes the file. `tool`
        names the command that produced it (compare, refs, revsearch): a `matched` clue must cite such a
        file, and `meta` keeps what the check needs (e.g. the id of the JSON behind a sheet)."""
        eid = self.next_id("E")
        name = f"{eid}_{slug(label, 40)}.{ext.lstrip('.')}"
        rec = {"path": f"evidence/{name}", "what": what, "created": now(), "pinned": pinned}
        if tool:
            rec["tool"] = tool
        if meta:
            rec["meta"] = meta
        self.data["files"][eid] = rec
        return eid, self.evidence_dir / name

    def import_file(self, src: Path, label: str, what: str) -> str:
        src = Path(src).expanduser().resolve()
        if not src.is_file():
            raise IglError(f"File not found: {src}")
        try:                                    # already inside evidence/: register it, don't copy
            rel = src.relative_to(self.root)
            for eid, f in self.data["files"].items():
                if f["path"] == rel.as_posix():
                    return eid
        except ValueError:
            pass
        eid, dst = self.reserve_file(label or src.stem, src.suffix or ".bin", what)
        shutil.copy2(src, dst)
        return eid

    def resolve_files(self, refs: list[str] | None, label: str = "", what: str = "") -> list[str]:
        """Accept evidence ids (E07) or file paths; paths outside evidence/ are copied in. Returns ids."""
        ids = []
        for r in refs or []:
            for part in [p.strip() for p in str(r).split(",") if p.strip()]:
                key = part.upper()
                if key in self.data["files"]:
                    if not (self.root / self.data["files"][key]["path"]).exists():
                        raise IglError(f"{key} is registered but its file is missing")
                    ids.append(key)
                    continue
                p = Path(part)
                if not p.is_absolute() and (self.root / p).exists():
                    p = self.root / p
                if not p.exists():
                    raise IglError(f"Unknown evidence reference {part!r}: give an id like E07 or a file path")
                ids.append(self.import_file(p, label or p.stem, what or f"imported {p.name}"))
        return ids

    def file_path(self, eid: str) -> Path:
        f = self.data["files"].get(eid.upper())
        if not f:
            raise IglError(f"No evidence file {eid}")
        return self.root / f["path"]

    # ------------------------------------------------------------------ lookups
    def clue(self, cid: str) -> dict:
        c = self.data["clues"].get(cid.upper())
        if not c:
            raise IglError(f"No clue {cid} (clues: {', '.join(list(self.data['clues'])[-12:]) or 'none'})")
        return c

    def cand(self, cid: str) -> dict:
        key = cid.strip()
        if key.upper() in self.data["candidates"]:
            return self.data["candidates"][key.upper()]
        hits = [c for c in self.data["candidates"].values() if c["name"].lower() == key.lower()]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise IglError(f"{cid!r} matches several candidates ({', '.join(h['id'] for h in hits)}): use the id")
        raise IglError(f"No candidate {cid!r} (candidates: "
                       f"{', '.join(c['id'] + '=' + c['name'] for c in list(self.data['candidates'].values())[-10:]) or 'none'})")

    def children(self, cid: str) -> list[dict]:
        return [c for c in self.data["candidates"].values() if c.get("parent") == cid]

    def descendants(self, cid: str) -> list[dict]:
        out, todo = [], [cid]
        while todo:
            cur = todo.pop()
            for k in self.children(cur):
                out.append(k)
                todo.append(k["id"])
        return out

    def ancestors(self, cid: str) -> list[dict]:
        out, cur = [], self.data["candidates"].get(cid)
        seen = set()
        while cur and cur.get("parent") and cur["parent"] not in seen:
            seen.add(cur["parent"])
            cur = self.data["candidates"].get(cur["parent"])
            if cur:
                out.append(cur)
        return out

    def is_excluded(self, cid: str) -> bool:
        c = self.data["candidates"].get(cid)
        if not c:
            return False
        if c.get("status") == "excluded":
            return True
        return any(a.get("status") == "excluded" for a in self.ancestors(cid))

    def sites_examined(self) -> set[str]:
        """Venues whose reference imagery was looked at: `refs` / `compare` ran for them (--for) and fetched
        pictures, or a clue of the `reference` lineage speaks for or against them (a comparison made in a
        browser tool is recorded that way)."""
        cands, clues = self.data["candidates"], self.data["clues"]
        out = {cid for cid, c in cands.items()
               if c["level"] == "site" and any(r.get("compared") for r in c.get("refs") or [])}
        links = [(e["candidate"], e["clue"]) for e in self.data["evidence"]] + \
                [(x["candidate"], x["clue"]) for x in self.data["exclusions"]]
        for cid, clue in links:
            if cands.get(cid, {}).get("level") == "site" and clues.get(clue, {}).get("source") == "reference":
                out.add(cid)
        return out

    def rivals_compared(self, cid: str) -> list[dict]:
        """The negative control of a venue match: OTHER venues whose reference imagery was examined. A rival
        that was compared and then excluded still counts."""
        c = self.data["candidates"].get(cid)
        if not c:
            return []
        site = c if c["level"] == "site" else next((x for x in self.ancestors(cid) if x["level"] == "site"), c)
        return [self.data["candidates"][x] for x in sorted(self.sites_examined() - {site["id"]})]

    def match_controlled(self, cid: str) -> bool:
        """Whether a reference match recorded for this candidate has its control. For a venue or a room: a
        rival venue went through the same comparison. For an area or a group (a design match): the
        reference photos of at least two venues were examined."""
        c = self.data["candidates"].get(cid)
        if not c:
            return False
        if c["level"] in ("site", "room"):
            return bool(self.rivals_compared(cid))
        return len(self.sites_examined()) >= 2

    def method_state(self) -> dict[str, dict]:
        """Per method: best status over its attempts (results > no_results > not_applicable > blocked > ...)."""
        order = ["results", "no_results", "not_applicable", "blocked", "unavailable", "skipped"]
        state: dict[str, dict] = {}
        for a in self.data["attempts"]:
            m = a["method"]
            cur = state.get(m)
            if cur is None or order.index(a["status"]) < order.index(cur["status"]):
                state[m] = {"status": a["status"], "detail": a.get("detail", ""), "n": 0}
            state[m]["n"] = state[m].get("n", 0) + 1
        for m, kinds in IMPLIED_BY_KIND.items():        # recorded clues already show that the method was done
            if state.get(m, {}).get("status") in RESOLVED:
                continue
            ids = [cid for cid, c in self.data["clues"].items() if c.get("kind") in kinds]
            if ids:
                state[m] = {"status": "results", "detail": f"shown by clue(s) {', '.join(ids[:8])}",
                            "n": state.get(m, {}).get("n", 0), "implied": True}
        return state

    def referenced_files(self) -> set[str]:
        refs = set()
        for c in self.data["clues"].values():
            refs.update(c.get("files", []))
        for c in self.data["candidates"].values():
            refs.update(c.get("files", []))
        for e in self.data["evidence"]:
            refs.update(e.get("files", []))
        for x in self.data["exclusions"]:
            refs.update(x.get("files", []))
        for a in self.data["attempts"]:
            refs.update(a.get("files", []))
        if self.data.get("answer"):
            refs.update(self.data["answer"].get("files", []))
        refs.update(k for k, f in self.data["files"].items() if f.get("pinned"))
        return refs


def default_parent(image: Path) -> Path:
    """Where a new case folder goes when --out is not given.

    claude.ai / Cowork sandboxes: /mnt/user-data/outputs (the user sees it). Otherwise the current
    working directory - never the skill folder and never a read-only uploads folder.
    """
    outputs = Path("/mnt/user-data/outputs")
    if outputs.is_dir() and _writable(outputs):
        return outputs
    cwd = Path.cwd()
    if _writable(cwd):
        return cwd
    if _writable(image.parent):
        return image.parent
    raise IglError("No writable place for the case folder: pass --out <folder>.")


def _writable(p: Path) -> bool:
    try:
        test = p / ".igl_write_test"
        test.write_text("x")
        test.unlink()
        return True
    except OSError:
        return False
