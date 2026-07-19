from __future__ import annotations

import random
import unittest
from decimal import Decimal

from quantops_risk import (
    PositionInput,
    historical_expected_shortfall,
    historical_var,
    parametric_var,
    value_portfolio,
    volatility_contributions,
)


class DeterministicPropertyTests(unittest.TestCase):
    """Algebraic properties exercised over a deterministic generated sample."""

    def test_historical_linear_tail_measures_scale_with_portfolio_value(self) -> None:
        generator = random.Random(20250301)
        for _ in range(100):
            returns = [generator.uniform(-0.08, 0.08) for _ in range(40)]
            scale = generator.uniform(0.1, 20)
            base_var = historical_var(returns, confidence_level=0.95).require_value()
            scaled_var = historical_var(
                returns, confidence_level=0.95, portfolio_value=scale
            ).require_value()
            base_es = historical_expected_shortfall(returns, confidence_level=0.95).require_value()
            scaled_es = historical_expected_shortfall(
                returns, confidence_level=0.95, portfolio_value=scale
            ).require_value()
            self.assertAlmostEqual(scaled_var, base_var * scale, places=10)
            self.assertAlmostEqual(scaled_es, base_es * scale, places=10)
            self.assertGreaterEqual(scaled_es + 1e-12, scaled_var)

    def test_parametric_var_scales_with_positive_exposures(self) -> None:
        covariance = [[0.0004, -0.0001], [-0.0001, 0.0009]]
        for scale in (0.1, 1, 7.5, 100):
            base = parametric_var([100, 50], covariance).require_value()
            scaled = parametric_var([100 * scale, 50 * scale], covariance).require_value()
            self.assertAlmostEqual(scaled, base * scale, places=10)

    def test_portfolio_total_is_order_independent_and_component_sum(self) -> None:
        positions = [
            PositionInput("C", Decimal("3"), Decimal("7"), "USD", "USD"),
            PositionInput("A", Decimal("2"), Decimal("5"), "USD", "USD"),
            PositionInput("B", Decimal("-1"), Decimal("4"), "USD", "USD"),
        ]
        orderings = (
            positions,
            list(reversed(positions)),
            [positions[1], positions[2], positions[0]],
        )
        for ordering in orderings:
            result = value_portfolio(ordering)
            self.assertEqual(
                result.total_market_value,
                sum((item.market_value for item in result.components), Decimal("0")),
            )
            self.assertEqual(result.total_market_value, Decimal("27"))

    def test_contribution_reconciliation_generated_positive_semidefinite_matrices(self) -> None:
        generator = random.Random(99)
        for _ in range(100):
            # Sigma = A A' is positive semidefinite by construction.
            a, b, c, d = (generator.uniform(-0.03, 0.03) for _ in range(4))
            covariance = [
                [a * a + b * b, a * c + b * d],
                [a * c + b * d, c * c + d * d],
            ]
            exposures = [generator.uniform(-100, 100), generator.uniform(-100, 100)]
            result = volatility_contributions(exposures, covariance)
            self.assertTrue(result.reconciled)
            self.assertAlmostEqual(result.component_sum, result.portfolio_volatility, places=9)


if __name__ == "__main__":
    unittest.main()
