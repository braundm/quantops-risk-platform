"""Canonical, deterministic serialization for domain evidence and events."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from quantops_domain._validation import as_utc
from quantops_domain.errors import DomainValidationError
from quantops_domain.value_objects import Currency, InstrumentSymbol, Money


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise DomainValidationError("cannot serialize a non-finite Decimal")
    return str(value)


def to_primitive(value: Any) -> Any:
    """Convert domain values to a stable JSON-compatible representation."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainValidationError("cannot serialize a non-finite float")
        return value
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return as_utc(value, "datetime").isoformat().replace("+00:00", "Z")
    if isinstance(value, Currency):
        return value.code
    if isinstance(value, InstrumentSymbol):
        return value.value
    if isinstance(value, Money):
        return {"amount": _decimal_text(value.amount), "currency": value.currency.code}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise DomainValidationError("only string-keyed mappings can be serialized")
        return {key: to_primitive(value[key]) for key in sorted(value)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_primitive(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: to_primitive(getattr(value, item.name))
            for item in fields(value)
            if not item.name.startswith("_")
        }
    raise DomainValidationError(f"unsupported serialization type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize with sorted keys and no platform-dependent whitespace."""

    return json.dumps(
        to_primitive(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
