"""Point-in-time Decimal valuation with explicit base-currency conversion."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ._validation import strict_decimal
from .exceptions import (
    CurrencyMismatchError,
    DuplicateInstrumentError,
    InsufficientDataError,
    InvalidInputError,
    ReconciliationError,
)
from .types import PortfolioValuation, PositionInput, PositionValuation


def normalize_currency(value: str, *, name: str) -> str:
    if not isinstance(value, str):
        raise InvalidInputError(f"{name} must be a three-letter currency code")
    result = value.strip().upper()
    if len(result) != 3 or not result.isalpha() or not result.isascii():
        raise InvalidInputError(f"{name} must be a three-letter ASCII currency code")
    return result


def value_position(position: PositionInput) -> PositionValuation:
    """Value one position; FX means units of base currency per price currency."""

    if not position.instrument_id.strip():
        raise InvalidInputError("instrument_id must be non-empty")
    quantity = strict_decimal(position.quantity, name="quantity")
    price = strict_decimal(position.price, name="price")
    if price < 0:
        raise InvalidInputError("price must be nonnegative")
    price_currency = normalize_currency(position.price_currency, name="price_currency")
    base_currency = normalize_currency(position.base_currency, name="base_currency")

    if price_currency == base_currency:
        if position.fx_rate_to_base is None:
            fx_rate = Decimal("1")
        else:
            fx_rate = strict_decimal(position.fx_rate_to_base, name="fx_rate_to_base")
            if fx_rate != Decimal("1"):
                raise CurrencyMismatchError(
                    price_currency,
                    base_currency,
                    instrument_id=position.instrument_id,
                    reason="same-currency FX rate must equal exactly 1",
                )
    else:
        if position.fx_rate_to_base is None:
            raise CurrencyMismatchError(
                price_currency, base_currency, instrument_id=position.instrument_id
            )
        fx_rate = strict_decimal(position.fx_rate_to_base, name="fx_rate_to_base")
        if fx_rate <= 0:
            raise CurrencyMismatchError(
                price_currency,
                base_currency,
                instrument_id=position.instrument_id,
                reason="FX rate must be positive",
            )

    local_value = quantity * price
    market_value = local_value * fx_rate
    unrealized_pnl: Decimal | None = None
    if position.cost_basis_per_unit is not None:
        cost_basis = strict_decimal(position.cost_basis_per_unit, name="cost_basis_per_unit")
        if cost_basis < 0:
            raise InvalidInputError("cost_basis_per_unit must be nonnegative")
        unrealized_pnl = quantity * (price - cost_basis) * fx_rate

    return PositionValuation(
        instrument_id=position.instrument_id,
        quantity=quantity,
        local_market_value=local_value,
        market_value=market_value,
        base_currency=base_currency,
        fx_rate_to_base=fx_rate,
        unrealized_pnl=unrealized_pnl,
    )


def value_portfolio(
    positions: Iterable[PositionInput], *, reconciliation_tolerance: Decimal = Decimal("0.0001")
) -> PortfolioValuation:
    """Value positions in deterministic instrument order and reconcile totals."""

    tolerance = strict_decimal(reconciliation_tolerance, name="reconciliation_tolerance")
    if tolerance < 0:
        raise InvalidInputError("reconciliation_tolerance must be nonnegative")
    raw = tuple(positions)
    if not raw:
        raise InsufficientDataError("portfolio valuation", required=1, actual=0)
    identifiers = [position.instrument_id for position in raw]
    if len(set(identifiers)) != len(identifiers):
        duplicate = next(
            identifier for identifier in identifiers if identifiers.count(identifier) > 1
        )
        raise DuplicateInstrumentError(f"duplicate instrument_id: {duplicate}")

    components = tuple(
        sorted((value_position(position) for position in raw), key=lambda item: item.instrument_id)
    )
    currencies = {component.base_currency for component in components}
    if len(currencies) > 1:
        ordered = ", ".join(sorted(currencies))
        raise CurrencyMismatchError(ordered, "single portfolio base currency")
    base_currency = next(iter(currencies), "")
    total = sum((component.market_value for component in components), Decimal("0"))
    reconstructed = sum((component.market_value for component in components), Decimal("0"))
    difference = abs(total - reconstructed)
    if difference > tolerance:
        raise ReconciliationError(
            f"portfolio valuation difference {difference} exceeds tolerance {tolerance}"
        )

    pnl_values = [component.unrealized_pnl for component in components]
    total_pnl = (
        sum((value for value in pnl_values if value is not None), Decimal("0"))
        if components and all(value is not None for value in pnl_values)
        else None
    )
    return PortfolioValuation(
        components=components,
        total_market_value=total,
        total_unrealized_pnl=total_pnl,
        base_currency=base_currency,
        reconciled=difference <= tolerance,
    )
