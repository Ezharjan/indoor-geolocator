#!/usr/bin/env python3
r"""
build_skill_zip.py - keep indoor-geolocator.zip (the installable skill) identical to the folder indoor-geolocator/.

WHAT IT IS FOR
    indoor-geolocator/ (next to this file) is THE skill. Claude Code and other agents use the folder itself.
    claude.ai and the Claude desktop apps install a skill from a zip (Customize -> Skills -> Upload a skill), so
    indoor-geolocator.zip is kept next to the folder, ready to upload, and versioned with it. Run this script after
    every change to indoor-geolocator/: it rebuilds the zip only when the zip no longer matches the folder.

USAGE (any Python >= 3.9, standard library only)
    python build_skill_zip.py            build the zip if it is missing or out of date, then verify it
    python build_skill_zip.py --check    only verify (nothing is written); exit 1 if missing, out of date or invalid
    python build_skill_zip.py --force    rebuild even when the zip is up to date

WHAT THE ZIP CONTAINS
    One root folder indoor-geolocator/ with every file of indoor-geolocator/ (SKILL.md at indoor-geolocator/SKILL.md),
    sorted, deflate-compressed. Never included: __pycache__/, .pytest_cache/, .mypy_cache/, .ruff_cache/, .git/,
    .ipynb_checkpoints/, .work/, case folders (*-geolocation*), *.pyc, *.pyo, *.tmp, Thumbs.db, .DS_Store,
    desktop.ini. Entry times are the files' modification times; permissions are normalised to rw-r--r--.

WHAT IS VERIFIED (both modes)
    * SKILL.md starts with YAML front matter holding `name` (1-64 lower-case letters, digits, hyphens; equal to the
      folder name) and a non-empty `description` of at most 1024 characters - what the Claude apps require;
    * every file that SKILL.md and the references link to exists, and indoor-geolocator/LICENSE.txt equals LICENSE;
    * the zip opens, every entry passes its CRC check and lies under indoor-geolocator/ (no absolute path, no ..);
    * the zip holds exactly the files of the folder (none missing, none extra), each with the same SHA-256.
      A file that differs only in line endings (CRLF vs LF after a git checkout on Windows) is reported but does
      not make the zip out of date.
    The build writes indoor-geolocator.zip.tmp, verifies it, and only then replaces the zip (an interrupted run
    never leaves a broken zip). Nothing else is written; the skill folder is only read.

EXIT CODES
    0  the zip matches the folder (built now or already up to date)
    1  --check: the zip is missing, out of date or invalid; build: the new zip failed its verification
    2  the skill folder itself is invalid (front matter, broken links, LICENSE copy) - nothing is built
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
import zipfile
from pathlib import Path, PurePosixPath

__version__ = "2.0.0"

HERE = Path(__file__).resolve().parent
ROOT = "indoor-geolocator"                   # root folder inside the zip = the skill name
SRC = HERE / ROOT                            # the skill folder (source of truth)
ZIP = HERE / f"{ROOT}.zip"                   # the installable copy
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".ipynb_checkpoints", ".git", ".work"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".tmp"}
EXCLUDE_NAMES = {"Thumbs.db", ".DS_Store", "desktop.ini"}
NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def published_files(src: Path) -> list[str]:
    """Relative POSIX paths of the files of ``src`` that belong in the zip (sorted, deterministic)."""
    out = []
    for dp, dns, fns in os.walk(src):
        dns[:] = sorted(d for d in dns if d not in EXCLUDE_DIRS and "-geolocation" not in d)
        for f in sorted(fns):
            if f in EXCLUDE_NAMES or Path(f).suffix.lower() in EXCLUDE_SUFFIXES:
                continue
            out.append(Path(dp, f).relative_to(src).as_posix())
    return sorted(out)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def eol(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def front_matter(skill_md: Path) -> tuple[dict, list[str]]:
    """Top-level ``key: value`` pairs of the YAML front matter of SKILL.md and the problems found."""
    if not skill_md.is_file():
        return {}, [f"missing {skill_md}"]
    lines = skill_md.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0].strip() != "---" or "---" not in (ln.strip() for ln in lines[1:]):
        return {}, [f"{skill_md.name}: no YAML front matter (--- ... ---) at the top"]
    meta = {}
    for ln in lines[1:]:
        if ln.strip() == "---":
            break
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", ln)
        if m:
            meta[m[1]] = m[2].strip().strip("'\"")
    problems = []
    if not NAME_RE.match(meta.get("name", "")):
        problems.append(f"{skill_md.name}: `name` must be 1-64 lower-case letters, digits or hyphens "
                        f"(found {meta.get('name')!r})")
    elif meta["name"] != skill_md.parent.name:
        problems.append(f"{skill_md.name}: `name` {meta['name']!r} differs from the folder name {skill_md.parent.name!r}")
    if not meta.get("description"):
        problems.append(f"{skill_md.name}: `description` is missing or empty")
    elif len(meta["description"]) > 1024:
        problems.append(f"{skill_md.name}: `description` has {len(meta['description'])} characters (max. 1024)")
    elif "<" in meta["description"] or ">" in meta["description"]:
        problems.append(f"{skill_md.name}: `description` must not contain angle brackets")
    return meta, problems


def folder_problems(src: Path) -> list[str]:
    """Broken relative links in the skill's markdown, and the LICENSE copy."""
    problems = []
    for md in sorted(src.rglob("*.md")):
        if any(part in EXCLUDE_DIRS for part in md.parts):
            continue
        for target in LINK_RE.findall(md.read_text(encoding="utf-8")):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target):          # http:, https:, mailto: ...
                continue
            if not (md.parent / target).exists():
                problems.append(f"broken link in {md.relative_to(src).as_posix()}: {target}")
    lic, copy = HERE / "LICENSE", src / "LICENSE.txt"
    if lic.is_file() and (not copy.is_file() or eol(lic.read_bytes()) != eol(copy.read_bytes())):
        problems.append(f"{ROOT}/LICENSE.txt must be an exact copy of LICENSE (the zip ships without the repo root)")
    return problems


def tool_version(src: Path) -> str:
    p = src / "scripts" / "iglib" / "__init__.py"
    if p.is_file():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.startswith("__version__"):
                return ln.split("=", 1)[1].strip().strip("'\"")
    return "?"


def compare(src: Path, zip_path: Path) -> tuple[list[str], list[str]]:
    """(differences that make the zip out of date or invalid, files that differ only in line endings)."""
    if not zip_path.is_file():
        return [f"{zip_path.name} does not exist"], []
    problems, eol_only = [], []
    try:
        with zipfile.ZipFile(zip_path) as z:
            bad = z.testzip()
            if bad:
                return [f"{zip_path.name}: CRC error in {bad}"], []
            entries = {}
            for info in z.infolist():
                if info.is_dir():
                    continue
                p = PurePosixPath(info.filename)
                if p.is_absolute() or ".." in p.parts or p.parts[0] != ROOT or len(p.parts) < 2:
                    problems.append(f"{zip_path.name}: entry outside {ROOT}/: {info.filename}")
                    continue
                entries[PurePosixPath(*p.parts[1:]).as_posix()] = z.read(info)
    except (OSError, zipfile.BadZipFile) as e:
        return [f"{zip_path.name} cannot be read: {e}"], []
    files = published_files(src)
    for rel in files:
        if rel not in entries:
            problems.append(f"missing in the zip: {rel}")
            continue
        a, b = (src / rel).read_bytes(), entries[rel]
        if sha256(a) != sha256(b):
            same = eol(a) == eol(b)
            (eol_only if same else problems).append(f"{'line endings differ' if same else 'differs from the folder'}: {rel}")
    for rel in sorted(set(entries) - set(files)):
        problems.append(f"extra in the zip (no longer in the folder): {rel}")
    return problems, eol_only


def build(src: Path, zip_path: Path) -> int:
    """Write the zip to <zip>.tmp, verify it, then replace <zip>. Returns the number of files."""
    tmp = zip_path.with_name(zip_path.name + ".tmp")
    files = published_files(src)
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in files:
            p = src / rel
            t = time.localtime(max(p.stat().st_mtime, 315532800))          # ZIP times start in 1980
            info = zipfile.ZipInfo(f"{ROOT}/{rel}", date_time=t[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3                                         # Unix: honour the permissions below
            info.external_attr = (0o100644 & 0xFFFF) << 16
            z.writestr(info, p.read_bytes(), compresslevel=9)
    problems, _ = compare(src, tmp)
    if problems:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise RuntimeError("the new zip failed its verification:\n  " + "\n  ".join(problems))
    os.replace(tmp, zip_path)
    return len(files)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=f"Keep {ZIP.name} (the installable skill) identical to {ROOT}/.",
        epilog=f"Run it after every change to {ROOT}/. Details: the comment at the top of this file.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="only verify the zip (nothing is written); exit 1 if it is "
                                                        "missing, out of date or invalid")
    g.add_argument("--force", action="store_true", help="rebuild the zip even when it is up to date")
    a = ap.parse_args(argv)

    meta, fm_problems = front_matter(SRC / "SKILL.md")
    fm_problems += folder_problems(SRC)
    if fm_problems:
        for p in fm_problems:
            print(f"ERROR: {p}", file=sys.stderr)
        return 2
    existed = ZIP.is_file()
    problems, eol_only = compare(SRC, ZIP)
    action = "up to date"
    if not a.check and (problems or a.force):
        try:
            build(SRC, ZIP)
        except (OSError, RuntimeError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        action = ("built" if not existed else "rebuilt" if not problems
                  else f"rebuilt ({len(problems)} difference(s) to the previous zip)")
        problems, eol_only = compare(SRC, ZIP)
    for p in eol_only:
        print(f"note: {p} (git line-ending conversion; the skill is unaffected)")
    if problems:
        print(f"{ZIP.name} is NOT in sync with {ROOT}/ - run: python build_skill_zip.py", file=sys.stderr)
        for p in problems[:40]:
            print(f"  {p}", file=sys.stderr)
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more", file=sys.stderr)
        return 1
    n = len(published_files(SRC))
    print(f"{ZIP.name} {action}: skill `{meta['name']}` (tool {tool_version(SRC)}), {n} files, "
          f"{ZIP.stat().st_size / 1e6:.2f} MB, sha256 {sha256(ZIP.read_bytes())[:16]}...")
    print(f"  {ZIP}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
