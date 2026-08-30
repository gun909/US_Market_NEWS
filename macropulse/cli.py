from __future__ import annotations

import argparse
import os
import sys

from .analyzer import FinBertNewsAnalyzer, RuleBasedNewsAnalyzer
from .engine import MacroPulseEngine
from .formatters import format_json, format_text
from .market import DemoMarketDataProvider, YFinanceMarketDataProvider
from .rss import DEFAULT_RSS_URL, FeedItem, fetch_feed
from .storage import HistoryStore
from .telegram import send_telegram


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze US market news and confirm it with market data")
    parser.add_argument("news", nargs="?", help="news headline; stdin is used when omitted")
    parser.add_argument("--latest", action="store_true", help="analyze the latest unsent RSS article")
    parser.add_argument(
        "--rss-url",
        default=os.environ.get("NEWS_RSS_URL") or DEFAULT_RSS_URL,
        help="RSS/Atom feed used by --latest",
    )
    parser.add_argument("--database", default="data/macropulse.db", help="SQLite delivery history")
    parser.add_argument("--market", choices=("demo", "yfinance"), default="demo")
    parser.add_argument("--analyzer", choices=("rules", "finbert"), default="rules")
    parser.add_argument("--json", action="store_true", help="print machine-readable output")
    parser.add_argument("--telegram", action="store_true", help="send the report using TELEGRAM_* env vars")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.latest and args.news:
        build_parser().error("use either a news headline or --latest, not both")

    item: FeedItem | None = None
    store: HistoryStore | None = None
    if args.latest:
        store = HistoryStore(args.database)
        item = store.latest_unsent(fetch_feed(args.rss_url))
        if item is None:
            print("No unsent RSS news found.")
            return 0
        news = item.title
    else:
        news = args.news or (sys.stdin.read().strip() if not sys.stdin.isatty() else "")
    if not news:
        build_parser().error("provide a news headline, pipe stdin, or use --latest")

    analyzer = FinBertNewsAnalyzer() if args.analyzer == "finbert" else RuleBasedNewsAnalyzer()
    market = YFinanceMarketDataProvider() if args.market == "yfinance" else DemoMarketDataProvider()
    report = MacroPulseEngine(analyzer).run(news, market)
    output = format_json(report) if args.json else format_text(report)
    if item and not args.json:
        output = f"{output}\n\nSource:\n{item.link}"
    # Windows PowerShell can otherwise replace the directional arrows under a GBK locale.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(output)

    if args.telegram:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise SystemExit("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
        telegram_text = format_text(report)
        if item:
            telegram_text = f"{telegram_text}\n\nSource:\n{item.link}"
        try:
            send_telegram(token, chat_id, telegram_text)
        except Exception as exc:
            if store and item:
                store.record_delivery(item, report, success=False, error=str(exc))
            raise
        if store and item:
            store.record_delivery(item, report, success=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
