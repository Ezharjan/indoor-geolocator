"""Reverse image search through a headless browser (Playwright + Chromium), one upload per engine per
image, at human pace. Saves each result page as a screenshot plus the extracted labels and matching
pages. Engine availability changes: every outcome is labelled results / no_results / blocked /
unavailable, and a blocked engine is never retried in a loop or worked around.

Headless status when this skill was built: Yandex and TinEye work; Google Lens and Bing usually demand a
CAPTCHA / refuse uploads from datacenter IPs. For those, use your browser tool (Claude in Chrome or the
built-in browser: open lens.google.com or bing.com/visualsearch and upload the file) or ask the user,
then record the outcome with `igl.py log`.
"""
from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from urllib.parse import urlparse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")
OWN = {"yandex": ("yandex.", "ya.ru", "yastatic"), "tineye": ("tineye.com", "idee.com"),
       "bing": ("bing.com", "microsoft.com", "msn.com", "live.com"), "lens": ("google.", "gstatic.", "googleusercontent")}
ENGINES = ("yandex", "tineye", "bing", "lens")


def available() -> tuple[bool, str]:
    import importlib.util
    if importlib.util.find_spec("playwright") is None:
        return False, "Python package `playwright` not installed (pip install playwright && playwright install chromium)"
    return True, ""


async def _links(page, engine: str, limit: int = 30) -> list[dict]:
    try:
        raw = await page.evaluate("""() => [...document.querySelectorAll('a[href^="http"]')].map(a => ({
            t: (a.innerText || a.title || a.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ').slice(0, 160),
            h: a.href}))""")
    except Exception:  # noqa: BLE001
        return []
    seen, out = set(), []
    for ln in raw:
        host = urlparse(ln["h"]).netloc.lower()
        if not host or any(o in host for o in OWN[engine]) or ln["h"] in seen or len(ln["t"]) < 4:
            continue
        seen.add(ln["h"])
        out.append({"title": ln["t"], "url": ln["h"], "site": host})
        if len(out) >= limit:
            break
    return out


async def _text(page) -> str:
    try:
        return await page.evaluate("document.body ? document.body.innerText : ''")
    except Exception:  # noqa: BLE001
        return ""


async def _yandex(page, img: Path) -> dict:
    await page.goto("https://yandex.com/images/search?rpt=imageview", wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(2500)
    inp = await page.query_selector('input[type="file"]')
    if not inp:
        return {"status": "blocked", "note": "upload control not found (CAPTCHA or layout change)"}
    await inp.set_input_files(str(img))
    for _ in range(20):
        await page.wait_for_timeout(1000)
        if "cbir_id" in page.url or "showcaptcha" in page.url:
            break
    await page.wait_for_timeout(3500)
    if "showcaptcha" in page.url:
        return {"status": "blocked", "note": "Yandex CAPTCHA"}
    txt = await _text(page)
    labels = []
    lines = [s.strip() for s in txt.splitlines() if s.strip()]
    for i, s in enumerate(lines):
        if "appears to contain" in s.lower() or s.lower().startswith("на изображении"):
            for nxt in lines[i + 1:i + 10]:
                if nxt.lower() in ("similar images", "похожие изображения", "sites", "сайты") or len(nxt) > 60:
                    break
                labels.append(nxt)
            break
    sites = []
    try:
        items = await page.query_selector_all(".CbirSites-Item, .CbirSitesItem, li[class*='CbirSites']")
        for it in items[:25]:
            t = (await it.inner_text()).strip().split("\n")
            a = await it.query_selector("a[href^='http']")
            href = await a.get_attribute("href") if a else ""
            sites.append({"title": " | ".join(x for x in t[:3] if x)[:200], "url": href,
                          "site": urlparse(href).netloc if href else ""})
    except Exception:  # noqa: BLE001
        pass
    if not sites:
        sites = await _links(page, "yandex")
    return {"status": "results" if (labels or sites) else "no_results", "labels": labels, "matches": sites,
            "text_head": "\n".join(lines[:80])[:3000]}


async def _tineye(page, img: Path) -> dict:
    await page.goto("https://tineye.com/", wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(2000)
    inp = await page.query_selector('input[type="file"]')
    if not inp:
        return {"status": "blocked", "note": "upload control not found"}
    await inp.set_input_files(str(img))
    for _ in range(20):
        await page.wait_for_timeout(1000)
        if "/search/" in page.url:
            break
    await page.wait_for_timeout(3000)
    txt = await _text(page)
    m = re.search(r"([\d,]+)\s+match", txt)
    n = int(m.group(1).replace(",", "")) if m else 0
    matches = []
    if n:
        try:
            blocks = await page.query_selector_all(".match, .match-row, div[class*='match']")
            for b in blocks[:40]:
                t = (await b.inner_text()).strip()
                a = await b.query_selector("a[href^='http']")
                href = await a.get_attribute("href") if a else ""
                if t and href and "tineye.com" not in href:
                    matches.append({"title": re.sub(r"\s+", " ", t)[:200], "url": href, "site": urlparse(href).netloc})
        except Exception:  # noqa: BLE001
            pass
        if not matches:
            matches = await _links(page, "tineye")
    return {"status": "results" if n else "no_results", "n_matches": n, "matches": matches[:30],
            "text_head": txt[:1500]}


async def _bing(page, img: Path) -> dict:
    await page.goto("https://www.bing.com/images", wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(2500)
    btn = await page.query_selector("#sb_sbi")
    if btn:
        await btn.click()
        await page.wait_for_timeout(1500)
    inp = await page.query_selector('input[type="file"]')
    if not inp:
        return {"status": "blocked", "note": "upload control not found"}
    await inp.set_input_files(str(img))
    await page.wait_for_timeout(11000)
    txt = await _text(page)
    if "unable to process" in txt.lower() or page.url.rstrip("/").endswith("/images"):
        return {"status": "blocked", "note": "Bing refused the headless upload - use your browser tool"}
    return {"status": "results", "matches": await _links(page, "bing"), "text_head": txt[:3000]}


async def _lens(page, img: Path) -> dict:
    await page.goto("https://lens.google.com/", wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(2500)
    inp = await page.query_selector('input[type="file"]')
    if not inp:
        return {"status": "blocked", "note": "upload control not found (consent page?) - use your browser tool"}
    await inp.set_input_files(str(img))
    await page.wait_for_timeout(10000)
    if "/sorry/" in page.url:
        return {"status": "blocked", "note": "Google 'unusual traffic' CAPTCHA - use your browser tool"}
    return {"status": "results", "matches": await _links(page, "lens"), "text_head": (await _text(page))[:3000]}


RUNNERS = {"yandex": _yandex, "tineye": _tineye, "bing": _bing, "lens": _lens}


async def _run_all(images: list[tuple[str, Path]], engines: list[str], shot_for) -> list[dict]:
    from playwright.async_api import async_playwright
    results = []
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        except Exception as e:  # noqa: BLE001
            msg = str(e).splitlines()[0]
            return [{"engine": e_, "image": lbl, "status": "unavailable",
                     "note": f"Chromium could not start ({msg}); try `playwright install chromium`"}
                    for lbl, _ in images for e_ in engines]
        ctx = await browser.new_context(user_agent=UA, locale="en-US", viewport={"width": 1366, "height": 900})

        async def one(engine: str, label: str, img: Path) -> dict:
            page = await ctx.new_page()
            t0 = time.time()
            try:
                res = await RUNNERS[engine](page, img)
            except Exception as e:  # noqa: BLE001
                res = {"status": "unavailable", "note": f"{type(e).__name__}: {str(e).splitlines()[0][:160]}"}
            res.update({"engine": engine, "image": label, "url": page.url, "seconds": round(time.time() - t0, 1)})
            try:
                path = shot_for(engine, label)
                await page.screenshot(path=str(path), full_page=False, type="jpeg", quality=80)
                res["screenshot"] = str(path)
            except Exception:  # noqa: BLE001
                pass
            await page.close()
            return res

        for label, img in images:          # images in sequence, engines in parallel (one upload each)
            results += await asyncio.gather(*[one(e, label, img) for e in engines])
        await browser.close()
    return results


def search(images: list[tuple[str, Path]], engines: list[str], shot_for) -> list[dict]:
    ok, why = available()
    if not ok:
        return [{"engine": e, "image": lbl, "status": "unavailable", "note": why} for lbl, _ in images for e in engines]
    return asyncio.run(_run_all(images, engines, shot_for))


MANUAL = """Manual reverse search (when an engine is blocked or not automated):
  * Google Lens - strongest for places/venues: lens.google.com -> upload; read 'Exact matches' (provenance) separately
    from the AI overview (a guess). With a public image URL: https://lens.google.com/uploadbyurl?url=<url>
  * Bing Visual Search: bing.com/visualsearch -> upload.     * Yandex: yandex.com/images -> camera icon.
  * TinEye (exact copies, oldest first): tineye.com.         * Baidu (China content): graph.baidu.com.
  * Naver (Korea): search.naver.com image search.            * Sogou (China): pic.sogou.com.
Use your browser tool if you have one (Claude in Chrome / built-in browser can upload files); otherwise ask the
user. Search the full image AND tight crops of distinctive objects; try a mirrored copy. Record each outcome:
  igl.py log <case> reverse_search --status results|no_results|blocked --engine lens --detail "..." --file E##"""
