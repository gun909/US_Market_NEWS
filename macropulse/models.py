from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

Direction = Literal["up", "down", "flat", "unknown"]
Sentiment = Literal["bullish", "bearish", "neutral"]


@dataclass(frozen=True)
class NewsAnalysis:
    headline: str
    sentiment: Sentiment
    thesis: str
    affected: tuple[str, ...]
    event_type: str
    score: float
    positive: tuple[str, ...] = ()
    negative: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketSignal:
    label: str
    symbol: str
    metric: str
    direction: Direction
    change_pct: float | None = None
    expected: Direction | None = None

    @property
    def confirms(self) -> bool | None:
        if self.expected is None or self.direction == "unknown":
            return None
        return self.direction == self.expected


@dataclass(frozen=True)
class AlertReport:
    analysis: NewsAnalysis
    checks: tuple[MarketSignal, ...]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    confidence_score: float

    def to_dict(self) -> dict:
        return asdict(self)
