from __future__ import annotations

from .analyzer import RuleBasedNewsAnalyzer
from .market import MarketDataProvider, build_market_checks
from .models import AlertReport, NewsAnalysis


class MacroPulseEngine:
    def __init__(self, analyzer=None) -> None:
        self.analyzer = analyzer or RuleBasedNewsAnalyzer()

    def run(self, headline: str, market: MarketDataProvider) -> AlertReport:
        analysis: NewsAnalysis = self.analyzer.analyze(headline)
        checks = build_market_checks(analysis, market)
        known = [check.confirms for check in checks if check.confirms is not None]
        confirmation = sum(known) / len(known) if known else 0.0
        if analysis.sentiment == "neutral":
            return AlertReport(analysis, checks, "LOW", round(0.55 * analysis.score, 3))
        score = round(0.55 * analysis.score + 0.45 * confirmation, 3)
        confidence = "HIGH" if score >= 0.78 else "MEDIUM" if score >= 0.58 else "LOW"
        return AlertReport(analysis, checks, confidence, score)
