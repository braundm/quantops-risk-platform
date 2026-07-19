from __future__ import annotations

import unittest

from quantops_risk import (
    CalculationStatus,
    InvalidInputError,
    correlation_matrix,
    herfindahl_hirschman,
    maximum_drawdown,
)


class DrawdownTests(unittest.TestCase):
    def test_recovered_drawdown_dates(self) -> None:
        result = maximum_drawdown(
            [100, 120, 90, 95, 120, 125], ["d1", "d2", "d3", "d4", "d5", "d6"]
        )
        self.assertAlmostEqual(result.maximum_drawdown or 0, 0.25)
        self.assertEqual(result.peak_date, "d2")
        self.assertEqual(result.trough_date, "d3")
        self.assertEqual(result.recovery_date, "d5")
        self.assertAlmostEqual(result.drawdowns[2], -0.25)

    def test_unrecovered_drawdown(self) -> None:
        result = maximum_drawdown([100, 80, 90], ["d1", "d2", "d3"])
        self.assertAlmostEqual(result.maximum_drawdown or 0, 0.2)
        self.assertIsNone(result.recovery_date)

    def test_no_drawdown_has_first_date_as_episode(self) -> None:
        result = maximum_drawdown([100, 101, 102], ["d1", "d2", "d3"])
        self.assertEqual(result.maximum_drawdown, 0.0)
        self.assertEqual(result.peak_date, "d1")
        self.assertEqual(result.trough_date, "d1")
        self.assertEqual(result.recovery_date, "d1")

    def test_dates_must_be_strictly_increasing(self) -> None:
        with self.assertRaises(InvalidInputError):
            maximum_drawdown([100, 90], ["d2", "d1"])


class CorrelationTests(unittest.TestCase):
    def test_known_positive_and_negative_correlation(self) -> None:
        result = correlation_matrix({"B": [3, 2, 1], "A": [1, 2, 3]}, unstable_below=3)
        self.assertEqual(result.instrument_ids, ("A", "B"))
        self.assertAlmostEqual(result.matrix[0][1] or 0, -1.0)
        self.assertEqual(result.observation_counts[0][1], 3)
        self.assertEqual(result.status, CalculationStatus.OK)

    def test_pairwise_missing_overlap_is_counted(self) -> None:
        result = correlation_matrix({"A": [1, 2, None, 4], "B": [1, None, 3, 4]}, unstable_below=3)
        self.assertEqual(result.observation_counts[0][1], 2)
        self.assertEqual(result.status, CalculationStatus.UNSTABLE)

    def test_constant_series_is_none_not_nan(self) -> None:
        result = correlation_matrix({"A": [1, 1, 1], "B": [1, 2, 3]})
        self.assertIsNone(result.matrix[0][1])
        self.assertEqual(result.status, CalculationStatus.INSUFFICIENT_DATA)

    def test_nonfinite_value_is_rejected_even_when_pair_is_missing(self) -> None:
        with self.assertRaises(InvalidInputError):
            correlation_matrix({"A": [1, float("nan")], "B": [1, None]})


class ConcentrationTests(unittest.TestCase):
    def test_equal_weights_have_inverse_n_hhi(self) -> None:
        result = herfindahl_hirschman({"C": 10, "A": 10, "B": 10})
        self.assertAlmostEqual(result.hhi or 0, 1 / 3)
        self.assertAlmostEqual(result.effective_number or 0, 3)
        self.assertEqual(result.instrument_ids, ("A", "B", "C"))

    def test_long_short_uses_absolute_gross_exposure(self) -> None:
        result = herfindahl_hirschman({"LONG": 100, "SHORT": -100})
        self.assertEqual(result.absolute_weights, (0.5, 0.5))
        self.assertEqual(result.hhi, 0.5)

    def test_zero_gross_is_insufficient(self) -> None:
        result = herfindahl_hirschman({"A": 0})
        self.assertIsNone(result.hhi)
        self.assertEqual(result.status, CalculationStatus.INSUFFICIENT_DATA)


if __name__ == "__main__":
    unittest.main()
