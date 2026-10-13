# anthropic-news-feed

An unofficial RSS feed of https://www.anthropic.com/news, which publishes no feed of its own.

Feed URL: https://lingnik.github.io/anthropic-news-feed/feed.xml

## How it works
- A GitHub Action runs `feed.py` every hour at :17.
- `feed.py` reads https://www.anthropic.com/sitemap.xml. A `/news/` URL not already in `seen.json` is a new post.
- Each new post's page is read once for its title, description and `article:published_time`.
- `feed.xml` lists the newest 50 posts by publish time. The sitemap's `lastmod` is not used, because it changes when a post is edited.
- The Action commits only when `seen.json` or `feed.xml` changed. GitHub Pages serves the repo root.

## Run locally
`python3 feed.py` (stdlib only). Tests: `python3 tests/test_feed.py`.
