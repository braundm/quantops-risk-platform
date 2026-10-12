"""Simplified constant-ADV liquidation capacity with explicit missing-data states."""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal, localcontext
from typing import Literal

from quantops_risk.exceptions import InvalidInputError


@dataclass(frozen=True, slots=True)
class LiquidityEstimate:
    status: Literal["valid", "insufficient"]
    observations: int
    adv: Decimal | None = None
    position_to_adv: Decimal | None = None
    days: int | None = None
    fraction_one_day: Decimal | None = None
    fraction_five_days: Decimal | None = None


def estimate_liquidity(
    quantity: Decimal, volumes: tuple[Decimal, ...], participation: Decimal
) -> LiquidityEstimate:
    """Use at least 20 supplied sessions; zero-volume sessions count, absent sessions do not."""
    values = (quantity, participation, *volumes)
    if any(not isinstance(v, Decimal) or not v.is_finite() for v in values):
        raise InvalidInputError("Liquidity inputs must be finite Decimals")
    if quantity <= 0 or not 0 < participation <= 1 or any(v < 0 for v in volumes):
        raise InvalidInputError(
            "Positive quantity, participation in (0, 1], nonnegative volumes required"
        )
    if not 20 <= len(volumes) <= 252:
        return LiquidityEstimate("insufficient", len(volumes))
    with localcontext() as context:
        context.prec = 40
        adv = sum(volumes, Decimal(0)) / len(volumes)
        if adv == 0:
            return LiquidityEstimate("insufficient", len(volumes), adv=adv)
        capacity = participation * adv
        return LiquidityEstimate(
            "valid",
            len(volumes),
            adv,
            quantity / adv,
            int((quantity / capacity).to_integral_value(rounding=ROUND_CEILING)),
            min(Decimal(1), capacity / quantity),
            min(Decimal(1), 5 * capacity / quantity),
        )
