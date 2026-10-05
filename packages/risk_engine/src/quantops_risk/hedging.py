"""Terminal, cash-settled FX forward sensitivity; no market quotes or execution."""

from dataclasses import dataclass
from decimal import Decimal

from ._validation import strict_decimal
from .exceptions import InvalidInputError


@dataclass(frozen=True, slots=True)
class ForwardComparison:
    ratio: Decimal
    signed_foreign_notional: Decimal
    base_notional: Decimal
    remaining_foreign_exposure: Decimal
    theoretical_forward: Decimal
    terminal_spot: Decimal
    payoff: Decimal
    entry_cost: Decimal
    holding_cost: Decimal
    net_payoff: Decimal


def compare_forward(
    *,
    foreign_exposure: Decimal,
    spot: Decimal,
    fx_shock: Decimal,
    ratio: Decimal,
    days: int,
    base_rate: Decimal,
    foreign_rate: Decimal,
    entry_bps: Decimal,
    annual_holding_bps: Decimal,
) -> ForwardComparison:
    """Use simple ACT/365 carry and signed notional, in base units per foreign unit.

    Positive exposure sells foreign currency forward; negative exposure buys it.
    Costs are base-currency estimates on absolute initial notional. Payoff is at
    maturity, undiscounted, and excludes collateral, counterparty and basis effects.
    """
    for name, value in (
        ("foreign_exposure", foreign_exposure),
        ("spot", spot),
        ("fx_shock", fx_shock),
        ("ratio", ratio),
        ("base_rate", base_rate),
        ("foreign_rate", foreign_rate),
        ("entry_bps", entry_bps),
        ("annual_holding_bps", annual_holding_bps),
    ):
        strict_decimal(value, name=name)
    if spot <= 0 or fx_shock <= -1 or not 0 <= ratio <= 1:
        raise InvalidInputError("positive spot, FX shock > -100%, and hedge ratio 0-100% required")
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 3650:
        raise InvalidInputError("forward maturity must be 1-3650 days")
    if entry_bps < 0 or annual_holding_bps < 0:
        raise InvalidInputError("forward costs must be nonnegative")
    term = Decimal(days) / Decimal(365)
    if 1 + base_rate * term <= 0 or 1 + foreign_rate * term <= 0:
        raise InvalidInputError("simple-interest accumulation factors must be positive")
    forward = spot * (1 + base_rate * term) / (1 + foreign_rate * term)
    terminal = spot * (1 + fx_shock)
    signed_notional = foreign_exposure * ratio
    base_notional = abs(signed_notional * spot)
    payoff = signed_notional * (forward - terminal)
    entry = base_notional * entry_bps / Decimal(10_000)
    holding = base_notional * annual_holding_bps / Decimal(10_000) * term
    return ForwardComparison(
        ratio,
        signed_notional,
        base_notional,
        foreign_exposure - signed_notional,
        forward,
        terminal,
        payoff,
        entry,
        holding,
        payoff - entry - holding,
    )
