from __future__ import annotations

import json

from .models import AlertReport

ARROWS = {"up": "↑", "down": "↓", "flat": "→", "unknown": "?"}


def format_text(report: AlertReport) -> str:
    sentiment = report.analysis.sentiment.upper()
    affected = "\n".join(report.analysis.affected) or "N/A"
    checks = "\n".join(f"{check.label} {ARROWS[check.direction]}" for check in report.checks)
    return (
        f"News:\n{report.analysis.headline}\n\n"
        f"AI:\n{report.analysis.thesis}\n\n"
        f"Affected:\n{affected}\n\n"
        f"Check:\n{checks}\n\n"
        f"Result:\n{report.confidence} confidence {sentiment.lower()} alert"
    )


def format_json(report: AlertReport) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)

