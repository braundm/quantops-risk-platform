from datetime import date, timedelta
from decimal import Decimal
from math import sqrt
from statistics import stdev

import pytest

from quantops_risk.portfolio_history import allocation_risk, compound_shock, performance_summary


def test_identical_assets_and_cash_reconcile_without_singular_matrix_noise() -> None:
    returns = [-0.02, -0.01, 0.01, 0.02]
    risk = allocation_risk(
        ["a", "b", "cash"],
        [Decimal("0.4"), Decimal("0.4"), Decimal("0.2")],
        [[r, r, 0] for r in returns],
        0.95,
    )
    assert risk.annual_volatility == pytest.approx(stdev(returns) * 0.8 * sqrt(252))
    assert risk.risk_shares == pytest.approx({"a": 0.5, "b": 0.5, "cash": 0.0})
    assert sum(risk.components.values()) == pytest.approx(risk.annual_volatility)
    assert risk.correlations[0][1] == pytest.approx(1)
    assert risk.correlations[0][2] is None
    assert risk.status == "insufficient_data"
    assert risk.var_fraction is None


def test_hedging_asset_keeps_negative_component() -> None:
    returns = [-0.02, -0.01, 0.01, 0.02]
    risk = allocation_risk(
        ["a", "hedge"], [Decimal("0.8"), Decimal("0.2")], [[r, -0.4 * r] for r in returns], 0.95
    )
    assert risk.risk_shares["hedge"] == pytest.approx(-1 / 9)
    assert risk.risk_shares["a"] == pytest.approx(10 / 9)
    assert risk.components["hedge"] < 0
    assert risk.reconciliation_error == pytest.approx(0, abs=1e-12)


def test_price_and_fx_cross_term_is_exact() -> None:
    assert compound_shock(Decimal(400), Decimal("-0.2"), Decimal("-0.1")) == Decimal(-112)


def test_unrecovered_drawdown_dates_and_partial_calendar_returns() -> None:
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(5)]
    result = performance_summary(days, [100, 80, 90, 70, 95])
    assert result.maximum_drawdown == pytest.approx(0.3)
    assert result.current_drawdown == pytest.approx(-0.05)
    assert result.peak_to_trough_days == 3
    assert result.recovery is None
    assert result.worst_month_return == pytest.approx(-0.05)
    assert result.partial_months == ("2024-01",)


def test_recovery_counts_days_from_trough_without_inventing_later_history() -> None:
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(4)]
    result = performance_summary(days, [100, 80, 90, 100])
    assert result.recovery == days[-1]
    assert result.recovery_days == 2


def test_all_cash_has_zero_risk_and_undefined_percentage_attribution() -> None:
    risk = allocation_risk(["cash"], [Decimal(1)], [[0.0]] * 300, 0.95)
    assert risk.annual_volatility == 0
    assert risk.var_fraction == 0
    assert risk.es_fraction == 0
    assert risk.risk_shares["cash"] is None


def test_missing_calendar_boundary_does_not_turn_multi_month_loss_into_one_month() -> None:
    result = performance_summary([date(2024, 1, 5), date(2024, 3, 6)], [100, 80])
    assert result.period_return == pytest.approx(-0.2)
    assert result.worst_month is None
    assert result.worst_month_return is None
    assert result.partial_months == ("2024-01", "2024-03")
