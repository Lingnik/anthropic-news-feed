import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import feed  # noqa: E402

SITEMAP = """<urlset>
<url><loc>https://www.anthropic.com/news/old-post</loc><lastmod>2026-10-09</lastmod></url>
<url><loc>https://www.anthropic.com/news/new-post</loc></url>
<url><loc>https://www.anthropic.com/news/</loc></url>
<url><loc>https://www.anthropic.com/research/other</loc></url>
</urlset>"""


def page(title, published, desc="d &amp; e"):
    return (f'<html><head><meta property="og:title" content="{title}"/>'
            f'<meta property="og:description" content="{desc}"/>'
            f'<meta property="article:published_time" content="{published}"/></head></html>')


PAGES = {"https://www.anthropic.com/news/old-post": page("Old", "2026-06-11T13:00:00.000Z"),
         "https://www.anthropic.com/news/new-post": page("New &amp; shiny", "2026-10-12T17:00:00.000Z")}


class FeedTests(unittest.TestCase):
    def setUp(self):
        feed.PAUSE_S = 0

    def test_only_news_posts_are_listed(self):
        self.assertEqual(feed.news_urls(SITEMAP), sorted(PAGES))

    def test_items_order_by_publish_time_not_lastmod(self):
        seen = {}
        feed.update(seen, feed.news_urls(SITEMAP), PAGES.__getitem__, 0)
        root = ET.fromstring(feed.render(seen, 0))
        titles = [t.text for t in root.iter("title")][1:]
        self.assertEqual(titles, ["New & shiny", "Old"])
        self.assertIn("12 Oct 2026", root.find("channel/item/pubDate").text)

    def test_a_known_post_is_not_fetched_again(self):
        seen = {}
        feed.update(seen, feed.news_urls(SITEMAP), PAGES.__getitem__, 0)
        calls = []
        new = feed.update(seen, feed.news_urls(SITEMAP), lambda u: calls.append(u), 0)
        self.assertEqual((new, calls), (0, []))

    def test_unchanged_input_renders_the_same_feed(self):
        seen = {}
        feed.update(seen, feed.news_urls(SITEMAP), PAGES.__getitem__, 0)
        self.assertEqual(feed.render(seen, 0), feed.render(seen, 999999))

    def test_a_failed_fetch_is_retried_next_run(self):
        seen = {}

        def boom(url):
            raise OSError("down")

        feed.update(seen, feed.news_urls(SITEMAP), boom, 0)
        self.assertEqual(seen, {})

    def test_a_publish_time_without_a_zone_sorts_as_utc(self):
        seen = {"a": {"published": "2026-10-01T09:00:00"},
                "b": {"published": "2026-10-02T09:00:00.000Z"}}
        root = ET.fromstring(feed.render(seen, 0))
        self.assertEqual([i.find("link").text for i in root.iter("item")], ["b", "a"])


if __name__ == "__main__":
    unittest.main()
