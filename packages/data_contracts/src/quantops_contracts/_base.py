"""Shared constrained types and canonical JSON primitives."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

MAX_PAYLOAD_BYTES = 64 * 1024
MAX_MESSAGE_BYTES = 80 * 1024
MAX_RAW_INPUT_BYTES = MAX_MESSAGE_BYTES


class ContractModel(BaseModel):
    """Strict immutable base used by every public event model."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp offset must be UTC (+00:00 or Z)")
    return value.astimezone(UTC)


def _require_non_nil_uuid(value: UUID) -> UUID:
    if value.int == 0:
        raise ValueError("UUID must not be nil")
    return value


UtcDateTime = Annotated[datetime, AfterValidator(_require_utc)]
NonNilUuid = Annotated[UUID, AfterValidator(_require_non_nil_uuid)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
InstrumentSymbol = Annotated[
    str,
    StringConstraints(min_length=2, max_length=20, pattern=r"^[A-Z][A-Z0-9._-]+$"),
]
BoundedIdentifier = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"),
]
ProducerName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
]
MethodologyVersion = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
EvidenceId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"),
]
QuestionText = Annotated[str, StringConstraints(min_length=1, max_length=4_096)]
BriefContent = Annotated[str, StringConstraints(min_length=1, max_length=72_000)]
FiniteDecimal = Annotated[
    Decimal,
    Field(allow_inf_nan=False, max_digits=30, decimal_places=12),
]
PositiveDecimal = Annotated[
    Decimal,
    Field(gt=0, allow_inf_nan=False, max_digits=30, decimal_places=12),
]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=0, allow_inf_nan=False, max_digits=30, decimal_places=12),
]


def decimal_text(value: Decimal) -> str:
    """Return a finite, exponent-free, scale-normalized decimal representation."""

    if not value.is_finite():
        raise ValueError("cannot serialize a non-finite Decimal")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def to_primitive(value: Any) -> Any:
    """Convert supported values to deterministic JSON-compatible primitives."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return decimal_text(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        normalized = _require_utc(value)
        return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("cannot serialize a non-finite float")
        return value
    if isinstance(value, BaseModel):
        return to_primitive(value.model_dump(mode="python"))
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("canonical JSON mappings require string keys")
        return {key: to_primitive(value[key]) for key in sorted(value)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_primitive(item) for item in value]
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize supported values with sorted keys and no ambiguous numbers."""

    return json.dumps(
        to_primitive(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
