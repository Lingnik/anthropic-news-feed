"""Build an RSS feed of anthropic.com/news from the site's sitemap.

anthropic.com publishes no feed. The sitemap lists every /news/ post, so a
post is new when its URL first appears there. Each new post's page is read
once for its title, description and publish time; seen.json keeps them.
feed.xml carries the newest MAX_ITEMS posts by publish time.

Run: python3 feed.py   (stdlib only; writes seen.json and feed.xml here)
"""
import email.utils
import html
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

SITEMAP = "https://www.anthropic.com/sitemap.xml"
NEWS = "https://www.anthropic.com/news/"
HERE = Path(__file__).resolve().parent
SEEN = HERE / "seen.json"
FEED = HERE / "feed.xml"
MAX_ITEMS = 50
MAX_FETCH = 400
PAUSE_S = 0.5
UA = "anthropic-news-feed (+https://github.com/Lingnik/anthropic-news-feed)"


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def news_urls(sitemap: str) -> list[str]:
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap)
    return sorted({u for u in locs if u.startswith(NEWS) and len(u) > len(NEWS)})


def meta(page: str, key: str) -> str:
    for tag in re.findall(r"<meta\s[^>]*>", page):
        if re.search(rf'(property|name)="{re.escape(key)}"', tag):
            m = re.search(r'content="([^"]*)"', tag)
            if m:
                return html.unescape(m.group(1)).strip()
    return ""


def post_info(url: str, page: str, now: float) -> dict:
    title = meta(page, "og:title")
    if not title:
        m = re.search(r"<title>(.*?)</title>", page, re.S)
        title = html.unescape(m.group(1)).strip() if m else url.rsplit("/", 1)[-1]
    published = meta(page, "article:published_time")
    return {"title": title,
            "description": meta(page, "og:description") or meta(page, "description"),
            "published": published,
            "first_seen": datetime.fromtimestamp(now, timezone.utc).isoformat()}


def when(info: dict) -> datetime:
    for key in ("published", "first_seen"):
        try:
            d = datetime.fromisoformat(info[key].replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
    return datetime.fromtimestamp(0, timezone.utc)


def render(seen: dict, now: float) -> str:
    items = sorted(seen.items(), key=lambda kv: when(kv[1]), reverse=True)[:MAX_ITEMS]
    newest = when(items[0][1]) if items else datetime.fromtimestamp(now, timezone.utc)
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0"><channel>',
           "<title>Anthropic News</title>",
           f"<link>{NEWS}</link>",
           "<description>Posts from anthropic.com/news, built from the site's sitemap. "
           "Unofficial.</description>",
           f"<lastBuildDate>{email.utils.format_datetime(newest)}</lastBuildDate>"]
    for url, info in items:
        out += ["<item>",
                f"<title>{escape(info.get('title') or url)}</title>",
                f"<link>{escape(url)}</link>",
                f'<guid isPermaLink="true">{escape(url)}</guid>',
                f"<pubDate>{email.utils.format_datetime(when(info))}</pubDate>"]
        if info.get("description"):
            out.append(f"<description>{escape(info['description'])}</description>")
        out.append("</item>")
    out.append("</channel></rss>")
    return "\n".join(out) + "\n"


def update(seen: dict, urls: list[str], fetch, now: float) -> int:
    new = [u for u in urls if u not in seen]
    for url in new[:MAX_FETCH]:
        try:
            seen[url] = post_info(url, fetch(url), now)
            time.sleep(PAUSE_S)
        except OSError as e:
            print(f"skip {url}: {e}", file=sys.stderr)
    return len(new)


def main() -> int:
    now = time.time()
    seen = json.loads(SEEN.read_text()) if SEEN.exists() else {}
    new = update(seen, news_urls(get(SITEMAP)), get, now)
    SEEN.write_text(json.dumps(seen, indent=1, sort_keys=True) + "\n")
    FEED.write_text(render(seen, now))
    print(f"{new} new, {len(seen)} known")
    return 0


if __name__ == "__main__":
    sys.exit(main())
