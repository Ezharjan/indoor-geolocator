"""Social media and community photos, searched for the PLACE (never for people - SKILL.md hard rule 11).

Two layers:
  search()  keyless OPEN APIs that are built for programmatic access: Bluesky (AppView searchPosts),
            Mastodon hashtag timelines, Flickr public tag feeds, Lemmy (federated forums) and Openverse
            (openly licensed images from Flickr, Wikimedia and others).
  links()   ready-to-open search URLs for platforms that need a browser and often a login (Instagram,
            TikTok, X, Facebook, Threads, YouTube, Reddit, Pinterest, Xiaohongshu, Douyin, Weibo,
            Bilibili, VK, Naver, Yahoo! JAPAN realtime search ...) plus search-engine `site:` queries
            that reach their publicly indexed posts. Open them with a browser tool; nothing is scraped.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse

from .net import Http

SOURCES = ["bluesky", "flickr", "openverse", "mastodon", "lemmy"]


def _text(s: str | None) -> str:
    s = re.sub(r"<br\s*/?>|</p>", " ", s or "", flags=re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def hashtag(query: str) -> str:
    """'Hotel Sacher Wien' -> 'hotelsacherwien' (letters and digits of any script)."""
    return re.sub(r"[\W_]+", "", query.lower())


def _item(source, url, date, text, thumbs=None, fulls=None, extra=None) -> dict:
    return {"source": source, "url": url, "date": (date or "")[:19], "text": text or "",
            "thumbs": [t for t in (thumbs or []) if t], "images": [f for f in (fulls or []) if f], **(extra or {})}


# ----------------------------------------------------------------------------- open APIs
def bluesky(http: Http, q: str, limit: int = 15, lang: str | None = None) -> dict:
    p = {"q": q, "limit": max(1, min(100, limit))}
    if lang:
        p["lang"] = lang
    r = http.get("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts", p)
    if not r["ok"]:
        return {"ok": False, "error": r.get("error"), "items": []}
    out = []
    for post in (r.get("data") or {}).get("posts", []):
        rkey = post.get("uri", "").rsplit("/", 1)[-1]
        who = (post.get("author") or {}).get("handle") or (post.get("author") or {}).get("did", "")
        emb = post.get("embed") or {}
        media = emb.get("media") or emb                      # recordWithMedia nests the media
        imgs = media.get("images") or []
        thumbs = [i.get("thumb") for i in imgs] or [media.get("thumbnail") or (media.get("external") or {}).get("thumb")]
        alts = " | ".join(i.get("alt", "") for i in imgs if i.get("alt"))
        rec = post.get("record") or {}
        out.append(_item("bluesky", f"https://bsky.app/profile/{who}/post/{rkey}", rec.get("createdAt"),
                         _text(rec.get("text")) + (f"  [alt: {alts}]" if alts else ""),
                         thumbs, [i.get("fullsize") for i in imgs]))
    return {"ok": True, "items": out}


def mastodon_tag(http: Http, tag: str, instance: str = "mastodon.social", limit: int = 15) -> dict:
    tag = hashtag(tag)
    if not tag:
        return {"ok": False, "error": "empty hashtag", "items": []}
    r = http.get(f"https://{instance}/api/v1/timelines/tag/{urllib.parse.quote(tag)}", {"limit": max(1, min(40, limit))})
    if not r["ok"]:
        return {"ok": False, "error": r.get("error"), "items": []}
    out = []
    for s in r.get("data") or []:
        media = s.get("media_attachments") or []
        desc = " | ".join(m.get("description") or "" for m in media if m.get("description"))
        out.append(_item("mastodon", s.get("url") or s.get("uri"), s.get("created_at"),
                         _text(s.get("content")) + (f"  [alt: {desc}]" if desc else ""),
                         [m.get("preview_url") for m in media], [m.get("url") for m in media]))
    return {"ok": True, "items": out, "tag": tag}


def flickr_tags(http: Http, tags: str, mode: str = "all", limit: int = 15) -> dict:
    r = http.get("https://www.flickr.com/services/feeds/photos_public.gne",
                 {"tags": tags, "tagmode": mode, "format": "json", "nojsoncallback": 1}, as_json=False)
    if not r["ok"]:
        return {"ok": False, "error": r.get("error"), "items": []}
    try:                                     # the feed sometimes escapes apostrophes as \' (invalid JSON)
        d = json.loads(r["text"].replace("\\'", "'"))
    except ValueError as e:
        return {"ok": False, "error": f"unreadable feed ({e})", "items": []}
    out = []
    for it in d.get("items", [])[:limit]:
        m = (it.get("media") or {}).get("m")
        out.append(_item("flickr", it.get("link"), it.get("date_taken"),
                         f"{it.get('title', '')}  [tags: {short_tags(it.get('tags', ''))}]",
                         [m], [m.replace("_m.", "_b.") if m else None]))
    return {"ok": True, "items": out, "tags": tags}


def short_tags(tags: str, n: int = 12) -> str:
    t = tags.split()
    return " ".join(t[:n]) + (" ..." if len(t) > n else "")


def lemmy(http: Http, q: str, instance: str = "lemmy.world", limit: int = 15) -> dict:
    r = http.get(f"https://{instance}/api/v3/search", {"q": q, "type_": "Posts", "sort": "TopAll",
                                                        "limit": max(1, min(50, limit))})
    if not r["ok"]:
        return {"ok": False, "error": r.get("error"), "items": []}
    out = []
    for pv in (r.get("data") or {}).get("posts", []):
        p = pv.get("post") or {}
        link = p.get("url") or ""
        is_img = bool(re.search(r"\.(jpe?g|png|webp|gif)(\?|$)", link, re.I))
        out.append(_item("lemmy", p.get("ap_id"), p.get("published"),
                         f"{p.get('name', '')} — {_text(p.get('body'))[:200]}  [c/{(pv.get('community') or {}).get('name', '')}]",
                         [p.get("thumbnail_url") or (link if is_img else None)], [link if is_img else None]))
    return {"ok": True, "items": out}


def openverse(http: Http, q: str, limit: int = 15) -> dict:
    r = http.get("https://api.openverse.org/v1/images/", {"q": q, "page_size": max(1, min(20, limit))})
    if not r["ok"]:
        return {"ok": False, "error": r.get("error"), "items": []}
    out = []
    for it in (r.get("data") or {}).get("results", []):
        lic = f"CC {it.get('license', '').upper()} {it.get('license_version') or ''}".strip()
        out.append(_item("openverse", it.get("foreign_landing_url"), it.get("indexed_on"),
                         f"{it.get('title', '')}  [{it.get('provider', '')}; {lic}]",
                         [it.get("thumbnail")], [it.get("url")]))
    return {"ok": True, "items": out}


def search(http: Http, query: str, sources: list[str], tag: str | None = None, limit: int = 15,
           instance: str = "mastodon.social", lang: str | None = None) -> dict:
    res: dict = {}
    for s in sources:
        if s == "bluesky":
            res[s] = bluesky(http, query, limit, lang)
        elif s == "mastodon":
            res[s] = mastodon_tag(http, tag or query, instance, limit)
        elif s == "flickr":
            tags = tag or ",".join(w for w in re.split(r"[\s,]+", query.lower()) if w)
            res[s] = flickr_tags(http, tags, "all", limit)
        elif s == "lemmy":
            res[s] = lemmy(http, query, limit=limit)
        elif s == "openverse":
            res[s] = openverse(http, query, limit)
        else:
            res[s] = {"ok": False, "error": f"unknown source (choose from {', '.join(SOURCES)})", "items": []}
    return res


# ----------------------------------------------------------------------------- links for a browser
def _u(base: str, **params) -> str:
    return base + "?" + urllib.parse.urlencode(params)


def links(query: str, tag: str | None = None, at: tuple[float, float] | None = None,
          only: list[str] | None = None) -> list[dict]:
    """Rows: {platform, kind, url, note}. kind = 'engine' (public index, no login) or 'native'."""
    q, t = query.strip(), hashtag(tag or query)
    qq = urllib.parse.quote(q)
    g = lambda s: _u("https://www.google.com/search", q=f"{q} {s}")            # noqa: E731
    rows = [
        ("instagram", "engine", g("site:instagram.com"), "public posts indexed by Google"),
        ("tiktok", "engine", g("site:tiktok.com"), "public videos indexed by Google"),
        ("x", "engine", g("(site:x.com OR site:twitter.com)"), "public posts indexed by Google"),
        ("facebook", "engine", g("site:facebook.com"), "public pages and posts"),
        ("reddit", "engine", g("site:reddit.com"), "threads, incl. 'where is this' subreddits"),
        ("youtube", "engine", g("site:youtube.com"), "room tours, walk-throughs, vlogs"),
        ("pinterest", "engine", g("site:pinterest.com"), "interior photos, often from listings"),
        ("threads", "engine", g("site:threads.com"), "public posts"),
        ("social", "engine", _u("https://www.bing.com/search", q=f"{q} (site:instagram.com OR site:tiktok.com OR "
                                                                   "site:facebook.com OR site:x.com OR site:reddit.com)"),
         "Bing's index differs from Google's"),
        ("vk", "engine", _u("https://yandex.com/search/", text=f"{q} site:vk.com"), "Russian-speaking web"),
        ("xiaohongshu", "engine", _u("https://www.baidu.com/s", wd=f"{q} site:xiaohongshu.com"), "Chinese lifestyle posts"),
        ("weibo", "engine", _u("https://www.baidu.com/s", wd=f"{q} site:weibo.com"), "Chinese microblog"),
        ("x", "engine", _u("https://search.yahoo.co.jp/realtime/search", p=q), "Yahoo! JAPAN realtime: X posts, no login"),
        ("naver", "engine", _u("https://search.naver.com/search.naver", where="blog", query=q), "Korean blogs (cafés, hotels, homes)"),
        ("daum", "engine", _u("https://search.daum.net/search", w="blog", q=q), "Korean blogs"),
        ("instagram", "native", f"https://www.instagram.com/explore/tags/{urllib.parse.quote(t)}/", "hashtag page (login)"),
        ("instagram", "native", _u("https://www.instagram.com/explore/search/keyword/", q=q), "keyword search (login)"),
        ("tiktok", "native", _u("https://www.tiktok.com/search", q=q), "search (may need login)"),
        ("x", "native", _u("https://x.com/search", q=q, f="live"), "latest posts (login)"),
        ("threads", "native", _u("https://www.threads.com/search", q=q), "search (login)"),
        ("facebook", "native", _u("https://www.facebook.com/search/posts/", q=q), "posts (login)"),
        ("youtube", "native", _u("https://www.youtube.com/results", search_query=q), "videos"),
        ("reddit", "native", _u("https://www.reddit.com/search/", q=q), "posts and comments"),
        ("pinterest", "native", _u("https://www.pinterest.com/search/pins/", q=q), "pins (login after a few views)"),
        ("flickr", "native", _u("https://www.flickr.com/search/", text=q), "photos, often geotagged"),
        ("bluesky", "native", _u("https://bsky.app/search", q=q), "posts"),
        ("mastodon", "native", f"https://mastodon.social/tags/{urllib.parse.quote(t)}", "hashtag (federated)"),
        ("xiaohongshu", "native", _u("https://www.xiaohongshu.com/search_result", keyword=q), "小红书 (login)"),
        ("douyin", "native", f"https://www.douyin.com/search/{qq}", "抖音 videos"),
        ("weibo", "native", _u("https://s.weibo.com/weibo", q=q), "微博 (login)"),
        ("bilibili", "native", _u("https://search.bilibili.com/all", keyword=q), "videos"),
        ("vk", "native", _u("https://vk.com/search/statuses", **{"c[q]": q}), "posts (login)"),
        ("naver", "native", _u("https://search.naver.com/search.naver", where="image", query=q), "Korean images"),
    ]
    if at:
        lat, lon = at
        rows.append(("flickr", "native", f"https://www.flickr.com/map?&fLat={lat:.5f}&fLon={lon:.5f}&zl=16",
                     "geotagged photos around the point"))
    out = [{"platform": p, "kind": k, "url": u, "note": n} for p, k, u, n in rows]
    if only:
        keep = {o.strip().lower() for o in only}
        out = [r for r in out if r["platform"] in keep]
    return out
