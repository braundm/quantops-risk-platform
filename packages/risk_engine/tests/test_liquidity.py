"""Capacity identities and unavailable/invalid-data behavior."""

from decimal import Decimal as D

import pytest

from quantops_risk.exceptions import InvalidInputError
from quantops_risk.liquidity import estimate_liquidity


def test_capacity_rounds_up_and_participation_is_monotone() -> None:
    result = estimate_liquidity(D(8001), (D(10000),) * 20, D("0.1"))
    assert result.status == "valid"
    assert result.adv == D(10000)
    assert result.position_to_adv == D("0.8001")
    assert result.days == 9
    assert float(result.fraction_one_day or 0) == pytest.approx(1000 / 8001)
    assert estimate_liquidity(D(8001), (D(10000),) * 20, D("0.2")).days == 5


def test_zero_sessions_count_and_capacity_is_capped() -> None:
    result = estimate_liquidity(D(100), (D(0), D(20000)) * 10, D("0.1"))
    assert result.adv == D(10000)
    assert result.days == 1
    assert result.fraction_one_day == result.fraction_five_days == D(1)


@pytest.mark.parametrize("volumes", [(), (D(100),) * 19, (D(0),) * 20])
def test_missing_or_zero_adv_withholds_days(volumes: tuple[D, ...]) -> None:
    result = estimate_liquidity(D(100), volumes, D("0.1"))
    assert result.status == "insufficient"
    assert result.days is None


@pytest.mark.parametrize(
    "quantity,volume,participation",
    [
        (D(0), D(10), D("0.1")),
        (D(1), D(-1), D("0.1")),
        (D(1), D(10), D(0)),
        (D("NaN"), D(10), D("0.1")),
    ],
)
def test_invalid_inputs_raise(quantity: D, volume: D, participation: D) -> None:
    with pytest.raises(InvalidInputError):
        estimate_liquidity(quantity, (volume,) * 20, participation)
