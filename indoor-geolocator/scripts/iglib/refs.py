"""Reference imagery: get many photos of a candidate place (or of every venue of a kind in an area) and let
the machine sort them against the query photo before anyone looks.

Why this exists: a venue is only identified when the photo matches INDEPENDENT pictures of it. Finding
two image URLs by hand is slow, and "it looks similar" is how wrong answers are made. So:

  collect()        image search by text on keyless engines (Brave, Startpage) and/or every picture on given
                   pages (a hotel's gallery, a listing), through one headless browser session;
  rank_against()   download the thumbnails in parallel, drop repeats of one photograph, and score each
                   reference against the query with match.Matcher (near-duplicate + SIFT/RANSAC), refining
                   the best ones on their full-size originals;
  ranked_sheets()  numbered contact sheets in rank order, the query photo first, a coloured frame per class.

The classes: COPY (the same photograph: provenance), SAME SCENE (strong geometric agreement), PARTIAL
(some), unconfirmed (the feature test found nothing - which it also does for genuine photos of the same
room taken at another time or angle, so unconfirmed items are judged by eye on the sheet, in the order the
source returned them). The same functions sort reverse-image-search results in `revsearch`.

Search engines change their pages and refuse automated clients at times: every provider run ends as
results / no_results / blocked / unavailable, and a blocked provider is never retried in a loop.
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from PIL import Image, ImageDraw

from . import embed, imaging, match
from .net import fetch_many
from .util import redact

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")
PROVIDERS = ("brave", "startpage")
WALL = re.compile(r"(?i)captcha|verify (?:that )?you are (?:a )?human|are you a robot|not a robot|unusual traffic|"
                  r"access denied|request blocked|enable javascript and cookies|pardon our interruption|"
                  r"checking your browser|security check")
FRAME = {"copy": (70, 140, 255), "same": (60, 210, 90), "partial": (240, 200, 40), "none": (110, 110, 118),
         "unchecked": (110, 110, 118), "missing": (60, 60, 66)}


def site_of(url: str) -> str:
    host = urlparse(url or "").netloc.lower().split(":")[0]
    for pre in ("www.", "m.", "mobile."):
        if host.startswith(pre) and host.count(".") > 1:
            return host[len(pre):]
    return host


def available() -> tuple[bool, str]:
    import importlib.util
    if importlib.util.find_spec("playwright") is None:
        return False, "Python package `playwright` not installed (pip install playwright && playwright install chromium)"
    return True, ""


# ----------------------------------------------------------------------------- providers (headless)
def brave_original(thumb: str) -> str:
    """Brave's image proxy carries the original URL base64-encoded in the thumbnail path."""
    m = re.search(r"/g:[a-z]+/(.+)$", thumb or "")
    if not m:
        return ""
    b64 = m.group(1).split("?")[0].replace("/", "")
    try:
        out = base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""
    return out if out.startswith(("http://", "https://")) else ""


def parse_brave(cards: list[dict], html: str) -> list[dict]:
    """Cards read from the DOM (thumb, alt, site) + the page URLs embedded in the page's data script."""
    pages = {}
    for m in re.finditer(r'url:"(https?://[^"]+)"(?:(?!url:").){0,2000}?thumbnail:\{src:"([^"]+)"', html or "", re.S):
        pages.setdefault(m.group(2), m.group(1))
    out = []
    for c in cards:
        thumb = c.get("thumb") or ""
        if not thumb.startswith("http"):
            continue
        image = brave_original(thumb)
        page = pages.get(thumb, "")
        out.append({"title": redact((c.get("alt") or "").strip())[:160], "page": page, "image": image, "thumb": thumb,
                    "site": (c.get("site") or "").strip() or site_of(page or image), "provider": "brave"})
    return out


def parse_startpage(html: str) -> list[dict]:
    """Startpage embeds its image results as JSON objects with rawImageUrl / altClickUrl / title."""
    out, seen = [], set()
    for m in re.finditer(r'\{[^{}]*"rawImageUrl":"[^"]+"[^{}]*\}', html or ""):
        try:
            d = json.loads(m.group(0))
        except ValueError:
            continue
        image = d.get("rawImageUrl") or ""
        if not image.startswith("http") or image in seen:
            continue
        seen.add(image)
        thumb = d.get("thumbnailUrl") or d.get("clickUrl") or ""
        if thumb.startswith("/"):
            thumb = "https://www.startpage.com" + thumb
        page = d.get("altClickUrl") or ""
        out.append({"title": redact(str(d.get("title") or "").strip())[:160], "page": page, "image": image,
                    "thumb": thumb, "site": site_of(page or image), "provider": "startpage"})
    return out


async def _body_text(page) -> str:
    try:
        return await page.evaluate("document.body ? document.body.innerText : ''")
    except Exception:  # noqa: BLE001
        return ""


async def _brave(ctx, q: str, limit: int) -> dict:
    page = await ctx.new_page()
    try:
        await page.goto("https://search.brave.com/images?q=" + quote_plus(q), wait_until="domcontentloaded",
                        timeout=40000)
        await page.wait_for_timeout(3000)
        for _ in range(2 if limit > 40 else 1):
            await page.evaluate("window.scrollBy(0, 6000)")
            await page.wait_for_timeout(900)
        cards = await page.evaluate("""() => [...document.querySelectorAll('button.image-result, .image-result')].map(b => {
            const im = b.querySelector('.image-wrapper img') || b.querySelector('img');
            const site = b.querySelector('.image-metadata-site');
            return {thumb: im ? (im.currentSrc || im.src || '') : '', alt: im ? (im.alt || '') : '',
                    site: site ? site.innerText.trim() : ''}; })""")
        items = parse_brave(cards, await page.content())[:limit]
        if items:
            return {"status": "results", "items": items}
        txt = await _body_text(page)
        if WALL.search(txt[:1500]) or "captcha" in page.url.lower():
            return {"status": "blocked", "items": [], "note": "Brave asked for verification (not bypassed)"}
        return {"status": "no_results" if len(txt.strip()) > 40 else "unavailable", "items": [],
                "note": "" if len(txt.strip()) > 40 else "the page did not load (network or proxy)"}
    finally:
        await page.close()


async def _startpage(ctx, q: str, limit: int) -> dict:
    page = await ctx.new_page()
    try:
        await page.goto("https://www.startpage.com/sp/search?query=" + quote_plus(q) + "&cat=images",
                        wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(3000)
        items = parse_startpage(await page.content())[:limit]
        if items:
            return {"status": "results", "items": items}
        txt = await _body_text(page)
        if WALL.search(txt[:1500]):
            return {"status": "blocked", "items": [], "note": "Startpage asked for verification (not bypassed)"}
        return {"status": "no_results" if len(txt.strip()) > 40 else "unavailable", "items": [],
                "note": "" if len(txt.strip()) > 40 else "the page did not load (network or proxy)"}
    finally:
        await page.close()


_HARVEST_JS = """(minSide) => {
  const out = new Map();
  const abs = u => { try { return new URL(u, location.href).href; } catch (e) { return ''; } };
  const add = (u, alt, w, h) => {
    u = abs(u || '');
    if (!/^https?:/.test(u) || /\\.(svg|gif)(\\?|$)/i.test(u)) return;
    const cur = out.get(u);
    if (!cur || (w * h) > (cur.w * cur.h)) out.set(u, {url: u, alt: (alt || '').trim().slice(0, 160), w: w || 0, h: h || 0});
  };
  const largest = ss => { let best = '', bw = -1;
    for (const part of (ss || '').split(',')) { const [u, d] = part.trim().split(/\\s+/); const n = parseFloat(d) || 1;
      if (u && n > bw) { bw = n; best = u; } } return best; };
  for (const im of document.querySelectorAll('img')) {
    const w = im.naturalWidth || parseInt(im.getAttribute('width')) || 0, h = im.naturalHeight || parseInt(im.getAttribute('height')) || 0;
    const lazy = im.getAttribute('data-src') || im.getAttribute('data-lazy-src') || im.getAttribute('data-original') ||
                 im.getAttribute('data-lazy') || largest(im.getAttribute('data-srcset'));
    const big = largest(im.getAttribute('srcset'));
    const u = big || lazy || im.currentSrc || im.src;
    if ((w && w < minSide) || (h && h < minSide * 0.6)) { if (!lazy && !big) continue; }
    add(u, im.alt || im.title, w, h);
  }
  for (const s of document.querySelectorAll('picture source[srcset]')) add(largest(s.getAttribute('srcset')), '', 0, 0);
  for (const a of document.querySelectorAll('a[href]')) if (/\\.(jpe?g|png|webp)(\\?|$)/i.test(a.getAttribute('href'))) add(a.getAttribute('href'), a.title || a.innerText, 0, 0);
  let n = 0;
  for (const el of document.querySelectorAll('[style*="background"], [data-bg], [data-background-image]')) {
    if (++n > 1500) break;
    const m = /url\\(["']?([^"')]+)["']?\\)/.exec(el.getAttribute('style') || '');
    const u = (m && m[1]) || el.getAttribute('data-bg') || el.getAttribute('data-background-image');
    const r = el.getBoundingClientRect();
    if (u && r.width >= minSide && r.height >= minSide * 0.6) add(u, el.getAttribute('aria-label') || '', Math.round(r.width), Math.round(r.height));
  }
  const og = document.querySelector('meta[property="og:image"]');
  if (og && og.content) add(og.content, document.title, 0, 0);
  return {title: document.title || '', items: [...out.values()]};
}"""


async def _page_images(ctx, url: str, limit: int, min_side: int = 200) -> dict:
    """Every sizeable picture on one page (img/srcset/lazy attributes, linked image files, CSS backgrounds,
    og:image), after scrolling so lazy galleries load."""
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2500)
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, Math.max(1200, window.innerHeight * 1.5))")
            await page.wait_for_timeout(700)
        data = await page.evaluate(_HARVEST_JS, min_side)
        items = [{"title": redact(i.get("alt") or data.get("title") or "")[:160], "page": url, "image": i["url"],
                  "thumb": "", "site": site_of(url), "provider": "page", "w": i.get("w"), "h": i.get("h")}
                 for i in data.get("items", [])]
        items.sort(key=lambda i: -((i.get("w") or 0) * (i.get("h") or 0)))
        txt = await _body_text(page)
        if len(items) < 3 and WALL.search(txt[:2000]):
            return {"status": "blocked", "items": [], "note": "the site showed a bot wall (not bypassed): open it in "
                                                              "your browser tool, or use an image search instead",
                    "title": data.get("title", "")}
        if not items:
            return {"status": "no_results" if len(txt.strip()) > 40 else "unavailable", "items": [],
                    "note": "no sizeable pictures found on the page" if len(txt.strip()) > 40 else
                            "the page did not load (network or proxy)", "title": data.get("title", "")}
        return {"status": "results", "items": items[:limit], "title": data.get("title", "")}
    finally:
        await page.close()


async def _collect(queries: list[str], urls: list[str], providers: list[str], per_query: int, per_page: int) -> dict:
    from playwright.async_api import async_playwright
    runs, items = [], []
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        except Exception as e:  # noqa: BLE001
            msg = str(e).splitlines()[0][:160]
            return {"runs": [{"kind": "browser", "status": "unavailable",
                              "note": f"Chromium could not start ({msg}); try `playwright install chromium`"}],
                    "items": []}
        ctx = await browser.new_context(user_agent=UA, locale="en-US", viewport={"width": 1366, "height": 900})

        async def run(kind: str, name: str, target: str, coro) -> None:
            t0 = time.time()
            try:
                res = await coro
            except Exception as e:  # noqa: BLE001 - DNS failure, proxy refusal, timeout, layout change
                first = str(e).splitlines()[0][:140] if str(e) else ""
                res = {"status": "unavailable", "items": [], "note": f"{type(e).__name__}: {first}"}
            for it in res["items"]:
                it["query" if kind == "search" else "from_page"] = target
            items.extend(res["items"])
            runs.append({"kind": kind, "provider": name, "target": target, "status": res["status"],
                         "n": len(res["items"]), "note": res.get("note", ""), "seconds": round(time.time() - t0, 1)})

        fn = {"brave": _brave, "startpage": _startpage}
        blocked: set[str] = set()
        for q in queries:
            for name in providers:
                if name in blocked:                # a provider that refused once is not asked again this run
                    continue
                await run("search", name, q, fn[name](ctx, q, per_query))
                if runs[-1]["status"] == "blocked":
                    blocked.add(name)
            await asyncio.sleep(0.8)               # human pace between queries
        for u in urls:
            await run("page", "page", u, _page_images(ctx, u, per_page))
        await browser.close()
    return {"runs": runs, "items": items}


def collect(queries: list[str], urls: list[str], providers: list[str] | None = None, per_query: int = 40,
            per_page: int = 60) -> dict:
    """{runs: [{kind, provider, target, status, n, note}], items: [{title, page, image, thumb, site, provider}]}."""
    providers = [p for p in (providers or list(PROVIDERS)) if p in PROVIDERS]
    ok, why = available()
    if not ok:
        return {"runs": [{"kind": "browser", "provider": "-", "target": "-", "status": "unavailable", "n": 0,
                          "note": why}], "items": []}
    return asyncio.run(_collect(queries, urls, providers, per_query, per_page))


def interleave(items: list[dict]) -> list[dict]:
    """Round-robin over the sources (each search on each provider, each page, the given images), keeping
    every source's own order: a cap on the total then keeps the top results of all of them instead of
    everything from the first search and nothing from the last."""
    groups: dict[tuple, list[dict]] = {}
    for it in items:
        groups.setdefault((it.get("provider"), it.get("query") or it.get("from_page") or ""), []).append(it)
    out, k = [], 0
    while True:
        row = [g[k] for g in groups.values() if k < len(g)]
        if not row:
            return out
        out.extend(row)
        k += 1


def dedupe_urls(items: list[dict]) -> list[dict]:
    """One entry per image URL (the first occurrence wins; a later one may add the page or title)."""
    seen: dict[str, dict] = {}
    out = []
    for it in items:
        key = (it.get("image") or it.get("thumb") or it.get("file") or "").split("#")[0]
        if not key:
            continue
        if key in seen:
            first = seen[key]
            for k in ("page", "title", "thumb"):
                if not first.get(k) and it.get(k):
                    first[k] = it[k]
            continue
        seen[key] = it
        out.append(it)
    return out


# ----------------------------------------------------------------------------- ranking against the query
def _open(path: Path) -> Image.Image | None:
    try:
        im = Image.open(path)
        im.load()
        if im.width < 48 or im.height < 48:
            return None
        return imaging.flatten(im)
    except Exception:  # noqa: BLE001 - HTML error page, truncated file, unsupported format
        return None


def rank_against(q: Image.Image, items: list[dict], work: Path, http=None, refine: int = 6, workers: int = 6,
                 start: int = 1, max_side: int = 1100) -> dict:
    """Score every item against the query. Adds to each item: n (its number, from `start`), cls, inliers,
    h_inliers, f_inliers, spread, mirrored, sim (visual similarity, when the model is available), local
    (file used), same_as (number of an earlier item showing the same photograph). Items are re-ordered:
    confirmed classes first, then the unconfirmed ones, most similar first. Returns counts per class.

    Download order per item: the thumbnail (served by the search engine, small but reliable), else the
    original image; items flagged `prefer_full` (gallery pages, engine "pages": few and worth the detail)
    try the original first and fall back to the thumbnail."""
    work.mkdir(parents=True, exist_ok=True)
    for n, it in enumerate(items, start):
        it["n"] = n
        it.setdefault("cls", "missing")
    first, second = [], []
    for it in items:
        order = [it.get("image"), it.get("thumb")] if it.get("prefer_full") else [it.get("thumb"), it.get("image")]
        order = [u for u in order if u]
        first.append("" if it.get("file") else (order[0] if order else ""))
        second.append("" if it.get("file") else (order[1] if len(order) > 1 else ""))
    got = fetch_many(http, first, work / "a", workers=workers)
    retry = [i for i in range(len(items)) if i not in got and second[i]]
    alt = fetch_many(http, [second[i] for i in retry], work / "b", workers=workers) if retry else {}
    try:
        matcher = match.Matcher(q, max_side=max_side)
    except ImportError:
        matcher = None
    qh = match.hashes(q)
    seen: list[tuple[int, dict]] = []
    alt_by_item = {retry[k]: path for k, path in alt.items()}
    smalls: list[Image.Image | None] = [None] * len(items)
    for i, it in enumerate(items):
        path = Path(it["file"]) if it.get("file") else (got.get(i) or alt_by_item.get(i))
        im = _open(path) if path else None
        if im is None:
            it["cls"] = "missing"
            continue
        it["local"] = str(path)
        it["size"] = list(im.size)
        rh = match.hashes(im)
        dup = match.duplicate_from(qh, rh)
        for n_prev, h_prev in seen:                 # the same photograph published twice counts once
            d = match.duplicate_from(h_prev, rh)
            if d["near_duplicate"] or d["mirrored_duplicate"]:
                it["same_as"] = n_prev
                break
        seen.append((it["n"], rh))
        geo = matcher.score(im) if matcher else {"available": False}
        _apply(it, dup, geo)
        if not it.get("same_as"):
            smalls[i] = embed.small(im)
    sims = embed.similarities(q, smalls, http) if any(s is not None for s in smalls) else None
    for it, sim in zip(items, sims or []):
        if sim is not None:
            it["sim"] = sim
    if matcher and refine:
        # Thumbnails are too small for the feature test to confirm much. Fetch the originals of the likeliest
        # pictures (some agreement already, then the most similar ones) and test those at full size.
        open_ = [it for it in items if it["cls"] in ("same", "partial", "none") and it.get("image")
                 and not it.get("refined") and not it.get("same_as") and max(it.get("size", [0, 0])) < 900]
        by_inliers = sorted((it for it in open_ if it.get("inliers", 0) >= 8), key=lambda it: -it.get("inliers", 0))
        by_sim = sorted((it for it in open_ if it.get("sim") is not None and it not in by_inliers),
                        key=lambda it: -it["sim"])
        todo = (by_inliers[:refine] + by_sim[:max(2, refine // 2)])[:refine + max(2, refine // 2)]
        full = fetch_many(http, [it["image"] for it in todo], work / "full", workers=workers, timeout=20.0) if todo else {}
        for k, it in enumerate(todo):
            im = _open(full[k]) if k in full else None
            if im is None or max(im.size) <= max(it.get("size", [0, 0])):
                continue
            dup = match.duplicate_from(qh, match.hashes(im))
            geo = matcher.score(im)
            if match.RANK[match.classify(dup, geo)] > match.RANK[it["cls"]] or geo.get("inliers", 0) > it.get("inliers", 0):
                _apply(it, dup, geo)
            it["local"], it["size"], it["refined"] = str(full[k]), list(im.size), True
    # Confirmed classes first, by strength. Unconfirmed items: most similar first when the similarity model
    # ran, otherwise the order they arrived in (the engine's own ranking). Their inlier counts are noise and
    # never reshuffle them.
    items.sort(key=lambda it: (-match.RANK.get(it["cls"], -1),
                               -it.get("inliers", 0) if it["cls"] in ("same", "partial") else 0,
                               -it.get("sim", 0.0) if it["cls"] == "none" else 0.0, it["n"]))
    counts: dict[str, int] = {}
    for it in items:
        if not it.get("same_as"):
            counts[it["cls"]] = counts.get(it["cls"], 0) + 1
    return counts


def by_similarity(items: list[dict]) -> bool:
    """Whether the unconfirmed items of a ranked list are ordered by visual similarity."""
    return any(it.get("sim") is not None for it in items)


def _apply(it: dict, dup: dict, geo: dict) -> None:
    it["cls"] = match.classify(dup, geo)
    it["verdict"] = match.verdict(dup, geo)
    for k in ("inliers", "h_inliers", "f_inliers", "matches", "spread", "mirrored", "query_box"):
        if k in geo:
            it[k] = geo[k]
    it.setdefault("inliers", 0)


def ranked_sheets(q: Image.Image, items: list[dict], per_sheet: int = 15, max_sheets: int = 2, cols: int = 4,
                  cell: int = 384) -> list[Image.Image]:
    """Contact sheets in rank order. Tile 0 of every sheet is the query photo; every reference tile carries
    its number and class, and a frame in the class colour (green SAME SCENE, yellow PARTIAL, blue COPY, grey
    unconfirmed). Repeats of one photograph and items that did not download are left out."""
    shown = [it for it in items if it.get("local") and not it.get("same_as")]
    sheets = []
    f = imaging.font(13)
    cap = 36
    for s in range(max_sheets):
        part = shown[s * per_sheet:(s + 1) * per_sheet]
        if not part:
            break
        tiles = [("QUERY (your photo)", q, (255, 255, 255))]
        for it in part:
            im = _open(Path(it["local"]))
            if im is None:
                continue
            lab = f"#{it['n']} {match.LABEL.get(it['cls'], it['cls'])}"
            if it["cls"] in ("same", "partial"):
                lab += f" {it.get('inliers', 0)}"
            elif it["cls"] == "none" and it.get("sim") is not None:
                lab += f" sim {it['sim']:.2f}"
            lab += f" · {it.get('site') or '?'}"
            tiles.append((lab, im, FRAME.get(it["cls"], FRAME["none"])))
        rows = -(-len(tiles) // cols)
        sheet = Image.new("RGB", (cols * cell, rows * (cell + cap)), (24, 24, 28))
        d = ImageDraw.Draw(sheet)
        for k, (label, im, colour) in enumerate(tiles):
            t = im.copy()
            t.thumbnail((cell - 14, cell - 14))
            x, y = (k % cols) * cell, (k // cols) * (cell + cap)
            px, py = x + (cell - t.width) // 2, y + 6 + (cell - 14 - t.height) // 2
            sheet.paste(t, (px, py))
            d.rectangle([px - 3, py - 3, px + t.width + 2, py + t.height + 2], outline=colour, width=3)
            text = label
            while text and d.textlength(text, font=f) > cell - 12:
                text = text[:-2]
            if text != label:
                text = text.rstrip() + "…"
            d.text((x + 6, y + cell + 4), text, font=f, fill=colour if colour != FRAME["none"] else (225, 225, 225))
        sheets.append(sheet)
    return sheets


def summary_line(counts: dict[str, int]) -> str:
    parts = [f"{counts[k]} {match.LABEL[k]}" for k in ("copy", "same", "partial", "none") if counts.get(k)]
    parts = [p_.replace("unconfirmed", "unconfirmed (judge by eye)") for p_ in parts]
    if counts.get("missing"):
        parts.append(f"{counts['missing']} not downloadable")
    if counts.get("unchecked"):
        parts.append(f"{counts['unchecked']} unchecked (OpenCV missing)")
    return ", ".join(parts) or "nothing to compare"
