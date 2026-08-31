import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from macropulse.cli import main
from macropulse.rss import FeedItem
from macropulse.storage import HistoryStore


class CliTests(unittest.TestCase):
    def test_latest_sends_every_unsent_item_and_records_each_success(self):
        items = (
            FeedItem("one", "Fed unexpectedly cuts rates", "https://example.com/one", None, "feed"),
            FeedItem("two", "US-Iran war sends oil prices higher", "https://example.com/two", None, "feed"),
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "macropulse.db"
            env = {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}
            with patch.dict(os.environ, env), patch("macropulse.cli.fetch_feed", return_value=items), patch(
                "macropulse.cli.send_telegram"
            ) as sender:
                result = main(
                    ["--latest", "--database", str(database), "--market", "demo", "--telegram"]
                )

            self.assertEqual(result, 0)
            self.assertEqual(sender.call_count, 2)
            store = HistoryStore(database)
            self.assertTrue(store.was_sent("one"))
            self.assertTrue(store.was_sent("two"))


if __name__ == "__main__":
    unittest.main()
