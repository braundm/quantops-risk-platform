from __future__ import annotations

import math
import unittest
from statistics import NormalDist
from typing import ClassVar

from quantops_risk import (
    CalculationStatus,
    InsufficientDataError,
    InvalidInputError,
    empirical_quantile,
    historical_expected_shortfall,
    historical_var,
    parametric_expected_shortfall,
    parametric_var,
    parametric_var_from_returns,
    portfolio_variance,
    rolling_sample_volatility,
    sample_covariance_matrix,
    sample_volatility,
)


class VolatilityTests(unittest.TestCase):
    def test_known_sample_and_annualized_volatility(self) -> None:
        result = sample_volatility([-0.01, 0.01], periods_per_year=4)
        self.assertAlmostEqual(result.sample_volatility or 0, math.sqrt(0.0002))
        self.assertAlmostEqual(result.annualized_volatility or 0, 2 * math.sqrt(0.0002))
        self.assertEqual(result.observation_count, 2)

    def test_zero_returns_have_zero_volatility(self) -> None:
        result = sample_volatility([0, 0, 0])
        self.assertEqual(result.sample_volatility, 0.0)
        self.assertEqual(result.annualized_volatility, 0.0)

    def test_insufficient_data_is_typed(self) -> None:
        result = sample_volatility([0.1])
        self.assertEqual(result.status, CalculationStatus.INSUFFICIENT_DATA)
        with self.assertRaises(InsufficientDataError) as caught:
            result.require_value()
        self.assertEqual(caught.exception.actual, 1)
        self.assertEqual(caught.exception.required, 2)

    def test_rolling_uses_complete_windows(self) -> None:
        result = rolling_sample_volatility([0, 1, 2, 3], window=3, periods_per_year=1)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].sample_volatility, 1.0)
        self.assertEqual(result[1].sample_volatility, 1.0)

    def test_nonfinite_return_is_rejected(self) -> None:
        with self.assertRaises(InvalidInputError):
            sample_volatility([0, float("nan")])


class CovarianceTests(unittest.TestCase):
    def test_one_asset_known_variance(self) -> None:
        result = sample_covariance_matrix([[1], [2], [3]])
        self.assertEqual(result.matrix, ((1.0,),))
        self.assertEqual(result.means, (2.0,))

    def test_two_asset_singular_covariance_is_retained(self) -> None:
        result = sample_covariance_matrix([[1, 2], [2, 4], [3, 6]])
        self.assertEqual(result.matrix, ((1.0, 2.0), (2.0, 4.0)))
        self.assertIn("singular", result.singular_policy)

    def test_portfolio_variance_known_example(self) -> None:
        value = portfolio_variance([100, 50], [[0.0004, 0.0001], [0.0001, 0.0009]])
        self.assertAlmostEqual(value, 7.25)

    def test_material_negative_variance_is_rejected(self) -> None:
        with self.assertRaises(InvalidInputError):
            portfolio_variance([1, 1], [[1, -2], [-2, 1]])

    def test_indefinite_covariance_is_rejected_for_any_exposure(self) -> None:
        with self.assertRaises(InvalidInputError):
            portfolio_variance([1, 0], [[1, 2], [2, 1]])


class HistoricalTailTests(unittest.TestCase):
    RETURNS: ClassVar[tuple[float, ...]] = (-0.10, -0.05, 0.0, 0.05, 0.10)

    def test_quantile_interpolation_rules(self) -> None:
        values = [0, 10, 20, 30]
        self.assertEqual(empirical_quantile(values, 0.75, interpolation="linear"), 22.5)
        self.assertEqual(empirical_quantile(values, 0.75, interpolation="lower"), 20)
        self.assertEqual(empirical_quantile(values, 0.75, interpolation="higher"), 30)
        self.assertEqual(empirical_quantile(values, 0.75, interpolation="midpoint"), 25)

    def test_historical_var_known_example(self) -> None:
        result = historical_var(self.RETURNS, confidence_level=0.8, portfolio_value=100)
        self.assertAlmostEqual(result.require_value(), 6.0)
        self.assertEqual(result.observation_count, 5)
        self.assertIn("nonnegative_amount_is_loss", result.assumptions)

    def test_expected_shortfall_known_example_and_small_tail_warning(self) -> None:
        result = historical_expected_shortfall(
            self.RETURNS, confidence_level=0.8, portfolio_value=100
        )
        self.assertAlmostEqual(result.var_threshold or 0, 6.0)
        self.assertEqual(result.value, 10.0)
        self.assertEqual(result.tail_observation_count, 1)
        self.assertEqual(result.status, CalculationStatus.UNSTABLE)

    def test_zero_series_has_zero_var_and_es(self) -> None:
        var = historical_var([0, 0, 0])
        es = historical_expected_shortfall([0, 0, 0])
        self.assertEqual(var.value, 0.0)
        self.assertEqual(es.value, 0.0)
        self.assertGreaterEqual(es.value or 0, var.value or 0)

    def test_all_gains_are_floored_not_negative(self) -> None:
        self.assertEqual(historical_var([0.01, 0.02, 0.03]).value, 0.0)
        self.assertEqual(historical_expected_shortfall([0.01, 0.02, 0.03]).value, 0.0)

    def test_insufficient_tail_inputs_return_status(self) -> None:
        result = historical_var([0.1])
        self.assertIsNone(result.value)
        self.assertEqual(result.status, CalculationStatus.INSUFFICIENT_DATA)


class ParametricTailTests(unittest.TestCase):
    def test_one_asset_analytical_var(self) -> None:
        result = parametric_var([100], [[0.0004]], confidence_level=0.975)
        expected = NormalDist().inv_cdf(0.975) * 2.0
        self.assertAlmostEqual(result.require_value(), expected)

    def test_two_asset_analytical_var(self) -> None:
        result = parametric_var(
            [100, 50], [[0.0004, 0.0001], [0.0001, 0.0009]], confidence_level=0.95
        )
        self.assertAlmostEqual(result.require_value(), NormalDist().inv_cdf(0.95) * math.sqrt(7.25))

    def test_singular_covariance_needs_no_inverse(self) -> None:
        result = parametric_var([1, 1], [[1, 1], [1, 1]], confidence_level=0.95)
        self.assertAlmostEqual(result.require_value(), NormalDist().inv_cdf(0.95) * 2)

    def test_parametric_es_is_at_least_var(self) -> None:
        var = parametric_var([100], [[0.0004]], confidence_level=0.99)
        es = parametric_expected_shortfall([100], [[0.0004]], confidence_level=0.99)
        self.assertGreaterEqual(es.require_value(), var.require_value())
        self.assertEqual(es.var_threshold, var.value)

    def test_from_returns_exposes_observation_count(self) -> None:
        result = parametric_var_from_returns([[0.01], [-0.01], [0.0]], [100])
        self.assertEqual(result.observation_count, 3)


if __name__ == "__main__":
    unittest.main()
