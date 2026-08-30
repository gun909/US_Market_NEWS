import tempfile
import unittest
from pathlib import Path

from macropulse.engine import MacroPulseEngine
from macropulse.market import DemoMarketDataProvider
from macropulse.rss import FeedItem, parse_feed
from macropulse.storage import HistoryStore


RSS_FIXTURE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Older market story</title>
    <link>https://example.com/older</link>
    <guid>older-1</guid>
    <pubDate>Sun, 30 Aug 2026 20:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Fed unexpectedly cuts rates</title>
    <link>https://example.com/newer</link>
    <guid>newer-1</guid>
    <pubDate>Sun, 30 Aug 2026 21:00:00 GMT</pubDate>
  </item>
</channel></rss>"""


class RssAndStorageTests(unittest.TestCase):
    def test_feed_is_normalised_newest_first(self):
        items = parse_feed(RSS_FIXTURE, "https://example.com/feed")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "Fed unexpectedly cuts rates")
        self.assertEqual(items[0].published_at, "2026-08-30T21:00:00+00:00")

    def test_successful_delivery_is_not_selected_again(self):
        items = parse_feed(RSS_FIXTURE, "https://example.com/feed")
        report = MacroPulseEngine().run(items[0].title, DemoMarketDataProvider())
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "macropulse.db"
            store = HistoryStore(database)
            self.assertEqual(store.latest_unsent(items), items[0])
            store.record_delivery(items[0], report, success=True)
            self.assertTrue(store.was_sent(items[0].fingerprint))
            self.assertEqual(store.latest_unsent(items), items[1])

    def test_failed_delivery_remains_retryable(self):
        item = FeedItem("abc", "Story", "https://example.com", None, "https://feed.example.com")
        report = MacroPulseEngine().run(item.title, DemoMarketDataProvider())
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "macropulse.db")
            store.record_delivery(item, report, success=False, error="network timeout")
            self.assertFalse(store.was_sent(item.fingerprint))
            self.assertEqual(store.latest_unsent((item,)), item)


if __name__ == "__main__":
    unittest.main()
