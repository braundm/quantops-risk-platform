"""Forward direction, carry and cost invariants on controlled terminal outcomes."""

from decimal import Decimal

import pytest

from quantops_risk.exceptions import InvalidInputError
from quantops_risk.hedging import compare_forward

D = Decimal


@pytest.mark.parametrize("exposure", [D("10000"), D("-10000")])
@pytest.mark.parametrize("shock", [D("-0.1"), D("0.1"), D("0")])
@pytest.mark.parametrize("ratio", [D("0"), D("0.5"), D("1")])
def test_forward_offsets_signed_currency_impact(
    exposure: Decimal,
    shock: Decimal,
    ratio: Decimal,
) -> None:
    result = compare_forward(
        foreign_exposure=exposure,
        spot=D(4),
        fx_shock=shock,
        ratio=ratio,
        days=90,
        base_rate=D(0),
        foreign_rate=D(0),
        entry_bps=D(0),
        annual_holding_bps=D(0),
    )
    unhedged = exposure * D(4) * shock
    assert unhedged + result.net_payoff == unhedged * (1 - ratio)
    assert result.signed_foreign_notional == exposure * ratio
    assert result.remaining_foreign_exposure == exposure * (1 - ratio)


def test_costs_use_absolute_notional_and_actual_term_without_charging_zero_hedge() -> None:
    result = compare_forward(
        foreign_exposure=D(-10000),
        spot=D(4),
        fx_shock=D("0.1"),
        ratio=D("0.5"),
        days=365,
        base_rate=D("0.04"),
        foreign_rate=D("0.02"),
        entry_bps=D(10),
        annual_holding_bps=D(20),
    )
    assert result.entry_cost == 20
    assert result.holding_cost == 40
    assert result.theoretical_forward == D(4) * D("1.04") / D("1.02")
    assert result.net_payoff == result.payoff - 60
    empty = compare_forward(
        foreign_exposure=D(100),
        spot=D(4),
        fx_shock=D("0.1"),
        ratio=D(0),
        days=365,
        base_rate=D(0),
        foreign_rate=D(0),
        entry_bps=D(100),
        annual_holding_bps=D(100),
    )
    assert empty.entry_cost == empty.holding_cost == empty.payoff == 0


@pytest.mark.parametrize(
    "spot,shock,ratio,days",
    [
        (D(0), D(0), D(1), 90),
        (D(4), D(-1), D(1), 90),
        (D(4), D(0), D("1.01"), 90),
        (D(4), D(0), D(1), 0),
        (D("NaN"), D(0), D(1), 90),
    ],
)
def test_invalid_forward_inputs_fail_closed(
    spot: Decimal,
    shock: Decimal,
    ratio: Decimal,
    days: int,
) -> None:
    with pytest.raises(InvalidInputError):
        compare_forward(
            foreign_exposure=D(100),
            spot=spot,
            fx_shock=shock,
            ratio=ratio,
            days=days,
            base_rate=D(0),
            foreign_rate=D(0),
            entry_bps=D(0),
            annual_holding_bps=D(0),
        )
