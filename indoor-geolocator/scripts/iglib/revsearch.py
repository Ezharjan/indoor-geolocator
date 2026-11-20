"""Reverse image search through a headless browser (Playwright + Chromium), one search per engine per
image, at human pace. Each engine returns HITS: pages and images the engine associates with the photo.
The caller (`igl.py revsearch`) then compares every hit with the photo itself (refs.rank_against) and
sorts them into COPY / SAME SCENE / PARTIAL / no match, because engines list look-alikes next to real
matches without telling them apart - the commonest source of a confidently wrong venue.

Two routes per engine, tried in this order:
  upload   the image file is given to the engine's own upload form (nothing else sees it);
  by URL   a temporary public copy (see share.py) is passed as ?url=...: far more reliable for Yandex and
           TinEye from datacenter networks, used automatically when the upload does not start a search.

A search that never started is `unavailable` (or `blocked` on a CAPTCHA), NEVER `no_results`:
`no_results` is only reported from an engine's own result page.

Headless status when last tested (2026-11): Yandex and TinEye work from datacenter networks (Yandex
mostly by URL); Baidu works where graph.baidu.com is reachable; Google Lens and Bing refuse headless
clients (CAPTCHA, decoy pages). For those, open the by-URL links in a browser tool, or set SERPAPI_KEY
(a SerpApi key: Google Lens results through their API).

Everything read from result pages passes through util.redact (engines decode QR codes and echo Wi-Fi
passwords back) before it is printed or stored.
"""
from __future__ import annotations

import asyncio
import html as htmllib
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .util import redact

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")
OWN = {"yandex": ("yandex.", "ya.ru", "yastatic"), "tineye": ("tineye.com", "idee.com", "shutterstock.com"),
       "baidu": ("baidu.com", "bdimg.com", "bdstatic.com"),
       "bing": ("bing.com", "microsoft.com", "msn.com", "live.com"), "lens": ("google.", "gstatic.", "googleusercontent")}
ENGINES = ("yandex", "tineye", "baidu", "bing", "lens")
BAIDU_REFUSED = ("功能优化中", "建议您重新上传其他图片")
IMG_EXT = re.compile(r"(?i)\.(jpe?g|png|webp|gif|bmp|avif)(\?|$)")
NOT_STARTED = ("the search did not start: the engine did not accept the image (upload not processed{}). "
               "This is NOT a no-result: try again later, another engine, or the by-URL links in a browser tool")


def available() -> tuple[bool, str]:
    import importlib.util
    if importlib.util.find_spec("playwright") is None:
        return False, "Python package `playwright` not installed (pip install playwright && playwright install chromium)"
    return True, ""


def by_url_links(url: str) -> dict[str, str]:
    """Search-by-URL entry points for an image at a public URL (open them in a browser tool)."""
    q = quote(url, safe="")
    return {"lens": f"https://lens.google.com/uploadbyurl?url={q}",
            "bing": f"https://www.bing.com/images/search?view=detailv2&iss=sbi&form=SBIVSP&sbisrc=UrlPaste&q=imgurl:{q}",
            "yandex": f"https://yandex.com/images/search?rpt=imageview&url={q}",
            "tineye": f"https://tineye.com/search?url={q}"}


def _site(url: str) -> str:
    host = urlparse(url or "").netloc.lower().split(":")[0]
    for pre in ("www.", "m.", "wap.", "mobile."):
        if host.startswith(pre) and host.count(".") > 1:
            return host[len(pre):]
    return host


def _hit(kind: str, title: str = "", page: str = "", image: str = "", thumb: str = "") -> dict:
    """kind: copy (the engine says it is this image) | page (a page the engine ties to the photo: a copy OR
    a look-alike, the engine does not say) | similar (visually similar image)."""
    for k in ("image", "thumb"):
        v = image if k == "image" else thumb
        if v.startswith("//"):
            v = "https:" + v
        if k == "image":
            image = v
        else:
            thumb = v
    return {"kind": kind, "title": redact(re.sub(r"\s+", " ", title or "").strip())[:200], "page": page or "",
            "image": image or "", "thumb": thumb or "", "site": _site(page or image)}


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
        out.append(_hit("page", ln["t"], page=ln["h"]))
        if len(out) >= limit:
            break
    return out


async def _text(page) -> str:
    try:
        return redact(await page.evaluate("document.body ? document.body.innerText : ''"))
    except Exception:  # noqa: BLE001
        return ""


async def _dismiss_cookies(page) -> None:
    for label in ("Allow essential cookies", "Only essential", "Accept essential", "Reject all", "Allow all",
                  "Accept all", "I agree"):
        try:
            btn = page.get_by_role("button", name=label)
            if await btn.count():
                await btn.first.click(timeout=2000)
                await page.wait_for_timeout(600)
                return
        except Exception:  # noqa: BLE001
            continue


async def _wait_for(page, selector: str, seconds: float):
    """Poll for an element (pages render their upload control late, especially over slow proxies)."""
    for _ in range(int(seconds * 2)):
        el = await page.query_selector(selector)
        if el:
            return el
        await page.wait_for_timeout(500)
    return None


async def _wait_url(page, good: tuple[str, ...], bad: tuple[str, ...], seconds: float) -> bool:
    """True once the address contains one of `good`; False on `bad` (a wall) or when the time is up."""
    for _ in range(int(seconds * 2)):
        url = page.url.lower()
        if any(b in url for b in bad):
            return False
        if any(g in url for g in good):
            return True
        await page.wait_for_timeout(500)
    return False


async def _not_started(page, tried: list[str]) -> dict:
    """The search never reached a result page: an empty page means the network failed, otherwise the engine
    did not process the image. Either way it is unavailable, not an absence of results."""
    txt = await _text(page)
    if len(txt.strip()) < 20:
        return {"status": "unavailable", "note": "the page did not load (network or proxy)"}
    how = f"; tried: {', '.join(tried)}" if tried else ""
    return {"status": "unavailable", "note": NOT_STARTED.format(how), "text_head": txt[:400]}


# ----------------------------------------------------------------------------- engines
async def _yandex(page, img: Path, get_url) -> dict:
    tried, started, route, url = [], False, "", None
    walls = ("showcaptcha",)
    try:
        await page.goto("https://yandex.com/images/search?rpt=imageview", wait_until="domcontentloaded", timeout=45000)
        inp = await _wait_for(page, 'input[type="file"]', 10)
        if inp:
            tried.append("upload")
            await inp.set_input_files(str(img))
            started = await _wait_url(page, ("cbir_id",), walls, 18)
            route = "upload"
    except Exception:  # noqa: BLE001 - fall through to the by-URL route
        pass
    if not started and "showcaptcha" not in page.url:
        url = get_url()                  # a temporary public copy is only made when the upload failed
    if not started and url and "showcaptcha" not in page.url:
        tried.append("by URL")
        await page.goto(by_url_links(url)["yandex"], wait_until="domcontentloaded", timeout=45000)
        started = await _wait_url(page, ("cbir_id",), walls, 20)
        route = "url"
    if "showcaptcha" in page.url:
        return {"status": "blocked", "note": "Yandex CAPTCHA (not solved): this network is rate-limited by Yandex now"}
    if not started:
        return await _not_started(page, tried)
    await page.wait_for_timeout(3500)
    await _dismiss_cookies(page)
    txt = await _text(page)
    lines = [s.strip() for s in txt.splitlines() if s.strip()]
    labels = []
    for i, s in enumerate(lines):
        if "appears to contain" in s.lower() or s.lower().startswith("на изображении"):
            for nxt in lines[i + 1:i + 10]:
                if nxt.lower() in ("similar images", "похожие изображения", "sites", "сайты", "in other sizes",
                                   "другие размеры") or len(nxt) > 60:
                    break
                labels.append(nxt)
            break
    hits: list[dict] = []
    try:
        raw = await page.evaluate("""() => [...document.querySelectorAll('.CbirSites-Item, .CbirSitesItem, li[class*="CbirSites"]')].slice(0, 25).map(it => {
            const a = it.querySelector('.CbirSites-ItemTitle a[href^="http"]') || it.querySelector('.CbirSites-ItemDomain[href^="http"]') || it.querySelector('a[href^="http"]');
            const ia = it.querySelector('.CbirSites-ItemThumb a[href^="http"]');
            const th = it.querySelector('.CbirSites-ItemThumb img') || it.querySelector('img');
            return {t: it.innerText.trim().split('\\n').filter(x => x).slice(0, 3).join(' | '), href: a ? a.href : '',
                    image: ia ? ia.href : '', thumb: th ? (th.currentSrc || th.src || '') : ''}; })""")
        for r in raw:
            if r.get("href"):
                hits.append(_hit("page", r["t"], page=r["href"].split("?utm_")[0].split("&utm_")[0], image=r.get("image") or "",
                                 thumb=r.get("thumb") or ""))
    except Exception:  # noqa: BLE001
        pass
    try:
        raw = await page.evaluate("""() => [...document.querySelectorAll('.CbirSimilarList-Thumb a')].map(a => {
            const d = a.querySelector('[role=img]') || a.querySelector('img') || a;
            const bg = (d.style && d.style.backgroundImage) || '';
            return {h: a.getAttribute('href') || '', t: d.getAttribute('aria-label') || d.getAttribute('alt') || '',
                    bg: bg, src: d.getAttribute('src') || ''};})""")
        for r in raw[:40]:
            q = parse_qs(urlparse(htmllib.unescape(r["h"])).query)
            src = (q.get("img_url") or [""])[0]
            m = re.search(r"url\(['\"]?([^'\")]+)", r["bg"] or "")
            thumb = (m.group(1) if m else r["src"]) or ""
            if thumb or src:
                hits.append(_hit("similar", r["t"], image=src, thumb=thumb))
    except Exception:  # noqa: BLE001
        pass
    if not hits and not labels:
        hits = await _links(page, "yandex")
    return {"status": "results" if (labels or hits) else "no_results", "route": route, "labels": labels, "hits": hits,
            "text_head": "\n".join(lines[:80])[:3000]}


async def _tineye(page, img: Path, get_url) -> dict:
    tried, started, route, url = [], False, "", None
    try:
        await page.goto("https://tineye.com/", wait_until="domcontentloaded", timeout=45000)
        inp = await _wait_for(page, 'input[type="file"]', 10)
        if inp:
            tried.append("upload")
            await inp.set_input_files(str(img))
            started = await _wait_url(page, ("/search/",), (), 20)
            route = "upload"
    except Exception:  # noqa: BLE001
        pass
    if not started:
        url = get_url()
    if not started and url:
        tried.append("by URL")
        await page.goto(by_url_links(url)["tineye"], wait_until="domcontentloaded", timeout=45000)
        started = await _wait_url(page, ("/search/",), (), 20)
        route = "url"
    if not started:
        return await _not_started(page, tried)
    await page.wait_for_timeout(3000)
    txt = await _text(page)
    m = re.search(r"([\d,]+)\s+match", txt)
    if not m:
        return {"status": "unavailable", "route": route, "text_head": txt[:400],
                "note": "TinEye's result page did not show a match count (rate limit or layout change): not a no-result"}
    n = int(m.group(1).replace(",", ""))
    hits: list[dict] = []
    if n:
        try:
            raw = await page.evaluate("""() => [...document.querySelectorAll('a[href^="http"]')].map(a => ({
                h: a.href, t: (a.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 120)}))""")
        except Exception:  # noqa: BLE001
            raw = []
        cur, seen = "", set()
        for ln in raw:                       # document order: a page link, then the image file(s) found on it
            host = urlparse(ln["h"]).netloc.lower()
            if not host or any(o in host for o in OWN["tineye"]) or (url and ln["h"].split("?")[0] == url.split("?")[0]):
                continue
            if IMG_EXT.search(ln["h"]) or ln["t"].lower() == "view image":
                key = (cur, ln["h"])
                if key not in seen:
                    seen.add(key)
                    hits.append(_hit("copy", _site(cur or ln["h"]), page=cur, image=ln["h"]))
            else:
                cur = ln["h"]
        by_image: dict[str, dict] = {}
        for h in hits:                       # one hit per image file
            by_image.setdefault(h["image"], h)
        hits = list(by_image.values())[:40]
    return {"status": "results" if n else "no_results", "route": route, "n_matches": n, "hits": hits,
            "text_head": txt[:1500],
            "note": "" if n else "TinEye finds copies of THIS image only: no match is normal for a private photo"}


async def _baidu(page, img: Path, get_url) -> dict:
    """Baidu 识图: the 相似图片 (similar images) cards are not DOM links; their data arrives through
    graph.baidu.com/ajax/pcsimi responses, which are captured here (title page = fromUrl)."""
    simi: list = []
    pending: list = []

    async def grab(resp):
        try:
            data = (await resp.json()).get("data") or {}
            simi.extend(data.get("list") or [])
        except Exception:  # noqa: BLE001
            pass

    page.on("response", lambda r: pending.append(asyncio.ensure_future(grab(r)))
            if "graph.baidu.com/ajax/pcsimi" in r.url else None)
    await page.goto("https://graph.baidu.com/pcpage/index?tpl_from=pc", wait_until="domcontentloaded", timeout=30000)
    inp = await _wait_for(page, "input[type=file]", 15)
    if not inp:
        res = await _not_started(page, [])
        if res["status"] == "unavailable" and "did not load" not in res.get("note", ""):
            res = {"status": "blocked", "note": "Baidu showed no upload control (verification page or layout change)",
                   "text_head": res.get("text_head", "")}
        return res
    await inp.set_input_files(str(img))
    started = await _wait_url(page, ("graph.baidu.com/s",), ("captcha",), 20)
    if not started:
        txt = await _text(page)
        if "安全验证" in txt or "captcha" in page.url.lower():
            return {"status": "blocked", "note": "Baidu security check (not bypassed)"}
        return await _not_started(page, ["upload"])
    for _ in range(24):                                 # the first similar-images page arrives a few s later
        await page.wait_for_timeout(500)
        if pending:
            break
    await page.wait_for_timeout(1500)
    for _ in range(2):                                  # scrolling loads the next page of similar images
        await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        await page.wait_for_timeout(2000)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    await page.evaluate("window.scrollTo(0, 0)")
    txt = await _text(page)
    lines = [s.strip() for s in txt.splitlines() if s.strip()]
    if any(w in txt for w in BAIDU_REFUSED):
        return {"status": "blocked", "note": "Baidu refused this image ('功能优化中'): try a crop or another engine",
                "text_head": "\n".join(lines[:40])}
    if "安全验证" in txt or "captcha" in page.url.lower():
        return {"status": "blocked", "note": "Baidu security check (not bypassed)"}
    guess = [s for s in lines if s.startswith("图中可能是")]
    seen, hits = set(), []
    for it in simi:
        key = it.get("contsign") or it.get("thumbUrl")
        if not it.get("thumbUrl") or key in seen:
            continue
        seen.add(key)
        hits.append(_hit("similar", it.get("title") or it.get("fromPageTitle") or "", page=it.get("fromUrl") or "",
                         image=it.get("objUrl") or "", thumb=it["thumbUrl"]))
    if not hits:
        hits = await _links(page, "baidu")
    return {"status": "results" if (guess or hits) else "no_results", "route": "upload", "labels": guess, "hits": hits,
            "text_head": "\n".join(lines[:60])[:2500]}


async def _bing(page, img: Path, get_url) -> dict:
    await page.goto("https://www.bing.com/images", wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(2500)
    btn = await _wait_for(page, "#sb_sbi", 6)
    if btn:
        await btn.click()
        await page.wait_for_timeout(1500)
    inp = await _wait_for(page, 'input[type="file"]', 6)
    if not inp:
        return {"status": "blocked", "note": "Bing showed no upload control to a headless client: open the by-URL "
                                             "link in a browser tool"}
    await inp.set_input_files(str(img))
    if not await _wait_url(page, ("detailv2", "insightstoken"), (), 25):
        return {"status": "blocked", "note": "Bing did not accept the headless upload: open the by-URL link in a "
                                             "browser tool"}
    return {"status": "results", "route": "upload", "hits": await _links(page, "bing"),
            "text_head": (await _text(page))[:3000]}


async def _lens(page, img: Path, get_url) -> dict:
    await page.goto("https://lens.google.com/", wait_until="domcontentloaded", timeout=45000)
    inp = await _wait_for(page, 'input[type="file"]', 8)
    if not inp:
        return {"status": "blocked", "note": "Google Lens showed no upload control (consent or verification page): "
                                             "open the by-URL link in a browser tool"}
    await inp.set_input_files(str(img))
    await page.wait_for_timeout(10000)
    if "/sorry/" in page.url:
        return {"status": "blocked", "note": "Google 'unusual traffic' CAPTCHA: open the by-URL link in a browser "
                                             "tool (or set SERPAPI_KEY)"}
    return {"status": "results", "route": "upload", "hits": await _links(page, "lens"),
            "text_head": (await _text(page))[:3000]}


RUNNERS = {"yandex": _yandex, "tineye": _tineye, "baidu": _baidu, "bing": _bing, "lens": _lens}


def lens_api(http, url: str, key: str | None = None) -> dict:
    """Google Lens through SerpApi (optional: needs the user's own key in SERPAPI_KEY and a public image URL).
    Returns the same shape as the headless engines; every visual match is a `page` hit until it is compared."""
    key = key or os.environ.get("SERPAPI_KEY")
    if not key:
        return {"status": "unavailable", "note": "no SERPAPI_KEY set (optional: Google Lens through SerpApi)"}
    if not url:
        return {"status": "unavailable", "note": "Lens by API needs a public image URL (no temporary copy was made)"}
    r = http.get("https://serpapi.com/search.json", {"engine": "google_lens", "url": url, "api_key": key}, cache=False)
    d = r.get("data") if r.get("ok") else None
    if not isinstance(d, dict):
        status = "blocked" if r.get("status") in (401, 403, 429) else "unavailable"
        return {"status": status, "note": f"SerpApi: {str(r.get('error'))[:160]}"}
    if d.get("error"):
        empty = "hasn't returned any results" in str(d["error"])
        return {"status": "no_results" if empty else "unavailable", "route": "api", "hits": [],
                "note": f"SerpApi: {str(d['error'])[:160]}"}
    hits = [_hit("page", f"{m.get('title') or ''}", page=m.get("link") or "", image=m.get("image") or "",
                 thumb=m.get("thumbnail") or "") for m in (d.get("visual_matches") or [])[:40] if isinstance(m, dict)]
    labels = [str(k.get("title")) for k in (d.get("knowledge_graph") or []) if isinstance(k, dict) and k.get("title")]
    return {"status": "results" if (hits or labels) else "no_results", "route": "api", "labels": labels[:8], "hits": hits}


async def _run_all(images: list[tuple[str, Path]], engines: list[str], shot_for, url_for) -> list[dict]:
    from playwright.async_api import async_playwright
    results = []
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        except Exception as e:  # noqa: BLE001
            msg = str(e).splitlines()[0]
            return [{"engine": e_, "image": lbl, "status": "unavailable", "hits": [],
                     "note": f"Chromium could not start ({msg}); try `playwright install chromium`"}
                    for lbl, _ in images for e_ in engines]
        ctx = await browser.new_context(user_agent=UA, locale="en-US", viewport={"width": 1366, "height": 900})

        async def one(engine: str, label: str, img: Path) -> dict:
            page = await ctx.new_page()
            t0 = time.time()
            try:
                res = await RUNNERS[engine](page, img, lambda: url_for(label))
            except Exception as e:  # noqa: BLE001 - DNS failure, proxy refusal, timeout, layout change
                first = str(e).splitlines()[0][:160] if str(e) else ""
                res = {"status": "unavailable", "note": f"{type(e).__name__}: {first}"}
            res.update({"engine": engine, "image": label, "url": page.url, "seconds": round(time.time() - t0, 1)})
            res.setdefault("hits", [])
            res.setdefault("labels", [])
            if res["status"] != "unavailable":
                try:
                    path = shot_for(engine, label)
                    h = await page.evaluate("document.documentElement.scrollHeight")
                    await page.screenshot(path=str(path), full_page=True, type="jpeg", quality=78,
                                          clip={"x": 0, "y": 0, "width": 1366, "height": min(int(h or 900), 2600)})
                    res["screenshot"] = str(path)
                except Exception:  # noqa: BLE001
                    pass
            await page.close()
            return res

        blocked: set[str] = set()
        for label, img in images:          # images in sequence, engines in parallel (one search each)
            todo = [e for e in engines if e not in blocked]
            results += [{"engine": e, "image": label, "status": "blocked", "hits": [], "labels": [],
                         "note": "skipped: the engine refused the previous image in this run"}
                        for e in engines if e in blocked]
            batch = await asyncio.gather(*[one(e, label, img) for e in todo])
            for r in batch:
                if r["status"] == "blocked":       # a wall stays up: do not send it the next image as well
                    blocked.add(r["engine"])
            results += batch
        await browser.close()
    return results


def search(images: list[tuple[str, Path]], engines: list[str], shot_for, url_for=None) -> list[dict]:
    """One result per (engine, image): {engine, image, status, route, note, labels, hits, n_matches?, url,
    seconds, screenshot}. `url_for(label)` returns a temporary public URL of that image (or None): it is
    only called when an engine's upload did not start a search (by-URL fallback)."""
    ok, why = available()
    if not ok:
        return [{"engine": e, "image": lbl, "status": "unavailable", "note": why, "hits": [], "labels": []}
                for lbl, _ in images for e in engines]
    return asyncio.run(_run_all(images, engines, shot_for, url_for or (lambda label: None)))


MANUAL = """Not covered headless: Google Lens (the largest index for venues, interiors and listings) and Bing.
If you have ANY browser tool (Claude in Chrome, the built-in browser), open the lens/bing links printed
above (or by `igl.py share <case> [--cell ..]`) there, on the full frame and on 2-3 tight crops: for an indoor
photo this is often the route that finds the place. Read 'Exact matches' (provenance) apart from 'Visual
matches' (leads: compare them with `igl.py refs <case> --image <url>`), and ignore the AI overview as evidence.
Also worth a browser visit: Baidu (graph.baidu.com) and Sogou (pic.sogou.com) for Chinese content, Naver for
Korean, Pinterest Lens for decor. Record each outcome:
  igl.py log <case> reverse_search --status results|no_results|blocked --engine lens --detail "..." """
