from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from quantops_risk import (
    CalculationStatus,
    CorrelationOverride,
    CurrencyMismatchError,
    DuplicateInstrumentError,
    EvidenceItem,
    FXShock,
    InstrumentPriceShock,
    InsufficientDataError,
    InvalidInputError,
    MissingDataPolicy,
    PositionInput,
    ScenarioDefinition,
    ScenarioPosition,
    VolatilityMultiplier,
    align_series,
    build_evidence_manifest,
    calculate_returns,
    correlation_matrix,
    empirical_quantile,
    evidence_item,
    historical_expected_shortfall,
    historical_var,
    kupiec_proportion_of_failures,
    maximum_drawdown,
    parametric_expected_shortfall,
    parametric_var,
    parametric_var_from_returns,
    rolling_historical_var_backtest,
    rolling_sample_volatility,
    run_scenario,
    sample_covariance_matrix,
    sample_volatility,
    system_scenario,
    value_portfolio,
    value_position,
    var_exception_backtest,
    volatility_contributions,
)


class ValidationEdgeTests(unittest.TestCase):
    def test_numeric_boundaries_raise_typed_errors(self) -> None:
        with self.assertRaises(InvalidInputError):
            sample_volatility([True, 0])
        with self.assertRaises(InvalidInputError):
            sample_volatility(["not-a-number", 0])
        with self.assertRaises(InvalidInputError):
            historical_var([0, 0], confidence_level=0.5)
        with self.assertRaises(InvalidInputError):
            historical_var([0, 0], portfolio_value=-1)

    def test_return_enum_and_all_missing_paths(self) -> None:
        with self.assertRaises(InvalidInputError):
            calculate_returns([1, 2], method="unsupported")
        with self.assertRaises(InvalidInputError):
            calculate_returns([1, 2], missing_policy="unsupported")
        result = calculate_returns([None, None], missing_policy=MissingDataPolicy.DROP_PAIR)
        self.assertEqual(result.status, CalculationStatus.INSUFFICIENT_DATA)
        self.assertEqual(result.skipped_pair_count, 1)

    def test_alignment_empty_invalid_and_duplicate_calendar_paths(self) -> None:
        self.assertEqual(align_series({}).status, CalculationStatus.INSUFFICIENT_DATA)
        with self.assertRaises(InvalidInputError):
            align_series({}, policy="unsupported")
        with self.assertRaises(InvalidInputError):
            align_series({"": {"d1": 1}})
        with self.assertRaises(InvalidInputError):
            align_series({"A": {date(2025, 1, 1): 1, "2025-01-01": 2}})

    def test_matrix_shape_symmetry_and_covariance_history_validation(self) -> None:
        with self.assertRaises(InvalidInputError):
            parametric_var([1, 1], [[1, 0]])
        with self.assertRaises(InvalidInputError):
            parametric_var([1, 1], [[1, 0], [0]])
        with self.assertRaises(InvalidInputError):
            parametric_var([1, 1], [[1, 0.2], [0.1, 1]])
        self.assertEqual(sample_covariance_matrix([]).status, CalculationStatus.INSUFFICIENT_DATA)
        self.assertEqual(
            sample_covariance_matrix([[1, 2]]).status,
            CalculationStatus.INSUFFICIENT_DATA,
        )
        with self.assertRaises(InvalidInputError):
            sample_covariance_matrix([[], []])
        with self.assertRaises(InvalidInputError):
            sample_covariance_matrix([[1], [1, 2]])

    def test_volatility_parameter_validation(self) -> None:
        with self.assertRaises(InvalidInputError):
            sample_volatility([0, 0], periods_per_year=True)
        with self.assertRaises(InvalidInputError):
            sample_volatility([0, 0], periods_per_year=0)
        with self.assertRaises(InvalidInputError):
            rolling_sample_volatility([0, 0], window=1)

    def test_quantile_boundaries_and_nearest_interpolation(self) -> None:
        with self.assertRaises(InvalidInputError):
            empirical_quantile([], 0.9)
        with self.assertRaises(InvalidInputError):
            empirical_quantile([1], 1.1)
        with self.assertRaises(InvalidInputError):
            empirical_quantile([1, 2], 0.9, interpolation="bad")  # type: ignore[arg-type]
        self.assertEqual(empirical_quantile([0, 10, 20], 0.9, interpolation="nearest"), 20)


class TailRiskEdgeTests(unittest.TestCase):
    def test_parametric_var_insufficient_and_parameter_paths(self) -> None:
        insufficient = parametric_var([], [], confidence_level=0.95)
        self.assertEqual(insufficient.status, CalculationStatus.INSUFFICIENT_DATA)
        with self.assertRaises(InsufficientDataError):
            insufficient.require_value()
        with self.assertRaises(InvalidInputError):
            parametric_var([1], [[1]], observation_count=True)
        with self.assertRaises(InvalidInputError):
            parametric_var([1], [[1]], observation_count=-1)
        with self.assertRaises(InvalidInputError):
            parametric_var([1, 1], [[1, 0], [0, 1]], mean_returns=[0])
        result = parametric_var(
            [1], [[1]], mean_returns=[0.1], horizon_periods=2, observation_count=10
        )
        self.assertEqual(result.observation_count, 10)
        self.assertGreaterEqual(result.require_value(), 0)

    def test_parametric_from_returns_insufficient_and_mean_paths(self) -> None:
        insufficient = parametric_var_from_returns([[0.1]], [1])
        self.assertEqual(insufficient.status, CalculationStatus.INSUFFICIENT_DATA)
        with_mean = parametric_var_from_returns(
            [[0.1], [0.2], [0.3]], [1], include_sample_mean=True
        )
        self.assertEqual(with_mean.observation_count, 3)

    def test_expected_shortfall_insufficient_and_parameter_paths(self) -> None:
        historical = historical_expected_shortfall([0.1])
        self.assertEqual(historical.status, CalculationStatus.INSUFFICIENT_DATA)
        with self.assertRaises(InsufficientDataError):
            historical.require_value()
        parametric = parametric_expected_shortfall([], [])
        self.assertEqual(parametric.status, CalculationStatus.INSUFFICIENT_DATA)
        with self.assertRaises(InvalidInputError):
            parametric_expected_shortfall([1], [[1]], observation_count=True)
        with self.assertRaises(InvalidInputError):
            parametric_expected_shortfall([1], [[1]], observation_count=-1)
        with self.assertRaises(InvalidInputError):
            parametric_expected_shortfall([1, 1], [[1, 0], [0, 1]], mean_returns=[0])
        result = parametric_expected_shortfall(
            [1], [[1]], mean_returns=[0.1], horizon_periods=2, observation_count=10
        )
        self.assertEqual(result.observation_count, 10)


class ValuationEdgeTests(unittest.TestCase):
    def test_currency_and_position_domain_errors(self) -> None:
        with self.assertRaises(InvalidInputError):
            value_position(PositionInput("", Decimal("1"), Decimal("1"), "USD", "USD"))
        with self.assertRaises(InvalidInputError):
            value_position(PositionInput("Q", Decimal("1"), Decimal("-1"), "USD", "USD"))
        with self.assertRaises(InvalidInputError):
            value_position(PositionInput("Q", Decimal("1"), Decimal("1"), "US", "USD"))
        with self.assertRaises(InvalidInputError):
            value_position(
                PositionInput(
                    "Q",
                    Decimal("1"),
                    Decimal("1"),
                    123,  # type: ignore[arg-type]
                    "USD",
                )
            )
        with self.assertRaises(InvalidInputError):
            value_position(
                PositionInput(
                    "Q",
                    Decimal("1"),
                    Decimal("NaN"),
                    "USD",
                    "USD",
                )
            )

    def test_fx_cost_basis_and_portfolio_errors(self) -> None:
        with self.assertRaises(InvalidInputError):
            value_position(
                PositionInput(
                    "Q",
                    Decimal("1"),
                    Decimal("1"),
                    "EUR",
                    "USD",
                    Decimal("NaN"),
                )
            )
        with self.assertRaises(CurrencyMismatchError):
            value_position(
                PositionInput(
                    "Q",
                    Decimal("1"),
                    Decimal("1"),
                    "EUR",
                    "USD",
                    Decimal("0"),
                )
            )
        with self.assertRaises(InvalidInputError):
            value_position(
                PositionInput(
                    "Q",
                    Decimal("1"),
                    Decimal("1"),
                    "USD",
                    "USD",
                    cost_basis_per_unit=Decimal("-1"),
                )
            )
        with self.assertRaises(InsufficientDataError):
            value_portfolio([])
        with self.assertRaises(InvalidInputError):
            value_portfolio(
                [PositionInput("Q", Decimal("1"), Decimal("1"), "USD", "USD")],
                reconciliation_tolerance=Decimal("-1"),
            )
        duplicate = PositionInput("Q", Decimal("1"), Decimal("1"), "USD", "USD")
        with self.assertRaises(DuplicateInstrumentError):
            value_portfolio([duplicate, duplicate])

    def test_portfolio_total_pnl_is_available_when_all_costs_exist(self) -> None:
        result = value_portfolio(
            [
                PositionInput(
                    "A",
                    Decimal("2"),
                    Decimal("10"),
                    "USD",
                    "USD",
                    cost_basis_per_unit=Decimal("8"),
                ),
                PositionInput(
                    "B",
                    Decimal("1"),
                    Decimal("20"),
                    "USD",
                    "USD",
                    cost_basis_per_unit=Decimal("15"),
                ),
            ]
        )
        self.assertEqual(result.total_unrealized_pnl, Decimal("9"))


class PortfolioAnalyticsEdgeTests(unittest.TestCase):
    def test_drawdown_invalid_and_short_histories(self) -> None:
        with self.assertRaises(InvalidInputError):
            maximum_drawdown([100], [])
        with self.assertRaises(InvalidInputError):
            maximum_drawdown([0, 1], ["d1", "d2"])
        self.assertEqual(maximum_drawdown([], []).status, CalculationStatus.INSUFFICIENT_DATA)
        self.assertEqual(
            maximum_drawdown([100], ["d1"]).drawdowns,
            (0.0,),
        )

    def test_correlation_configuration_and_shape_errors(self) -> None:
        self.assertEqual(correlation_matrix({}).status, CalculationStatus.INSUFFICIENT_DATA)
        with self.assertRaises(InvalidInputError):
            correlation_matrix({"A": [1], "B": [1, 2]})
        with self.assertRaises(InvalidInputError):
            correlation_matrix({"A": [1, 2]}, minimum_observations=1)
        with self.assertRaises(InvalidInputError):
            correlation_matrix({"A": [1, 2]}, minimum_observations=3, unstable_below=2)
        result = correlation_matrix({"A": [1, None], "B": [1, None]}, unstable_below=2)
        self.assertEqual(result.status, CalculationStatus.INSUFFICIENT_DATA)

    def test_contribution_identifier_errors(self) -> None:
        with self.assertRaises(InvalidInputError):
            volatility_contributions([], [])
        with self.assertRaises(InvalidInputError):
            volatility_contributions([1], [[1]], instrument_ids=[])
        with self.assertRaises(InvalidInputError):
            volatility_contributions([1, 1], [[1, 0], [0, 1]], instrument_ids=["A", "A"])


class BacktestingAndEvidenceEdgeTests(unittest.TestCase):
    def test_kupiec_argument_validation(self) -> None:
        with self.assertRaises(InvalidInputError):
            kupiec_proportion_of_failures(0, 0, expected_exception_rate=0.05)
        with self.assertRaises(InvalidInputError):
            kupiec_proportion_of_failures(2, 1, expected_exception_rate=0.05)
        with self.assertRaises(InvalidInputError):
            kupiec_proportion_of_failures(0, 1, expected_exception_rate=0)

    def test_backtest_shape_forecast_and_threshold_validation(self) -> None:
        with self.assertRaises(InvalidInputError):
            var_exception_backtest([1], [], confidence_level=0.95)
        with self.assertRaises(InvalidInputError):
            var_exception_backtest([1], [0], confidence_level=0.95, dates=[])
        with self.assertRaises(InvalidInputError):
            var_exception_backtest([1], [0], confidence_level=0.95, regime_labels=[])
        with self.assertRaises(InvalidInputError):
            var_exception_backtest([1], [0], confidence_level=0.95, small_sample_threshold=0)
        with self.assertRaises(InvalidInputError):
            var_exception_backtest([-1], [0], confidence_level=0.95)
        result = var_exception_backtest([1], [0], confidence_level=0.95, small_sample_threshold=1)
        self.assertEqual(result.status, CalculationStatus.OK)

    def test_rolling_backtest_shape_validation(self) -> None:
        with self.assertRaises(InvalidInputError):
            rolling_historical_var_backtest([0, 0], window=1)
        with self.assertRaises(InvalidInputError):
            rolling_historical_var_backtest([0, 0, 0], window=2, dates=[])
        with self.assertRaises(InvalidInputError):
            rolling_historical_var_backtest([0, 0, 0], window=2, regime_labels=[])

    def test_evidence_metadata_serialization_and_identity_validation(self) -> None:
        with self.assertRaises(InvalidInputError):
            evidence_item(key="", source_kind="fixture", as_of="now", payload={})
        with self.assertRaises(InvalidInputError):
            evidence_item(key="bad", source_kind="fixture", as_of="now", payload=object())
        item = EvidenceItem("same", "fixture", "now", "a" * 64)
        with self.assertRaises(InvalidInputError):
            build_evidence_manifest([item, item], parameters={})


class ScenarioEdgeTests(unittest.TestCase):
    @staticmethod
    def demo_positions() -> tuple[ScenarioPosition, ...]:
        return (
            ScenarioPosition(
                "QTECH",
                "equity_index",
                Decimal("10"),
                Decimal("100"),
                "USD",
                "USD",
            ),
            ScenarioPosition(
                "QGOLD",
                "commodity",
                Decimal("5"),
                Decimal("200"),
                "USD",
                "USD",
            ),
            ScenarioPosition(
                "QWTI",
                "commodity",
                Decimal("4"),
                Decimal("50"),
                "USD",
                "USD",
            ),
        )

    def test_all_system_scenarios_run_against_required_demo_taxonomy(self) -> None:
        for key in (
            "equity_selloff_15pct",
            "oil_spike_25pct",
            "gold_down_10pct",
            "cross_asset_correlation_breakdown",
            "combined_liquidity_stress",
        ):
            with self.subTest(key=key):
                result = run_scenario(system_scenario(key), self.demo_positions())
                self.assertTrue(result.hypothetical)
                self.assertEqual(
                    result.stressed_value - result.base_value,
                    result.pnl,
                )

    def test_scenario_definition_and_shock_validation(self) -> None:
        with self.assertRaises(InvalidInputError):
            InstrumentPriceShock("", Decimal("0.1"))
        with self.assertRaises(InvalidInputError):
            InstrumentPriceShock("Q", Decimal("-1.1"))
        with self.assertRaises(InvalidInputError):
            FXShock("USD", Decimal("-1"))
        with self.assertRaises(InvalidInputError):
            VolatilityMultiplier(Decimal("0"))
        with self.assertRaises(InvalidInputError):
            CorrelationOverride("A", "A", Decimal("0"))
        with self.assertRaises(InvalidInputError):
            CorrelationOverride("A", "B", Decimal("2"))
        with self.assertRaises(InvalidInputError):
            ScenarioDefinition("x", "X", "bad", (VolatilityMultiplier(Decimal("1")),), ("a",))
        with self.assertRaises(InvalidInputError):
            ScenarioDefinition("x", "X", "1.0.0", (), ("a",))
        with self.assertRaises(InvalidInputError):
            ScenarioDefinition(
                "x",
                "X",
                "1.0.0",
                (VolatilityMultiplier(Decimal("1")),),
                (),
            )
        with self.assertRaises(InvalidInputError):
            ScenarioDefinition(
                "x",
                "X",
                "1.0.0",
                (VolatilityMultiplier(Decimal("1")),),
                ("a",),
                False,
            )

    def test_scenario_run_input_errors(self) -> None:
        definition = ScenarioDefinition(
            "x",
            "X",
            "1.0.0",
            (VolatilityMultiplier(Decimal("1")),),
            ("analytical",),
        )
        with self.assertRaises(InvalidInputError):
            run_scenario(definition, ())
        with self.assertRaises(InvalidInputError):
            system_scenario("missing")


if __name__ == "__main__":
    unittest.main()
