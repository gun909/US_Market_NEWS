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
                "macropulse.cli.fetch_telegram_updates", return_value=()
            ), patch("macropulse.cli.send_telegram") as sender:
                result = main(
                    ["--latest", "--database", str(database), "--market", "demo", "--telegram"]
                )

            self.assertEqual(result, 0)
            self.assertEqual(sender.call_count, 2)
            store = HistoryStore(database)
            self.assertTrue(store.was_sent("one"))
            self.assertTrue(store.was_sent("two"))

    def test_low_neutral_is_recorded_without_telegram_notification(self):
        items = (FeedItem("one", "Quiet market update", "https://example.com/one", None, "feed"),)
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "macropulse.db"
            env = {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}
            with patch.dict(os.environ, env), patch("macropulse.cli.fetch_feed", return_value=items), patch(
                "macropulse.cli.fetch_telegram_updates", return_value=()
            ), patch("macropulse.cli.send_telegram") as sender:
                result = main(["--latest", "--database", str(database), "--market", "demo", "--telegram"])

            self.assertEqual(result, 0)
            sender.assert_not_called()
            self.assertTrue(HistoryStore(database).was_sent("one"))

    def test_high_and_medium_commands_query_database(self):
        item = FeedItem("high", "Fed unexpectedly hikes rates", "https://example.com/high", None, "feed")
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "macropulse.db"
            store = HistoryStore(database)
            from macropulse.engine import MacroPulseEngine
            from macropulse.market import DemoMarketDataProvider
            report = MacroPulseEngine().run(item.title, DemoMarketDataProvider())
            store.record_delivery(item, report, success=True)
            env = {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "123"}
            updates = ({"update_id": 7, "message": {"chat": {"id": 123}, "text": "/high"}},)
            with patch.dict(os.environ, env), patch("macropulse.cli.fetch_feed", return_value=()), patch(
                "macropulse.cli.fetch_telegram_updates", return_value=updates
            ), patch("macropulse.cli.send_telegram") as sender:
                result = main(["--latest", "--database", str(database), "--telegram"])
            self.assertEqual(result, 0)
            self.assertIn("HIGH bearish alerts", sender.call_args.args[2])
            self.assertEqual(store.get_state("telegram_update_offset"), "8")


if __name__ == "__main__":
    unittest.main()
