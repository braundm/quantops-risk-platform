from __future__ import annotations

import unittest

from quantops_risk import InvalidInputError, volatility_contributions


class ContributionTests(unittest.TestCase):
    def test_contributions_reconcile_exactly_for_diagonal_covariance(self) -> None:
        result = volatility_contributions(
            [100, 50],
            [[0.0004, 0.0], [0.0, 0.0009]],
            instrument_ids=["A", "B"],
        )
        self.assertTrue(result.reconciled)
        self.assertAlmostEqual(result.component_sum, result.portfolio_volatility)
        self.assertAlmostEqual(
            sum(item.percentage_contribution for item in result.contributions), 1.0
        )

    def test_negative_diversifying_contribution_is_not_clipped(self) -> None:
        result = volatility_contributions(
            [1, 1], [[1, -1.5], [-1.5, 4]], instrument_ids=["HEDGE", "RISK"]
        )
        self.assertLess(result.contributions[0].component_contribution, 0)
        self.assertTrue(result.reconciled)

    def test_zero_variance_contributions_are_defined_as_zero(self) -> None:
        result = volatility_contributions([1, 2], [[0, 0], [0, 0]])
        self.assertEqual(result.portfolio_volatility, 0)
        self.assertEqual(result.component_sum, 0)
        self.assertTrue(all(item.component_contribution == 0 for item in result.contributions))

    def test_shape_mismatch_is_rejected(self) -> None:
        with self.assertRaises(InvalidInputError):
            volatility_contributions([1, 2], [[1]])


if __name__ == "__main__":
    unittest.main()
