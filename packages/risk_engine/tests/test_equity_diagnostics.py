"""Behavioral checks for descriptive concentration and equity risk diagnostics."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from quantops_risk.equity_diagnostics import (
    EquityDiagnostics,
    concentration_diagnostics,
    equity_diagnostics,
)
from quantops_risk.exceptions import InvalidInputError
from quantops_risk.portfolio_history import allocation_risk, performance_summary


def diagnostics(
    weights: dict[str, Decimal],
    *,
    count: int = 300,
    stale: bool = False,
    equities: set[str] | None = None,
) -> EquityDiagnostics:
    symbols = list(weights)
    rows = [[((-1) ** i) * 0.01 * (j + 1) for j in range(len(symbols))] for i in range(count)]
    days = [date(2023, 1, 1) + timedelta(days=i) for i in range(count + 1)]
    values = [100.0]
    for row in rows:
        values.append(
            values[-1] * (1 + sum(float(weights[s]) * r for s, r in zip(symbols, row, strict=True)))
        )
    return equity_diagnostics(
        symbols=symbols,
        weights=weights,
        issuer_ids={},
        daily_rows=rows,
        risk=allocation_risk(symbols, list(weights.values()), rows, 0.95),
        performance=performance_summary(days, values),
        curve=[(day, Decimal(str(v))) for day, v in zip(days, values, strict=True)],
        capital=Decimal(100000),
        equity_symbols=set(symbols) if equities is None else equities,
        stale_valuation=stale,
    )


def test_effective_holdings_and_single_name_losses_match_hand_calculation() -> None:
    equal = concentration_diagnostics({str(i): Decimal("0.2") for i in range(5)}, {})
    concentrated = {"a": Decimal("0.6"), **{str(i): Decimal("0.1") for i in range(4)}}
    report = concentration_diagnostics(concentrated, {})
    assert equal.hhi == Decimal("0.2") and equal.effective_positions == 5
    assert report.hhi == Decimal("0.4") and report.effective_positions == Decimal("2.5")
    result = diagnostics(concentrated)
    assert result.single_position_stress[0].pnl == -30000
    assert result.single_position_stress[0].value_after == 70000
    assert result.single_position_stress[0].portfolio_fraction == Decimal("-0.3")


def test_documented_share_classes_are_one_issuer_without_guessing_unknown_identities() -> None:
    report = concentration_diagnostics(
        {"a": Decimal("0.3"), "b": Decimal("0.3"), "c": Decimal("0.4"), "zero": Decimal(0)},
        {"a": "issuer", "b": "issuer"},
    )
    assert report.positions == 3 and report.groups == 2
    assert report.largest == Decimal("0.6")
    assert report.issuer_identity_coverage == Decimal("0.6")


@pytest.mark.parametrize(
    "weights",
    [{}, {"a": Decimal("NaN")}, {"a": Decimal("0.5")}, {"a": Decimal(2), "b": Decimal(-1)}],
)
def test_malformed_weights_are_never_turned_into_a_rating(weights: dict[str, Decimal]) -> None:
    with pytest.raises(InvalidInputError):
        concentration_diagnostics(weights, {})


def test_identical_return_drivers_do_not_create_a_diversification_benefit() -> None:
    report = diagnostics({"a": Decimal("0.5"), "b": Decimal("0.5")})
    assert report.weighted_correlation == pytest.approx(1)
    assert report.diversification_ratio == pytest.approx(1)
    assert report.score.status == "available"
    assert report.score.value is not None and 0 <= report.score.value <= 100
    assert sum(c.weight for c in report.score.components) == 1
    assert all(value <= 0 for _, value in report.drawdown_curve)


def test_insufficient_stale_or_non_equity_data_never_receive_a_complete_score() -> None:
    weights = {"a": Decimal("0.5"), "cash": Decimal("0.5")}
    for result, status in (
        (diagnostics(weights, count=251), "insufficient_data"),
        (diagnostics(weights, stale=True), "stale_valuation"),
        (diagnostics(weights, equities={"a"}), "outside_equity_scope"),
    ):
        assert result.score.status == status and result.score.value is None


def test_nonfinite_risk_is_rejected() -> None:
    rows = [[0.01], [-0.01]]
    days = [date(2023, 1, i) for i in (1, 2, 3)]
    with pytest.raises(InvalidInputError):
        equity_diagnostics(
            symbols=["a"],
            weights={"a": Decimal(1)},
            issuer_ids={},
            daily_rows=rows,
            risk=replace(
                allocation_risk(["a"], [Decimal(1)], rows, 0.95), annual_volatility=float("nan")
            ),
            performance=performance_summary(days, [100, 101, 99]),
            curve=list(zip(days, [Decimal(100), Decimal(101), Decimal(99)], strict=True)),
            capital=Decimal(100),
            equity_symbols={"a"},
            stale_valuation=False,
        )
