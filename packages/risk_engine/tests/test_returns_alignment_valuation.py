from __future__ import annotations

import math
import unittest
from decimal import Decimal

from quantops_risk import (
    AlignmentPolicy,
    CalculationStatus,
    CurrencyMismatchError,
    InvalidInputError,
    MissingDataError,
    MissingDataPolicy,
    NonPositivePriceError,
    PositionInput,
    align_series,
    arithmetic_returns,
    log_returns,
    value_portfolio,
    value_position,
)


class ReturnTests(unittest.TestCase):
    def test_arithmetic_known_example_and_dates(self) -> None:
        result = arithmetic_returns([100, 110, 99], dates=["d0", "d1", "d2"])
        self.assertEqual(result.observation_count, 2)
        self.assertEqual(result.interval_end_dates, ("d1", "d2"))
        self.assertAlmostEqual(result.values[0], 0.1)
        self.assertAlmostEqual(result.values[1], -0.1)
        self.assertEqual(result.status, CalculationStatus.OK)

    def test_log_returns_compound_additively(self) -> None:
        result = log_returns([100, 110, 121])
        self.assertAlmostEqual(sum(result.values), math.log(1.21))

    def test_drop_pair_does_not_bridge_gap(self) -> None:
        result = arithmetic_returns(
            [100, None, 121, 133.1], missing_policy=MissingDataPolicy.DROP_PAIR
        )
        self.assertEqual(result.skipped_pair_count, 2)
        self.assertEqual(len(result.values), 1)
        self.assertAlmostEqual(result.values[0], 0.1)

    def test_missing_raises_by_default(self) -> None:
        with self.assertRaises(MissingDataError):
            arithmetic_returns([100, None])

    def test_nonpositive_prices_are_explicit(self) -> None:
        for prices in ([100, 0], [100, -1]):
            with self.subTest(prices=prices), self.assertRaises(NonPositivePriceError):
                arithmetic_returns(prices)

    def test_short_input_returns_status_not_nan(self) -> None:
        result = arithmetic_returns([100])
        self.assertIsNone(next(iter(result.values), None))
        self.assertEqual(result.status, CalculationStatus.INSUFFICIENT_DATA)

    def test_dates_length_is_validated(self) -> None:
        with self.assertRaises(InvalidInputError):
            arithmetic_returns([100, 101], dates=["only-one"])


class AlignmentTests(unittest.TestCase):
    def test_intersection_is_sorted_and_drops_incomplete_dates(self) -> None:
        result = align_series(
            {
                "B": {"2025-01-02": 2, "2025-01-03": 3},
                "A": {"2025-01-01": 10, "2025-01-02": 20, "2025-01-03": None},
            }
        )
        self.assertEqual(result.instrument_ids, ("A", "B"))
        self.assertEqual(result.dates, ("2025-01-02",))
        self.assertEqual(result.rows, ((20.0, 2.0),))

    def test_strict_union_rejects_calendar_gap(self) -> None:
        with self.assertRaises(MissingDataError):
            align_series(
                {"A": {"d1": 1}, "B": {"d2": 2}},
                policy=AlignmentPolicy.UNION_STRICT,
            )

    def test_nonfinite_value_is_rejected_even_off_intersection(self) -> None:
        with self.assertRaises(InvalidInputError):
            align_series({"A": {"d1": float("nan")}, "B": {"d2": 2}})


class ValuationTests(unittest.TestCase):
    def test_decimal_position_value_and_unrealized_pnl(self) -> None:
        result = value_position(
            PositionInput(
                "QTECH",
                Decimal("2.5"),
                Decimal("100.10"),
                "usd",
                "USD",
                cost_basis_per_unit=Decimal("80.10"),
            )
        )
        self.assertEqual(result.local_market_value, Decimal("250.250"))
        self.assertEqual(result.market_value, Decimal("250.250"))
        self.assertEqual(result.unrealized_pnl, Decimal("50.000"))

    def test_cross_currency_conversion_is_explicit(self) -> None:
        result = value_position(
            PositionInput(
                "QEUR",
                Decimal("10"),
                Decimal("20"),
                "EUR",
                "USD",
                Decimal("1.25"),
            )
        )
        self.assertEqual(result.market_value, Decimal("250.00"))

    def test_cross_currency_without_fx_is_rejected(self) -> None:
        with self.assertRaises(CurrencyMismatchError):
            value_position(PositionInput("QEUR", Decimal("1"), Decimal("1"), "EUR", "USD"))

    def test_same_currency_nonunit_fx_is_rejected(self) -> None:
        with self.assertRaises(CurrencyMismatchError):
            value_position(
                PositionInput("QUSD", Decimal("1"), Decimal("1"), "USD", "USD", Decimal("1.01"))
            )

    def test_float_money_is_rejected(self) -> None:
        with self.assertRaises(InvalidInputError):
            value_position(
                PositionInput("Q", 1.0, Decimal("1"), "USD", "USD")  # type: ignore[arg-type]
            )

    def test_portfolio_reconciles_and_orders_components(self) -> None:
        result = value_portfolio(
            [
                PositionInput("B", Decimal("2"), Decimal("3"), "USD", "USD"),
                PositionInput("A", Decimal("4"), Decimal("5"), "USD", "USD"),
            ]
        )
        self.assertEqual(tuple(item.instrument_id for item in result.components), ("A", "B"))
        self.assertEqual(result.total_market_value, Decimal("26"))
        self.assertTrue(result.reconciled)

    def test_mixed_base_currencies_are_rejected(self) -> None:
        with self.assertRaises(CurrencyMismatchError):
            value_portfolio(
                [
                    PositionInput("A", Decimal("1"), Decimal("1"), "USD", "USD"),
                    PositionInput("B", Decimal("1"), Decimal("1"), "EUR", "EUR"),
                ]
            )


if __name__ == "__main__":
    unittest.main()
