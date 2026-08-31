from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .models import AlertReport
from .rss import FeedItem


def _report_value(report: dict, key: str, default: str = "") -> str:
    value = report.get(key, default)
    return str(value) if value is not None else default


class HistoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialise(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS deliveries (
                        fingerprint TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        link TEXT NOT NULL,
                        source_url TEXT NOT NULL,
                        published_at TEXT,
                        attempted_at TEXT NOT NULL,
                        sent_at TEXT,
                        success INTEGER NOT NULL CHECK (success IN (0, 1)),
                        error TEXT,
                        report_json TEXT NOT NULL
                    )
                    """
                )
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(deliveries)").fetchall()
                }
                if "notified" not in columns:
                    connection.execute(
                        "ALTER TABLE deliveries ADD COLUMN notified INTEGER NOT NULL DEFAULT 1"
                    )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_deliveries_sent_at ON deliveries(sent_at)"
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bot_state (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )

    def was_sent(self, fingerprint: str) -> bool:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT success FROM deliveries WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
        return bool(row and row["success"])

    def latest_unsent(self, items: tuple[FeedItem, ...]) -> FeedItem | None:
        return next(iter(self.unsent(items)), None)

    def unsent(self, items: tuple[FeedItem, ...]) -> tuple[FeedItem, ...]:
        if not items:
            return ()
        with closing(self._connect()) as connection:
            sent = {
                row["fingerprint"]
                for row in connection.execute(
                    "SELECT fingerprint FROM deliveries WHERE success = 1"
                ).fetchall()
            }
        return tuple(item for item in items if item.fingerprint not in sent)

    def record_delivery(
        self,
        item: FeedItem,
        report: AlertReport,
        *,
        success: bool,
        error: str | None = None,
        notified: bool = True,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sent_at = now if success else None
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO deliveries (
                        fingerprint, title, link, source_url, published_at,
                        attempted_at, sent_at, success, error, report_json, notified
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(fingerprint) DO UPDATE SET
                        attempted_at = excluded.attempted_at,
                        sent_at = excluded.sent_at,
                        success = excluded.success,
                        error = excluded.error,
                        report_json = excluded.report_json,
                        notified = excluded.notified
                    """,
                    (
                        item.fingerprint,
                        item.title,
                        item.link,
                        item.source_url,
                        item.published_at,
                        now,
                        sent_at,
                        int(success),
                        error,
                        json.dumps(report.to_dict(), ensure_ascii=False),
                        int(notified),
                    ),
                )

    def get_state(self, key: str, default: str = "") -> str:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT value FROM bot_state WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO bot_state (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, value),
                )

    def query_alerts(
        self,
        *,
        confidence: str,
        sentiment: str | None = None,
    ) -> tuple[dict[str, str], ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT title, link, attempted_at, report_json
                FROM deliveries
                WHERE success = 1
                ORDER BY attempted_at DESC
                """
            ).fetchall()

        matches: list[dict[str, str]] = []
        for row in rows:
            report = json.loads(row["report_json"])
            analysis = report.get("analysis", {})
            if _report_value(report, "confidence").upper() != confidence.upper():
                continue
            if sentiment and _report_value(analysis, "sentiment").lower() != sentiment.lower():
                continue
            affected = analysis.get("affected") or ()
            matches.append(
                {
                    "time": row["attempted_at"],
                    "confidence": _report_value(report, "confidence"),
                    "sentiment": _report_value(analysis, "sentiment"),
                    "title": row["title"],
                    "affected": ", ".join(str(value) for value in affected) or "N/A",
                    "link": row["link"],
                }
            )
        return tuple(matches)
