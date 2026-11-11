"""Add posts on X from the accounts in x-accounts.txt to the feed.

X publishes no free feed. fxtwitter's profile endpoint returns an account's
newest posts without a login. x_seen.json keeps, per account, the highest post
id seen and the count of failed runs in a row, plus the posts themselves in the
same shape as seen.json; feed.py merges them into feed.xml.

The first run for an account records its newest id and adds nothing, so a new
account does not flood the channel with its back catalog.

A failed or empty fetch adds nothing and logs one line. The third failure in a
row for an account writes `alert=<accounts>` to $GITHUB_OUTPUT, which fails the
workflow run once; the count keeps rising, so later failures stay quiet until a
success resets it.

Run: python3 x_feed.py   (stdlib only; writes x_seen.json here)
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCOUNTS = HERE / "x-accounts.txt"
STATE = HERE / "x_seen.json"
API = "https://api.fxtwitter.com/2/profile/{}/statuses"
UA = "anthropic-news-feed (+https://github.com/Lingnik/anthropic-news-feed)"
ALERT_AT = 3
KEEP_PER_ACCOUNT = 100
TITLE_LEN = 100


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def accounts(text: str) -> list[str]:
    names = (line.split("#", 1)[0].strip().lstrip("@") for line in text.splitlines())
    return [n for n in names if n]


def own_posts(account: str, payload: dict) -> list[dict]:
    """The account's own posts and replies, without reposts of other accounts."""
    out = []
    for r in payload.get("results") or []:
        author = (r.get("author") or {}).get("screen_name", "")
        if author.lower() != account.lower() or r.get("reposted_by"):
            continue
        if str(r.get("id", "")).isdigit() and r.get("url"):
            out.append(r)
    return out


def item(account: str, post: dict, now: float) -> tuple[str, dict]:
    text = (post.get("text") or "").strip()
    first = text.splitlines()[0] if text else post["url"]
    if len(first) > TITLE_LEN:
        first = first[:TITLE_LEN - 1].rstrip() + "…"
    try:
        published = datetime.fromtimestamp(int(post["created_timestamp"]), timezone.utc)
    except (KeyError, TypeError, ValueError):
        published = datetime.fromtimestamp(now, timezone.utc)
    return post["url"], {"title": f"@{account}: {first}",
                         "description": text,
                         "published": published.isoformat(),
                         "first_seen": datetime.fromtimestamp(now, timezone.utc).isoformat(),
                         "account": account}


def update(state: dict, names: list[str], fetch, now: float) -> tuple[int, list[str]]:
    """Fetch each account once. Returns (posts added, accounts to alert on)."""
    accts = state.setdefault("accounts", {})
    items = state.setdefault("items", {})
    added, alert = 0, []
    for name in names:
        acct = accts.setdefault(name, {"max_id": None, "failures": 0})
        try:
            posts = own_posts(name, fetch(API.format(name)))
            if not posts:
                raise ValueError("no posts in the response")
        except (OSError, ValueError) as e:
            acct["failures"] = acct.get("failures", 0) + 1
            print(f"x {name}: fetch failed ({acct['failures']} in a row): {e}", file=sys.stderr)
            if acct["failures"] == ALERT_AT:
                alert.append(name)
            continue
        acct["failures"] = 0
        newest = max(int(p["id"]) for p in posts)
        if acct.get("max_id") is None:
            acct["max_id"] = str(newest)
            print(f"x {name}: first run, starting after {newest}")
            continue
        floor = int(acct["max_id"])
        for p in sorted(posts, key=lambda p: int(p["id"])):
            if int(p["id"]) > floor:
                url, info = item(name, p, now)
                items[url] = info
                added += 1
        acct["max_id"] = str(max(newest, floor))
    prune(items)
    return added, alert


def post_id(url: str) -> int:
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def prune(items: dict) -> None:
    by_account: dict[str, list[str]] = {}
    for url, info in items.items():
        by_account.setdefault(info.get("account", ""), []).append(url)
    for urls in by_account.values():
        urls.sort(key=post_id)
        for url in urls[:-KEEP_PER_ACCOUNT]:
            del items[url]


def load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> int:
    state = load(STATE)
    added, alert = update(state, accounts(ACCOUNTS.read_text()), get_json, time.time())
    STATE.write_text(json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"x: {added} new, {len(state.get('items', {}))} kept")
    if alert:
        print(f"x: {ALERT_AT} failed fetches in a row for {', '.join(alert)}", file=sys.stderr)
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a") as f:
                f.write(f"alert={','.join(alert)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
