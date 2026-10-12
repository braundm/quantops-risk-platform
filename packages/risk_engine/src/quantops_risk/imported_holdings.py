"""Deterministic long-only spot ledger reconstruction using average remaining cost.

This is an exposure basis, not tax accounting or investment performance.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True)
class SpotFill:
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: Decimal
    price: Decimal
    at: datetime
    sequence: int


@dataclass(frozen=True)
class SpotHolding:
    symbol: str
    quantity: Decimal
    cost: Decimal
    first_purchase: datetime


def reconstruct_spot(fills: list[SpotFill]) -> list[SpotHolding]:
    """Keep unsold quantities; reject incomplete history rather than invent opening balances."""
    state: dict[str, SpotHolding] = {}
    for fill in sorted(fills, key=lambda row: (row.at, row.sequence)):
        if fill.at.utcoffset() is None or any(
            not value.is_finite() or value <= 0 for value in (fill.quantity, fill.price)
        ):
            raise ValueError("Spot fills require aware times and finite positive inputs")
        old = state.get(fill.symbol)
        if fill.side == "BUY":
            state[fill.symbol] = SpotHolding(
                fill.symbol,
                (old.quantity if old else Decimal(0)) + fill.quantity,
                (old.cost if old else Decimal(0)) + fill.quantity * fill.price,
                old.first_purchase if old else fill.at,
            )
        elif fill.side == "SELL":
            if old is None or fill.quantity > old.quantity:
                raise ValueError("Sale exceeds imported purchases; opening history is missing")
            remaining = old.quantity - fill.quantity
            if remaining:
                state[fill.symbol] = SpotHolding(
                    fill.symbol,
                    remaining,
                    old.cost * remaining / old.quantity,
                    old.first_purchase,
                )
            else:
                del state[fill.symbol]
        else:
            raise ValueError("Unsupported spot side")
    return list(state.values())


def mark_spot(
    quantity: Decimal,
    close: Decimal,
    cost: Decimal,
    comparable: bool,
) -> tuple[Decimal, Decimal | None, Decimal | None]:
    """Value current units; suppress cost comparisons after unreconciled corporate actions."""
    if any(not value.is_finite() or value <= 0 for value in (quantity, close, cost)):
        raise ValueError("Spot valuation requires finite positive inputs")
    value = quantity * close
    return value, cost if comparable else None, value - cost if comparable else None
