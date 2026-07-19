from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal

from quantops_risk import (
    AssetClassShock,
    CorrelationOverride,
    FXShock,
    InstrumentPriceShock,
    InvalidInputError,
    ScenarioDefinition,
    ScenarioPosition,
    VolatilityMultiplier,
    run_scenario,
    system_scenario,
)


def positions() -> tuple[ScenarioPosition, ...]:
    return (
        ScenarioPosition("QTECH", "equity_index", Decimal("10"), Decimal("100"), "USD", "USD"),
        ScenarioPosition("QGOLD", "commodity", Decimal("5"), Decimal("200"), "USD", "USD"),
        ScenarioPosition(
            "QEUR", "cash", Decimal("100"), Decimal("1"), "EUR", "USD", Decimal("1.2")
        ),
    )


class ScenarioTests(unittest.TestCase):
    def test_price_asset_and_fx_shocks_revalue_decimal_positions(self) -> None:
        definition = ScenarioDefinition(
            "mixed",
            "Mixed stress",
            "1.0.0",
            (
                InstrumentPriceShock("QGOLD", Decimal("0.25")),
                AssetClassShock("equity_index", Decimal("-0.10")),
                FXShock("EUR", Decimal("-0.05")),
            ),
            ("fixed instantaneous shocks",),
        )
        result = run_scenario(definition, positions())
        self.assertEqual(result.base_value, Decimal("2120.0"))
        self.assertEqual(result.stressed_value, Decimal("2264.00"))
        self.assertEqual(result.pnl, Decimal("144.00"))
        self.assertTrue(result.hypothetical)

    def test_deterministic_ordering_and_run_id(self) -> None:
        shocks = (
            AssetClassShock("equity_index", Decimal("-0.1")),
            InstrumentPriceShock("QTECH", Decimal("-0.2")),
            VolatilityMultiplier(Decimal("2")),
        )
        left = ScenarioDefinition("same", "Same", "1.0.0", shocks, ("same assumptions",))
        right = ScenarioDefinition(
            "same", "Same", "1.0.0", tuple(reversed(shocks)), ("same assumptions",)
        )
        first = run_scenario(left, positions())
        second = run_scenario(right, tuple(reversed(positions())))
        self.assertEqual(first, second)
        self.assertEqual(first.deterministic_run_id, second.deterministic_run_id)

    def test_inputs_are_immutable_and_unmodified(self) -> None:
        original = positions()
        before = tuple(original)
        definition = ScenarioDefinition(
            "down",
            "Down",
            "1.0.0",
            (InstrumentPriceShock("QTECH", Decimal("-0.1")),),
            ("instantaneous",),
        )
        run_scenario(definition, original)
        self.assertEqual(original, before)
        with self.assertRaises(FrozenInstanceError):
            original[0].price = Decimal("0")  # type: ignore[misc]

    def test_volatility_and_correlation_are_analytical_outputs(self) -> None:
        definition = ScenarioDefinition(
            "analytical",
            "Analytical",
            "1.0.0",
            (
                VolatilityMultiplier(Decimal("1.5")),
                CorrelationOverride("QTECH", "QGOLD", Decimal("0.8")),
            ),
            ("no deterministic price P&L",),
        )
        result = run_scenario(definition, positions())
        self.assertEqual(result.pnl, Decimal("0.0"))
        self.assertEqual(result.volatility_multiplier, Decimal("1.5"))
        self.assertEqual(result.correlation_overrides[0].canonical_pair, ("QGOLD", "QTECH"))

    def test_unknown_target_and_duplicate_override_are_rejected(self) -> None:
        unknown = ScenarioDefinition(
            "bad",
            "Bad",
            "1.0.0",
            (InstrumentPriceShock("MISSING", Decimal("0.1")),),
            ("invalid fixture",),
        )
        with self.assertRaises(InvalidInputError):
            run_scenario(unknown, positions())
        duplicate = ScenarioDefinition(
            "dup",
            "Dup",
            "1.0.0",
            (
                CorrelationOverride("QTECH", "QGOLD", Decimal("0.5")),
                CorrelationOverride("QGOLD", "QTECH", Decimal("0.6")),
            ),
            ("invalid fixture",),
        )
        with self.assertRaises(InvalidInputError):
            run_scenario(duplicate, positions())

    def test_base_currency_fx_shock_is_rejected(self) -> None:
        definition = ScenarioDefinition(
            "bad-fx",
            "Bad FX",
            "1.0.0",
            (FXShock("USD", Decimal("0.1")),),
            ("invalid fixture",),
        )
        with self.assertRaises(InvalidInputError):
            run_scenario(definition, positions())

    def test_assumptions_are_part_of_deterministic_identity(self) -> None:
        shock = (InstrumentPriceShock("QTECH", Decimal("-0.1")),)
        left = ScenarioDefinition("identity", "Identity", "1.0.0", shock, ("first",))
        right = ScenarioDefinition("identity", "Identity", "1.0.0", shock, ("second",))
        self.assertNotEqual(
            run_scenario(left, positions()).deterministic_run_id,
            run_scenario(right, positions()).deterministic_run_id,
        )

    def test_all_named_system_scenarios_are_versioned_and_hypothetical(self) -> None:
        keys = (
            "equity_selloff_15pct",
            "oil_spike_25pct",
            "gold_down_10pct",
            "cross_asset_correlation_breakdown",
            "combined_liquidity_stress",
        )
        for key in keys:
            with self.subTest(key=key):
                result = system_scenario(key)
                self.assertEqual(result.version, "1.0.0")
                self.assertTrue(result.hypothetical)
                self.assertTrue(result.assumptions)


if __name__ == "__main__":
    unittest.main()
