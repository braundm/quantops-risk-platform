from __future__ import annotations

import json
import unittest
from decimal import Decimal

from quantops_risk import (
    METHODOLOGY_VERSION,
    CalculationStatus,
    InvalidInputError,
    build_evidence_manifest,
    evidence_item,
    historical_var,
    kupiec_proportion_of_failures,
    methodology_metadata,
    rolling_historical_var_backtest,
    var_exception_backtest,
)


class BacktestingTests(unittest.TestCase):
    def test_exception_count_and_regime_labels(self) -> None:
        result = var_exception_backtest(
            [1, 1, 1],
            [-0.005, -0.02, 0.01],
            confidence_level=0.95,
            portfolio_value=100,
            dates=["d1", "d2", "d3"],
            regime_labels=["normal", "shock", "recovery"],
        )
        self.assertEqual(result.exception_count, 1)
        self.assertAlmostEqual(result.exception_rate or 0, 1 / 3)
        self.assertFalse(result.observations[0].exception)
        self.assertTrue(result.observations[1].exception)
        self.assertEqual(result.observations[1].regime_label, "shock")
        self.assertEqual(result.status, CalculationStatus.UNSTABLE)

    def test_exception_is_strictly_greater_than_forecast(self) -> None:
        result = var_exception_backtest([1], [-0.01], confidence_level=0.95, portfolio_value=100)
        self.assertEqual(result.exception_count, 0)

    def test_risk_estimate_forecast_checks_confidence(self) -> None:
        forecast = historical_var([-0.01, 0, 0.01], confidence_level=0.95)
        with self.assertRaises(InvalidInputError):
            var_exception_backtest([forecast], [0], confidence_level=0.99)

    def test_kupiec_boundaries_are_finite(self) -> None:
        for exceptions in (0, 100):
            with self.subTest(exceptions=exceptions):
                statistic, p_value = kupiec_proportion_of_failures(
                    exceptions, 100, expected_exception_rate=0.05
                )
                self.assertGreaterEqual(statistic, 0)
                self.assertGreaterEqual(p_value, 0)
                self.assertLessEqual(p_value, 1)

    def test_rolling_window_excludes_realized_day(self) -> None:
        result = rolling_historical_var_backtest(
            [0, 0, 0, -0.1], window=3, confidence_level=0.95, portfolio_value=100
        )
        self.assertEqual(result.observation_count, 1)
        self.assertEqual(result.observations[0].forecast_var, 0)
        self.assertEqual(result.observations[0].realized_loss, 10)
        self.assertEqual(result.exception_count, 1)

    def test_short_rolling_history_is_insufficient(self) -> None:
        result = rolling_historical_var_backtest([0, 0], window=2)
        self.assertEqual(result.status, CalculationStatus.INSUFFICIENT_DATA)
        self.assertIsNone(result.kupiec_pof_statistic)


class EvidenceTests(unittest.TestCase):
    def test_evidence_manifest_is_content_addressed_and_order_independent(self) -> None:
        prices = evidence_item(
            key="prices", source_kind="synthetic_fixture", as_of="2025-01-01", payload=[1, 2]
        )
        positions = evidence_item(
            key="positions",
            source_kind="portfolio_snapshot",
            as_of="2025-01-01",
            payload={"value": Decimal("12.30")},
        )
        left = build_evidence_manifest(
            [prices, positions], parameters={"window": 250, "confidence": 0.99}
        )
        right = build_evidence_manifest(
            [positions, prices], parameters={"confidence": 0.99, "window": 250}
        )
        self.assertEqual(left, right)
        self.assertTrue(left.evidence_id.startswith("evd_"))
        self.assertEqual(len(left.evidence_id), 68)
        self.assertEqual(json.loads(left.to_json())["methodology_version"], METHODOLOGY_VERSION)

    def test_nan_payload_is_rejected(self) -> None:
        with self.assertRaises(InvalidInputError):
            evidence_item(key="bad", source_kind="test", as_of="now", payload=float("nan"))


class MethodologyTests(unittest.TestCase):
    def test_semantic_version_and_stable_serialization(self) -> None:
        metadata = methodology_metadata()
        self.assertRegex(metadata.version, r"^\d+\.\d+\.\d+$")
        parsed = json.loads(metadata.to_json())
        self.assertEqual(parsed["version"], METHODOLOGY_VERSION)
        self.assertEqual(parsed["var_loss_convention"], "nonnegative_amount_is_loss")

    def test_estimates_embed_methodology_version(self) -> None:
        self.assertEqual(historical_var([0, 0]).methodology_version, METHODOLOGY_VERSION)


if __name__ == "__main__":
    unittest.main()
