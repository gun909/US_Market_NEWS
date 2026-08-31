from __future__ import annotations

import json

from .models import AlertReport

ARROWS = {"up": "↑", "down": "↓", "flat": "→", "unknown": "?"}


def _format_affected(report: AlertReport) -> str:
    sections: list[str] = []
    if report.analysis.positive:
        sections.append("Positive correlation:\n" + "\n".join(report.analysis.positive))
    if report.analysis.negative:
        sections.append("Negative correlation:\n" + "\n".join(report.analysis.negative))
    if sections:
        return "\n\n".join(sections)
    if report.analysis.affected:
        return "Related:\n" + "\n".join(report.analysis.affected)
    return "N/A"


def format_text(report: AlertReport) -> str:
    sentiment = report.analysis.sentiment.upper()
    affected = _format_affected(report)
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
