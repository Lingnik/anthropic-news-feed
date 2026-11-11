# anthropic-news-feed

An unofficial RSS feed of https://www.anthropic.com/news, which publishes no feed of its own, plus posts on X from the accounts in `x-accounts.txt` (ClaudeDevs first).

Feed URL: https://lingnik.com/anthropic-news-feed/feed.xml

## How it works
- A GitHub Action runs `x_feed.py`, then `feed.py`, every 30 minutes, at :17 and :47.
- `feed.py` reads https://www.anthropic.com/sitemap.xml. A `/news/` URL not already in `seen.json` is a new post.
- Each new post's page is read once for its title, description and `article:published_time`.
- `feed.xml` lists the newest 50 posts by publish time. The sitemap's `lastmod` is not used, because it changes when a post is edited.
- `x_feed.py` reads `https://api.fxtwitter.com/2/profile/<account>/statuses`, a third-party service with no uptime commitment. A post with an id above the highest one in `x_seen.json` is new. Reposts of other accounts are skipped; an account's replies in its own threads are kept. A new account's first run records its newest id and adds nothing.
- A failed or empty X fetch adds nothing and logs one line. The third failure in a row for an account fails the run once, which is the alert; a success resets the count.
- `feed.py` merges the X posts in `x_seen.json` into `feed.xml` with the news posts.
- The Action commits only when `seen.json`, `x_seen.json` or `feed.xml` changed. GitHub Pages serves the repo root.

## Run locally
`python3 x_feed.py && python3 feed.py` (stdlib only). Tests: `python3 tests/test_feed.py` and `python3 tests/test_x_feed.py`. To follow another account, add its handle to `x-accounts.txt`.
