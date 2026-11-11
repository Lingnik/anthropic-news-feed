import copy
import json
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import feed  # noqa: E402
import x_feed  # noqa: E402

# fxtwitter's /2/profile/ClaudeDevs/statuses, recorded 2026-11-10, trimmed to the fields used.
RECORDED = json.loads((Path(__file__).parent / "fixtures" / "claudedevs-statuses.json").read_text())
NEWEST = "2120275296637321476"
RESET_URL = f"https://x.com/ClaudeDevs/status/{NEWEST}"


def serve(payload):
    return lambda url: copy.deepcopy(payload)


def older_than(payload, post_id):
    """The recorded page as it looked before post_id was published."""
    p = copy.deepcopy(payload)
    p["results"] = [r for r in p["results"] if int(r["id"]) < int(post_id)]
    return p


def boom(url):
    raise OSError("HTTP Error 503")


class XFeedTests(unittest.TestCase):
    def test_accounts_file_skips_blanks_comments_and_at_signs(self):
        self.assertEqual(x_feed.accounts("ClaudeDevs\n\n# off for now\n@ClaudeAI  # second\n"),
                         ["ClaudeDevs", "ClaudeAI"])

    def test_first_run_records_the_newest_id_and_adds_nothing(self):
        state = {}
        added, alert = x_feed.update(state, ["ClaudeDevs"], serve(RECORDED), 0)
        self.assertEqual((added, alert, state["items"]), (0, [], {}))
        self.assertEqual(state["accounts"]["ClaudeDevs"]["max_id"], NEWEST)

    def test_a_new_post_is_added_once(self):
        state = {}
        x_feed.update(state, ["ClaudeDevs"], serve(older_than(RECORDED, NEWEST)), 0)
        added, _ = x_feed.update(state, ["ClaudeDevs"], serve(RECORDED), 100)
        self.assertEqual((added, list(state["items"])), (1, [RESET_URL]))
        info = state["items"][RESET_URL]
        self.assertTrue(info["title"].startswith("@ClaudeDevs: We've given all Pro"))
        self.assertIn("clau.de/reset", info["description"])
        self.assertEqual(info["published"], "2026-11-10T21:59:58+00:00")
        again, _ = x_feed.update(state, ["ClaudeDevs"], serve(RECORDED), 200)
        self.assertEqual(again, 0)

    def test_a_thread_adds_every_post_newer_than_the_mark(self):
        state = {}
        x_feed.update(state, ["ClaudeDevs"], serve(older_than(RECORDED, "2120227979041341943")), 0)
        added, _ = x_feed.update(state, ["ClaudeDevs"], serve(RECORDED), 100)
        self.assertEqual(added, 4)

    def test_reposts_of_other_accounts_are_skipped(self):
        p = copy.deepcopy(RECORDED)
        p["results"][0]["reposted_by"] = {"screen_name": "ClaudeDevs"}
        p["results"][1]["author"]["screen_name"] = "someoneelse"
        ids = [r["id"] for r in x_feed.own_posts("claudedevs", p)]
        self.assertNotIn(p["results"][0]["id"], ids)
        self.assertNotIn(p["results"][1]["id"], ids)
        self.assertEqual(len(ids), len(p["results"]) - 2)

    def test_a_failed_or_empty_fetch_adds_nothing_and_keeps_the_mark(self):
        state = {}
        x_feed.update(state, ["ClaudeDevs"], serve(older_than(RECORDED, NEWEST)), 0)
        mark = state["accounts"]["ClaudeDevs"]["max_id"]
        for fetch in (boom, serve({"code": 200, "results": []}), serve({"code": 404})):
            added, _ = x_feed.update(state, ["ClaudeDevs"], fetch, 0)
            self.assertEqual(added, 0)
        self.assertEqual(state["accounts"]["ClaudeDevs"]["max_id"], mark)
        self.assertEqual(state["items"], {})

    def test_the_third_failure_in_a_row_alerts_once(self):
        state = {}
        alerts = [x_feed.update(state, ["ClaudeDevs"], boom, 0)[1] for _ in range(5)]
        self.assertEqual(alerts, [[], [], ["ClaudeDevs"], [], []])

    def test_a_success_resets_the_failure_count(self):
        state = {}
        x_feed.update(state, ["ClaudeDevs"], boom, 0)
        x_feed.update(state, ["ClaudeDevs"], boom, 0)
        x_feed.update(state, ["ClaudeDevs"], serve(RECORDED), 0)
        self.assertEqual(state["accounts"]["ClaudeDevs"]["failures"], 0)
        self.assertEqual(x_feed.update(state, ["ClaudeDevs"], boom, 0)[1], [])

    def test_one_failing_account_does_not_stop_another(self):
        state = {"accounts": {"ClaudeDevs": {"max_id": "1", "failures": 0}}}

        def fetch(url):
            if "Broken" in url:
                raise OSError("down")
            return copy.deepcopy(RECORDED)

        added, _ = x_feed.update(state, ["Broken", "ClaudeDevs"], fetch, 0)
        self.assertEqual(added, len(RECORDED["results"]))
        self.assertEqual(state["accounts"]["Broken"]["failures"], 1)

    def test_old_posts_are_pruned_per_account(self):
        x_feed.KEEP_PER_ACCOUNT, keep = 3, x_feed.KEEP_PER_ACCOUNT
        try:
            state = {"accounts": {"ClaudeDevs": {"max_id": "1", "failures": 0}}}
            x_feed.update(state, ["ClaudeDevs"], serve(RECORDED), 0)
            self.assertEqual(sorted(state["items"], key=x_feed.post_id)[-1], RESET_URL)
            self.assertEqual(len(state["items"]), 3)
        finally:
            x_feed.KEEP_PER_ACCOUNT = keep

    def test_posts_render_in_the_news_feed_by_publish_time(self):
        state = {}
        x_feed.update(state, ["ClaudeDevs"], serve(older_than(RECORDED, NEWEST)), 0)
        x_feed.update(state, ["ClaudeDevs"], serve(RECORDED), 0)
        news = {"https://www.anthropic.com/news/roadshow-launch":
                {"title": "Roadshow", "published": "2026-11-10T00:00:00.000Z"}}
        root = ET.fromstring(feed.render({**news, **state["items"]}, 0))
        links = [i.find("link").text for i in root.iter("item")]
        self.assertEqual(links, [RESET_URL, "https://www.anthropic.com/news/roadshow-launch"])


if __name__ == "__main__":
    unittest.main()
