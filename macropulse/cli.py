from __future__ import annotations

import argparse
import json
import os
import sys

from .analyzer import FinBertNewsAnalyzer, RuleBasedNewsAnalyzer
from .engine import MacroPulseEngine
from .formatters import format_text
from .market import DemoMarketDataProvider, YFinanceMarketDataProvider
from .models import AlertReport
from .rss import DEFAULT_RSS_URL, FeedItem, fetch_feed
from .storage import HistoryStore
from .telegram import fetch_telegram_updates, send_telegram, split_telegram_text


BOT_HELP = (
    "MacroPulse commands:\n"
    "/high - all HIGH confidence bearish alerts\n"
    "/medium - all MEDIUM confidence alerts\n"
    "/help - show this help"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze US market news and confirm it with market data")
    parser.add_argument("news", nargs="?", help="news headline; stdin is used when omitted")
    parser.add_argument("--latest", action="store_true", help="analyze every unsent RSS article")
    parser.add_argument(
        "--rss-url",
        default=os.environ.get("NEWS_RSS_URL") or DEFAULT_RSS_URL,
        help="RSS/Atom feed used by --latest",
    )
    parser.add_argument("--database", default="data/macropulse.db", help="SQLite delivery history")
    parser.add_argument("--market", choices=("demo", "yfinance"), default="demo")
    parser.add_argument("--analyzer", choices=("rules", "finbert"), default="rules")
    parser.add_argument("--json", action="store_true", help="print machine-readable output")
    parser.add_argument("--telegram", action="store_true", help="send reports using TELEGRAM_* env vars")
    return parser


def _with_source(report: AlertReport, item: FeedItem | None) -> str:
    text = format_text(report)
    return f"{text}\n\nSource:\n{item.link}" if item else text


def _format_query_rows(title: str, rows: tuple[dict[str, str], ...]) -> str:
    if not rows:
        return f"{title}\n\nNo matching records in data/macropulse.db."
    records = []
    for index, row in enumerate(rows, 1):
        records.append(
            f"[{index}] {row['time']}\n"
            f"Confidence: {row['confidence']}\n"
            f"Direction: {row['sentiment']}\n"
            f"News: {row['title']}\n"
            f"Affected: {row['affected']}\n"
            f"Source: {row['link']}"
        )
    return f"{title}\nRows: {len(rows)}\n\n" + "\n\n".join(records)


def _process_bot_commands(store: HistoryStore, token: str, chat_id: str) -> None:
    offset = int(store.get_state("telegram_update_offset", "0") or 0)
    updates = fetch_telegram_updates(token, offset)
    for update in updates:
        next_offset = int(update.get("update_id", 0)) + 1
        message = update.get("message") or {}
        incoming_chat = str((message.get("chat") or {}).get("id", ""))
        command = str(message.get("text", "")).strip().split(maxsplit=1)[0].lower()
        command = command.split("@", 1)[0]
        if incoming_chat == str(chat_id):
            if command in {"/high", "/high_bearish"}:
                rows = store.query_alerts(confidence="HIGH", sentiment="bearish")
                reply = _format_query_rows("HIGH bearish alerts", rows)
            elif command == "/medium":
                rows = store.query_alerts(confidence="MEDIUM")
                reply = _format_query_rows("MEDIUM confidence alerts", rows)
            elif command in {"/help", "/start"}:
                reply = BOT_HELP
            else:
                reply = ""
            for chunk in split_telegram_text(reply) if reply else ():
                send_telegram(token, chat_id, chunk)
        store.set_state("telegram_update_offset", str(next_offset))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.latest and args.news:
        parser.error("use either a news headline or --latest, not both")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if args.telegram and (not token or not chat_id):
        raise SystemExit("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")

    store: HistoryStore | None = None
    feed_items: tuple[FeedItem, ...] = ()
    if args.latest:
        store = HistoryStore(args.database)
        if args.telegram:
            try:
                _process_bot_commands(store, token or "", chat_id or "")
            except Exception as exc:
                print(f"Telegram command polling failed: {exc}", file=sys.stderr)
        feed_items = store.unsent(fetch_feed(args.rss_url))
        if not feed_items:
            print("No unsent RSS news found.")
        work: tuple[tuple[FeedItem | None, str], ...] = tuple(
            (item, item.title) for item in feed_items
        )
    else:
        news = args.news or (sys.stdin.read().strip() if not sys.stdin.isatty() else "")
        if not news:
            parser.error("provide a news headline, pipe stdin, or use --latest")
        work = ((None, news),)

    analyzer = FinBertNewsAnalyzer() if args.analyzer == "finbert" else RuleBasedNewsAnalyzer()
    market = YFinanceMarketDataProvider() if args.market == "yfinance" else DemoMarketDataProvider()
    engine = MacroPulseEngine(analyzer)
    reports = tuple((item, engine.run(headline, market)) for item, headline in work)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.json and reports:
        payload = [report.to_dict() for _, report in reports]
        print(json.dumps(payload if args.latest else payload[0], ensure_ascii=False, indent=2))
    elif reports:
        print("\n\n---\n\n".join(_with_source(report, item) for item, report in reports))

    errors: list[str] = []
    if args.telegram:
        for item, report in reports:
            if report.confidence == "LOW" and report.analysis.sentiment == "neutral":
                if store and item:
                    store.record_delivery(item, report, success=True, notified=False)
                continue
            try:
                send_telegram(token or "", chat_id or "", _with_source(report, item))
            except Exception as exc:
                if store and item:
                    store.record_delivery(item, report, success=False, error=str(exc))
                errors.append(f"{report.analysis.headline}: {exc}")
                continue
            if store and item:
                store.record_delivery(item, report, success=True)

    if errors:
        print(f"Telegram failed for {len(errors)} article(s):", file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
