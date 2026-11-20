"""Helpers shared by the command modules (commands.py, visual.py): HTTP clients tied to a case, grid/box
parsing, and the two ledger primitives every command uses (a method attempt, a clue)."""
from __future__ import annotations

import datetime as dt
import json

from . import imaging
from .case import Case
from .net import Http
from .util import IglError, parse_box, short, write_json


_DRY: list[Http] = []            # Http clients created under `geo --print-url` (their URLs are printed)


def _http(case: Case | None, service: str | None = None, timeout: float = 25.0, retries: int = 3,
          dry: bool = False) -> Http:
    if dry:
        h = Http(timeout=timeout, retries=0, dry=True)
        _DRY.append(h)
        return h
    if case is not None and service:
        svc = case.data["auto"].setdefault("services", [])
        if service not in svc:
            svc.append(service)
    return Http(cache_dir=(case.work / "cache") if case else None, timeout=timeout, retries=retries)


def _box_from(a, img_size, case: Case | None = None) -> tuple | None:
    if getattr(a, "box", None):
        return parse_box(a.box)
    if getattr(a, "cell", None):
        if case is None or "grid" not in case.data["image"]:
            raise IglError("--cell needs a case created by `igl.py init` (it defines the grid)")
        return imaging.cell_box(case.data["image"]["grid"], a.cell)
    if getattr(a, "rel", None):
        x0, y0, x1, y1 = (float(v) for v in a.rel.split(","))
        w, h = img_size
        return int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)
    return None


def _attempt(case: Case, method: str, status: str, detail: str, engine: str | None = None, query: str | None = None,
             url: str | None = None, files: list[str] | None = None, save: bool = True) -> str:
    aid = case.next_id("A")
    case.data["attempts"].append({"id": aid, "method": method, "status": status, "detail": detail, "engine": engine,
                                  "query": query, "url": url, "files": files or [], "time": dt.datetime.now()
                                  .astimezone().isoformat(timespec="seconds")})
    case.event("log", f"{aid} {method}{('/' + engine) if engine else ''}: {status} - {short(detail, 140)}", save=save)
    return aid


def _new_clue(case: Case, text: str, kind: str, status: str, source: str, files=None, box=None, url=None,
              resolves=None) -> str:
    cid = case.next_id("N")
    case.data["clues"][cid] = {"id": cid, "text": text, "kind": kind, "status": status, "source": source,
                               "files": files or [], "box": list(box) if box else None, "url": url,
                               "resolves": resolves or [], "time": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    case.event("note", f"{cid} [{status}/{source}] {short(text, 160)}")
    return cid


def _print_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def _save_json(case: Case | None, label: str, what: str, obj) -> str | None:
    if not case:
        return None
    eid, p = case.reserve_file(label, "json", what)
    write_json(p, obj)
    case.save()
    return eid
