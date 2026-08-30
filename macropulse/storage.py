from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .models import AlertReport
from .rss import FeedItem


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
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_deliveries_sent_at ON deliveries(sent_at)"
                )

    def was_sent(self, fingerprint: str) -> bool:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT success FROM deliveries WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
        return bool(row and row["success"])

    def latest_unsent(self, items: tuple[FeedItem, ...]) -> FeedItem | None:
        return next((item for item in items if not self.was_sent(item.fingerprint)), None)

    def record_delivery(
        self,
        item: FeedItem,
        report: AlertReport,
        *,
        success: bool,
        error: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sent_at = now if success else None
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO deliveries (
                        fingerprint, title, link, source_url, published_at,
                        attempted_at, sent_at, success, error, report_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(fingerprint) DO UPDATE SET
                        attempted_at = excluded.attempted_at,
                        sent_at = excluded.sent_at,
                        success = excluded.success,
                        error = excluded.error,
                        report_json = excluded.report_json
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
                    ),
                )
