import unittest

from macropulse.analyzer import RuleBasedNewsAnalyzer
from macropulse.engine import MacroPulseEngine
from macropulse.formatters import format_text
from macropulse.market import DemoMarketDataProvider


class EngineTests(unittest.TestCase):
    def test_fed_cut_matches_reference_flow(self):
        report = MacroPulseEngine().run("Fed unexpectedly cuts rates", DemoMarketDataProvider())
        self.assertEqual(report.analysis.sentiment, "bullish")
        self.assertEqual(report.analysis.affected, ("QQQ", "NVDA", "MSFT", "AMZN"))
        self.assertEqual([check.direction for check in report.checks], ["up", "down", "down"])
        self.assertEqual(report.confidence, "HIGH")

    def test_explicit_ticker_is_preserved(self):
        result = RuleBasedNewsAnalyzer().analyze("$TSLA earnings beat estimates")
        self.assertEqual(result.affected, ("TSLA",))

    def test_title_case_word_is_not_a_ticker(self):
        result = RuleBasedNewsAnalyzer().analyze("Fed unexpectedly cuts rates")
        self.assertEqual(result.affected, ("QQQ", "NVDA", "MSFT", "AMZN"))

    def test_neutral_news_does_not_invent_market_expectations(self):
        report = MacroPulseEngine().run("Board schedules its annual meeting", DemoMarketDataProvider())
        self.assertEqual(report.analysis.sentiment, "neutral")
        self.assertTrue(all(check.expected is None for check in report.checks))
        self.assertEqual(report.confidence, "LOW")

    def test_text_output_contains_all_sections(self):
        report = MacroPulseEngine().run("Fed unexpectedly cuts rates", DemoMarketDataProvider())
        text = format_text(report)
        for section in ("News:", "AI:", "Affected:", "Check:", "Result:"):
            self.assertIn(section, text)


if __name__ == "__main__":
    unittest.main()
