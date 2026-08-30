from __future__ import annotations

import re
from dataclasses import dataclass

from .models import NewsAnalysis


@dataclass(frozen=True)
class EventRule:
    name: str
    patterns: tuple[str, ...]
    sentiment: str
    thesis: str
    affected: tuple[str, ...]
    strength: float


EVENT_RULES = (
    EventRule(
        "fed_rate_cut",
        (r"\bfed(?:eral reserve)?\b.*\b(cut|cuts|lower|lowers|slashed)\b.*\brate", r"\brate cut\b"),
        "bullish",
        "Bullish for growth stocks",
        ("QQQ", "NVDA", "MSFT", "AMZN"),
        0.88,
    ),
    EventRule(
        "fed_rate_hike",
        (r"\bfed(?:eral reserve)?\b.*\b(hike|hikes|raise|raises)\b.*\brate", r"\brate hike\b"),
        "bearish",
        "Bearish for rate-sensitive growth stocks",
        ("QQQ", "NVDA", "MSFT", "AMZN"),
        0.88,
    ),
    EventRule(
        "inflation_cools",
        (r"\b(cpi|inflation)\b.*\b(cools|falls|slows|below)\b",),
        "bullish",
        "Lower inflation supports risk assets",
        ("SPY", "QQQ", "IWM"),
        0.78,
    ),
    EventRule(
        "inflation_heats",
        (r"\b(cpi|inflation)\b.*\b(rises|jumps|accelerates|hotter|above)\b",),
        "bearish",
        "Higher inflation pressures risk assets",
        ("SPY", "QQQ", "IWM"),
        0.78,
    ),
    EventRule(
        "earnings_beat",
        (r"\b(earnings|revenue)\b.*\b(beat|beats|above)\b", r"\bbeat(s)? estimates\b"),
        "bullish",
        "Positive earnings surprise",
        (),
        0.72,
    ),
    EventRule(
        "earnings_miss",
        (r"\b(earnings|revenue)\b.*\b(miss|misses|below)\b", r"\bmiss(es)? estimates\b"),
        "bearish",
        "Negative earnings surprise",
        (),
        0.72,
    ),
)

TICKER_RE = re.compile(r"(?<![A-Za-z])(?:\$([A-Z]{1,5})|([A-Z]{2,5}))(?![A-Za-z])")
TICKER_STOPWORDS = {"A", "AI", "CEO", "CPI", "ETF", "FED", "GDP", "SEC", "US", "USA"}


class RuleBasedNewsAnalyzer:
    """Deterministic fallback. It keeps the application useful without a GPU or API."""

    def analyze(self, headline: str) -> NewsAnalysis:
        clean = " ".join(headline.strip().split())
        if not clean:
            raise ValueError("news headline cannot be empty")

        lower = clean.lower()
        rule = next(
            (rule for rule in EVENT_RULES if any(re.search(pattern, lower) for pattern in rule.patterns)),
            None,
        )
        candidates = (prefixed or bare for prefixed, bare in TICKER_RE.findall(clean))
        explicit = tuple(dict.fromkeys(ticker for ticker in candidates if ticker not in TICKER_STOPWORDS))

        if rule:
            affected = explicit or rule.affected
            return NewsAnalysis(
                clean,
                rule.sentiment,  # type: ignore[arg-type]
                rule.thesis,
                affected,
                rule.name,
                rule.strength,
            )

        positive = sum(word in lower for word in ("surges", "rallies", "upgrade", "approval", "record high"))
        negative = sum(word in lower for word in ("plunges", "falls", "downgrade", "lawsuit", "default"))
        sentiment = "bullish" if positive > negative else "bearish" if negative > positive else "neutral"
        thesis = {
            "bullish": "Positive market catalyst",
            "bearish": "Negative market catalyst",
            "neutral": "No strong directional catalyst detected",
        }[sentiment]
        return NewsAnalysis(clean, sentiment, thesis, explicit, "unclassified", 0.55 if sentiment != "neutral" else 0.35)  # type: ignore[arg-type]


class FinBertNewsAnalyzer:
    """Optional FinBERT overlay; event classification remains deterministic and auditable."""

    def __init__(self) -> None:
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError("Install AI support with: pip install -e .[ai]") from exc
        self._classifier = pipeline("sentiment-analysis", model="ProsusAI/finbert")
        self._rules = RuleBasedNewsAnalyzer()

    def analyze(self, headline: str) -> NewsAnalysis:
        base = self._rules.analyze(headline)
        result = self._classifier(headline, truncation=True)[0]
        label = str(result["label"]).lower()
        sentiment = {"positive": "bullish", "negative": "bearish"}.get(label, "neutral")
        return NewsAnalysis(
            base.headline,
            sentiment,  # type: ignore[arg-type]
            base.thesis if sentiment == base.sentiment else f"FinBERT: {label}",
            base.affected,
            base.event_type,
            float(result["score"]),
        )
