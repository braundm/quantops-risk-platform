"""Typed records shared by the synthetic generator and quality validator."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class RuleCode(StrEnum):
    """Stable machine-readable codes emitted by the data-quality layer."""

    REQUIRED_FIELD = "DQ_REQUIRED_FIELD"
    MALFORMED_NUMBER = "DQ_MALFORMED_NUMBER"
    MALFORMED_TIMESTAMP = "DQ_MALFORMED_TIMESTAMP"
    INVALID_SYNTHETIC_MARKER = "DQ_INVALID_SYNTHETIC_MARKER"
    UNKNOWN_SYMBOL = "DQ_UNKNOWN_SYMBOL"
    UNKNOWN_REGIME = "DQ_UNKNOWN_REGIME"
    NON_FINITE_NUMBER = "DQ_NON_FINITE_NUMBER"
    NON_POSITIVE_PRICE = "DQ_NON_POSITIVE_PRICE"
    INVALID_OHLC = "DQ_INVALID_OHLC"
    NEGATIVE_VOLUME = "DQ_NEGATIVE_VOLUME"
    RECEIVED_BEFORE_EVENT = "DQ_RECEIVED_BEFORE_EVENT"
    LATE_ARRIVAL = "DQ_LATE_ARRIVAL"
    DUPLICATE_EVENT = "DQ_DUPLICATE_EVENT"
    MISSING_EXPECTED_BAR = "DQ_MISSING_EXPECTED_BAR"


class Severity(StrEnum):
    """Operational severity for a validation failure."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class RuleViolation:
    """One bounded validation finding, safe to serialize into run metadata."""

    code: RuleCode
    severity: Severity
    message: str
    observed_value: str
    expected_constraint: str

    def to_mapping(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
            "observed_value": self.observed_value,
            "expected_constraint": self.expected_constraint,
        }


class RecordParseError(ValueError):
    """Raised when a raw record cannot be converted to a typed price bar."""

    def __init__(self, violation: RuleViolation) -> None:
        super().__init__(violation.message)
        self.violation = violation


@dataclass(frozen=True, slots=True)
class PriceBar:
    """Canonical daily OHLCV record with explicit provenance and regime labels."""

    schema_version: str
    record_id: str
    source_event_id: str
    symbol: str
    timestamp: datetime
    received_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    currency: str
    interval: str
    regime: str
    source: str
    is_synthetic: bool

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> PriceBar:
        return cls(
            schema_version=_required_string(raw, "schema_version"),
            record_id=_required_string(raw, "record_id"),
            source_event_id=_required_string(raw, "source_event_id"),
            symbol=_required_string(raw, "symbol"),
            timestamp=_required_datetime(raw, "timestamp"),
            received_at=_required_datetime(raw, "received_at"),
            open=_required_decimal(raw, "open"),
            high=_required_decimal(raw, "high"),
            low=_required_decimal(raw, "low"),
            close=_required_decimal(raw, "close"),
            volume=_required_integer(raw, "volume"),
            currency=_required_string(raw, "currency"),
            interval=_required_string(raw, "interval"),
            regime=_required_string(raw, "regime"),
            source=_required_string(raw, "source"),
            is_synthetic=_required_boolean(raw, "is_synthetic"),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "record_id": self.record_id,
            "source_event_id": self.source_event_id,
            "symbol": self.symbol,
            "timestamp": _format_datetime(self.timestamp),
            "received_at": _format_datetime(self.received_at),
            "open": _format_decimal(self.open),
            "high": _format_decimal(self.high),
            "low": _format_decimal(self.low),
            "close": _format_decimal(self.close),
            "volume": self.volume,
            "currency": self.currency,
            "interval": self.interval,
            "regime": self.regime,
            "source": self.source,
            "is_synthetic": self.is_synthetic,
        }


def _required_value(raw: Mapping[str, object], field: str) -> object:
    if field not in raw or raw[field] is None or raw[field] == "":
        raise RecordParseError(
            RuleViolation(
                code=RuleCode.REQUIRED_FIELD,
                severity=Severity.ERROR,
                message=f"Required field '{field}' is missing.",
                observed_value="missing",
                expected_constraint=f"{field} must be present",
            )
        )
    return raw[field]


def _required_string(raw: Mapping[str, object], field: str) -> str:
    value = _required_value(raw, field)
    if not isinstance(value, str):
        raise RecordParseError(
            RuleViolation(
                code=RuleCode.REQUIRED_FIELD,
                severity=Severity.ERROR,
                message=f"Field '{field}' must be a string.",
                observed_value=type(value).__name__,
                expected_constraint=f"{field} must be a non-empty string",
            )
        )
    return value


def _required_decimal(raw: Mapping[str, object], field: str) -> Decimal:
    value = _required_value(raw, field)
    if isinstance(value, bool):
        value = str(value)
    try:
        return Decimal(str(value))
    except InvalidOperation as error:
        raise RecordParseError(
            RuleViolation(
                code=RuleCode.MALFORMED_NUMBER,
                severity=Severity.ERROR,
                message=f"Field '{field}' is not a valid decimal number.",
                observed_value=str(value)[:80],
                expected_constraint=f"{field} must be a finite decimal",
            )
        ) from error


def _required_integer(raw: Mapping[str, object], field: str) -> int:
    value = _required_value(raw, field)
    if isinstance(value, bool):
        parsed: int | None = None
    elif isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            parsed = None
    else:
        parsed = None
    if parsed is None:
        raise RecordParseError(
            RuleViolation(
                code=RuleCode.MALFORMED_NUMBER,
                severity=Severity.ERROR,
                message=f"Field '{field}' is not a valid integer.",
                observed_value=str(value)[:80],
                expected_constraint=f"{field} must be an integer",
            )
        )
    return parsed


def _required_boolean(raw: Mapping[str, object], field: str) -> bool:
    value = _required_value(raw, field)
    if not isinstance(value, bool):
        raise RecordParseError(
            RuleViolation(
                code=RuleCode.INVALID_SYNTHETIC_MARKER,
                severity=Severity.ERROR,
                message=f"Field '{field}' must be a JSON boolean.",
                observed_value=type(value).__name__,
                expected_constraint=f"{field} must be true",
            )
        )
    return value


def _required_datetime(raw: Mapping[str, object], field: str) -> datetime:
    value = _required_string(raw, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise RecordParseError(
            RuleViolation(
                code=RuleCode.MALFORMED_TIMESTAMP,
                severity=Severity.ERROR,
                message=f"Field '{field}' is not a valid ISO-8601 timestamp.",
                observed_value=value[:80],
                expected_constraint=f"{field} must be an offset-aware UTC timestamp",
            )
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RecordParseError(
            RuleViolation(
                code=RuleCode.MALFORMED_TIMESTAMP,
                severity=Severity.ERROR,
                message=f"Field '{field}' does not include a UTC offset.",
                observed_value=value[:80],
                expected_constraint=f"{field} must be an offset-aware UTC timestamp",
            )
        )
    return parsed.astimezone(UTC)


def _format_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _format_decimal(value: Decimal) -> str:
    return format(value, ".6f")
