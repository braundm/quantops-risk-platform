"""Regular fixed-coupon bond sensitivity at a coupon boundary, nominal yield convention."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from quantops_risk.exceptions import InvalidInputError

VERSION = "treasury@1.0.0"
BP = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class BondTerms:
    """One regular bullet bond; no accrued interest, options, credit curve or default."""

    face: Decimal
    coupon_rate: Decimal
    yield_rate: Decimal
    years: int
    frequency: int

    def __post_init__(self) -> None:
        for value in (self.face, self.coupon_rate, self.yield_rate):
            if not isinstance(value, Decimal) or not value.is_finite():
                raise InvalidInputError("Bond amounts and rates must be finite Decimals")
        if not 0 < self.face <= Decimal("1e12"):
            raise InvalidInputError("Face must be positive and no greater than 1e12")
        if not Decimal(0) <= self.coupon_rate <= Decimal("0.5"):
            raise InvalidInputError("Coupon must be between zero and 50%")
        if not Decimal("-0.1") <= self.yield_rate <= Decimal(1):
            raise InvalidInputError("Nominal yield must be between -10% and 100%")
        if type(self.years) is not int or not 1 <= self.years <= 50:
            raise InvalidInputError("Remaining whole years must be between 1 and 50")
        if type(self.frequency) is not int or self.frequency not in (1, 2, 4, 12):
            raise InvalidInputError("Coupon frequency must be 1, 2, 4 or 12")


@dataclass(frozen=True, slots=True)
class BondSensitivity:
    price: Decimal
    macaulay_duration: Decimal
    modified_duration: Decimal
    convexity: Decimal
    dv01: Decimal


def _moments(terms: BondTerms, yield_rate: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    m = Decimal(terms.frequency)
    base = 1 + yield_rate / m
    if base <= 0:
        raise InvalidInputError("Discount factor must be positive")
    price = first = second = Decimal(0)
    count = terms.years * terms.frequency
    for period in range(1, count + 1):
        cash = terms.face * terms.coupon_rate / m
        if period == count:
            cash += terms.face
        pv = cash / base**period
        price += pv
        first += Decimal(period) / m * pv
        second += Decimal(period * (period + 1)) / (m * m * base * base) * pv
    return price, first, second


def bond_sensitivity(terms: BondTerms) -> BondSensitivity:
    """Analytic duration/convexity and positive loss magnitude for a +1bp yield move."""
    with localcontext() as context:
        context.prec = 40
        price, first, second = _moments(terms, terms.yield_rate)
        macaulay = first / price
        modified = macaulay / (1 + terms.yield_rate / terms.frequency)
        return BondSensitivity(price, macaulay, modified, second / price, modified * price * BP)


def shocked_bond_price(terms: BondTerms, shock_bp: int) -> Decimal:
    """Full repricing under a parallel nominal-yield change; not a forecast."""
    if type(shock_bp) is not int or not -200 <= shock_bp <= 200:
        raise InvalidInputError("Yield shock must be an integer between -200 and 200 bp")
    with localcontext() as context:
        context.prec = 40
        return _moments(terms, terms.yield_rate + Decimal(shock_bp) * BP)[0]
