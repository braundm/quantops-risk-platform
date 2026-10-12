"""Independent identities and finite-difference checks for Treasury sensitivities."""

from decimal import Decimal as D
from decimal import localcontext

import pytest

from quantops_risk.exceptions import InvalidInputError
from quantops_risk.treasury import BondTerms, bond_sensitivity, shocked_bond_price


def test_zero_coupon_matches_closed_form() -> None:
    terms = BondTerms(D(1000), D(0), D("0.05"), 10, 2)
    result = bond_sensitivity(terms)
    assert float(result.price) == pytest.approx(1000 / 1.025**20)
    assert result.macaulay_duration == D(10)
    assert float(result.modified_duration) == pytest.approx(10 / 1.025)
    assert float(result.convexity) == pytest.approx(20 * 21 / (4 * 1.025**2))


@pytest.mark.parametrize("frequency", [1, 2, 4, 12])
def test_coupon_equals_yield_prices_at_par(frequency: int) -> None:
    result = bond_sensitivity(BondTerms(D(1000), D("0.04"), D("0.04"), 5, frequency))
    assert abs(result.price - D(1000)) < D("1e-30")
    assert 0 < result.modified_duration < result.macaulay_duration < 5


def test_analytic_derivatives_match_independent_repricing() -> None:
    terms = BondTerms(D(1000), D("0.04"), D("0.035"), 7, 2)
    result = bond_sensitivity(terms)
    with localcontext() as context:
        context.prec = 40
        up, down = shocked_bond_price(terms, 1), shocked_bond_price(terms, -1)
        assert float((down - up) / 2) == pytest.approx(float(result.dv01), rel=1e-6)
        second = (up - 2 * result.price + down) / (result.price * D("0.0001") ** 2)
        assert float(second) == pytest.approx(float(result.convexity), rel=1e-6)
    assert shocked_bond_price(terms, 0) == result.price
    assert shocked_bond_price(terms, 200) < result.price < shocked_bond_price(terms, -100)


def test_zero_and_negative_yields_remain_finite() -> None:
    for rate in (D(0), D("-0.1")):
        terms = BondTerms(D(1000), D("0.02"), rate, 50, 12)
        assert bond_sensitivity(terms).price.is_finite()
        assert shocked_bond_price(terms, -200).is_finite()


@pytest.mark.parametrize(
    "face,coupon,yield_rate,years,frequency",
    [
        (D("NaN"), D(0), D(0), 1, 1),
        (D(0), D(0), D(0), 1, 1),
        (D(100), D("-0.01"), D(0), 1, 1),
        (D(100), D(0), D("-1"), 1, 1),
        (D(100), D(0), D(0), 0, 1),
        (D(100), D(0), D(0), 1, 3),
    ],
)
def test_invalid_terms_fail_closed(
    face: D, coupon: D, yield_rate: D, years: int, frequency: int
) -> None:
    with pytest.raises(InvalidInputError):
        BondTerms(face, coupon, yield_rate, years, frequency)
