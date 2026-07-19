"""Typed failures raised at the risk-engine boundary."""

from __future__ import annotations


class RiskEngineError(ValueError):
    """Base class for expected, user-correctable risk input failures."""


class InvalidInputError(RiskEngineError):
    """An input is malformed, non-finite, or outside its valid domain."""


class InsufficientDataError(RiskEngineError):
    """A caller explicitly requested a value that cannot yet be estimated."""

    def __init__(self, metric: str, *, required: int, actual: int) -> None:
        self.metric = metric
        self.required = required
        self.actual = actual
        super().__init__(f"{metric} requires at least {required} observations; received {actual}")


class MissingDataError(RiskEngineError):
    """A required observation is missing under the selected missing-data policy."""

    def __init__(self, index: int) -> None:
        self.index = index
        super().__init__(f"missing observation at index {index}")


class NonPositivePriceError(RiskEngineError):
    """A price is nonpositive where a positive price is mathematically required."""

    def __init__(self, index: int, value: object) -> None:
        self.index = index
        self.value = value
        super().__init__(f"price at index {index} must be positive; received {value!r}")


class CurrencyMismatchError(RiskEngineError):
    """Currency conversion data is absent, contradictory, or ambiguous."""

    def __init__(
        self,
        price_currency: str,
        base_currency: str,
        *,
        instrument_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        self.price_currency = price_currency
        self.base_currency = base_currency
        self.instrument_id = instrument_id
        detail = reason or "an explicit FX rate to base currency is required"
        context = f" for {instrument_id}" if instrument_id else ""
        super().__init__(
            f"currency mismatch{context}: {price_currency} -> {base_currency}; {detail}"
        )


class DuplicateInstrumentError(RiskEngineError):
    """A portfolio-like input contains a repeated instrument identifier."""


class ReconciliationError(RiskEngineError):
    """Independent component and portfolio totals do not agree within tolerance."""
