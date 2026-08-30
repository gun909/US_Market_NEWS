from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import Direction, MarketSignal, NewsAnalysis


@dataclass(frozen=True)
class QuoteChange:
    price_pct: float | None = None
    volume_pct: float | None = None


class MarketDataProvider(Protocol):
    def changes(self, symbols: tuple[str, ...]) -> dict[str, QuoteChange]: ...


class DemoMarketDataProvider:
    """Stable data for demos/tests; it represents confirmation after a dovish Fed surprise."""

    def changes(self, symbols: tuple[str, ...]) -> dict[str, QuoteChange]:
        sample = {
            "QQQ": QuoteChange(price_pct=1.40, volume_pct=38.0),
            "^VIX": QuoteChange(price_pct=-8.20),
            "^TNX": QuoteChange(price_pct=-2.10),
        }
        return {symbol: sample.get(symbol, QuoteChange()) for symbol in symbols}


class YFinanceMarketDataProvider:
    def changes(self, symbols: tuple[str, ...]) -> dict[str, QuoteChange]:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("Install market support with: pip install -e .[market]") from exc

        results: dict[str, QuoteChange] = {}
        for symbol in symbols:
            history = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=True)
            if len(history) < 2:
                results[symbol] = QuoteChange()
                continue
            previous, latest = history.iloc[-2], history.iloc[-1]
            price_pct = _pct_change(float(previous["Close"]), float(latest["Close"]))
            volume_pct = _pct_change(float(previous["Volume"]), float(latest["Volume"]))
            results[symbol] = QuoteChange(price_pct, volume_pct)
        return results


def _pct_change(previous: float, latest: float) -> float | None:
    if previous == 0:
        return None
    return (latest / previous - 1) * 100


def _direction(value: float | None, threshold: float = 0.10) -> Direction:
    if value is None:
        return "unknown"
    if value > threshold:
        return "up"
    if value < -threshold:
        return "down"
    return "flat"


def build_market_checks(analysis: NewsAnalysis, provider: MarketDataProvider) -> tuple[MarketSignal, ...]:
    data = provider.changes(("QQQ", "^VIX", "^TNX"))
    if analysis.sentiment == "bullish":
        expected: tuple[Direction | None, Direction | None, Direction | None] = ("up", "down", "down")
    elif analysis.sentiment == "bearish":
        # High participation confirms either direction; VIX and yields encode direction.
        expected = ("up", "up", "up")
    else:
        expected = (None, None, None)
    qqq, vix, tnx = data["QQQ"], data["^VIX"], data["^TNX"]
    return (
        MarketSignal("QQQ volume", "QQQ", "volume", _direction(qqq.volume_pct, 5.0), qqq.volume_pct, expected[0]),
        MarketSignal("VIX", "^VIX", "price", _direction(vix.price_pct), vix.price_pct, expected[1]),
        MarketSignal("10Y yield", "^TNX", "price", _direction(tnx.price_pct), tnx.price_pct, expected[2]),
    )
