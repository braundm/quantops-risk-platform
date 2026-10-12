"""Current stock holdings in separate native-currency buckets; no inferred executions."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from .exceptions import InvalidInputError


@dataclass(frozen=True)
class StockMark:
    currency: str
    quantity: Decimal
    close: Decimal
    purchase_price: Decimal | None
    cost_comparable: bool = True


@dataclass(frozen=True)
class StockValue:
    value: Decimal
    cost: Decimal | None
    unrealized_change: Decimal | None
    status: Literal["ok", "unknown_cost", "corporate_action_review"]


def value_stock(mark: StockMark) -> StockValue:
    """Use current units; suppress cost comparisons requiring corporate-action reconciliation."""
    values = [mark.quantity, mark.close]
    if mark.purchase_price is not None:
        values.append(mark.purchase_price)
    if mark.currency not in {"USD", "PLN"} or any(not v.is_finite() or v <= 0 for v in values):
        raise InvalidInputError("Stock quantities and prices must be finite and positive")
    value = mark.quantity * mark.close
    if not mark.cost_comparable:
        return StockValue(value, None, None, "corporate_action_review")
    if mark.purchase_price is None:
        return StockValue(value, None, None, "unknown_cost")
    cost = mark.quantity * mark.purchase_price
    return StockValue(value, cost, value - cost, "ok")
