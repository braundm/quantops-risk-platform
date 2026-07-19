"""Internal validation and immutable-JSON helpers."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Never, cast
from uuid import UUID

from quantops_domain.errors import DomainValidationError

_EVENT_NAME = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_SENSITIVE_KEY_PARTS = frozenset(
    {
        "api_key",
        "authorization",
        "cookie",
        "credential",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "session",
        "token",
    }
)


def fail(field_name: str, message: str) -> Never:
    raise DomainValidationError(f"{field_name}: {message}")


def require_uuid(value: UUID, field_name: str) -> UUID:
    if not isinstance(value, UUID):
        fail(field_name, "must be a UUID")
    if value.int == 0:
        fail(field_name, "nil UUID is not permitted")
    return value


def require_optional_uuid(value: UUID | None, field_name: str) -> UUID | None:
    if value is not None:
        return require_uuid(value, field_name)
    return None


def as_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        fail(field_name, "must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        fail(field_name, "must be timezone-aware")
    return value.astimezone(UTC)


def require_decimal(
    value: Decimal,
    field_name: str,
    *,
    minimum: Decimal | None = None,
) -> Decimal:
    if not isinstance(value, Decimal):
        fail(field_name, "must be Decimal; float and implicit coercion are not permitted")
    if not value.is_finite():
        fail(field_name, "must be finite")
    if minimum is not None and value < minimum:
        fail(field_name, f"must be greater than or equal to {minimum}")
    return value


def require_int(
    value: int,
    field_name: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        fail(field_name, "must be an integer")
    if minimum is not None and value < minimum:
        fail(field_name, f"must be at least {minimum}")
    if maximum is not None and value > maximum:
        fail(field_name, f"must be at most {maximum}")
    return value


def require_text(
    value: str,
    field_name: str,
    *,
    maximum: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        fail(field_name, "must be a string")
    normalized = value.strip()
    if not normalized and not allow_empty:
        fail(field_name, "must not be empty")
    if len(normalized) > maximum:
        fail(field_name, f"must contain at most {maximum} characters")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in normalized):
        fail(field_name, "contains unsupported control characters")
    return normalized


def require_event_name(value: str, field_name: str = "event_type") -> str:
    value = require_text(value, field_name, maximum=120)
    if _EVENT_NAME.fullmatch(value) is None:
        fail(field_name, "must be a lowercase dotted event name")
    return value


def _normalize_sensitive_key(value: str) -> str:
    with_word_boundaries = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)
    return re.sub(r"[^a-z0-9]+", "_", with_word_boundaries.casefold()).strip("_")


def _reject_sensitive_key(key: str, field_name: str) -> None:
    normalized = _normalize_sensitive_key(key)
    padded = f"_{normalized}_"
    if any(f"_{forbidden}_" in padded for forbidden in _SENSITIVE_KEY_PARTS):
        fail(field_name, f"sensitive key {key!r} is not permitted")


def freeze_json_object(
    value: Mapping[str, Any],
    field_name: str,
    *,
    max_bytes: int,
    reject_sensitive_keys: bool = False,
) -> Mapping[str, Any]:
    """Validate JSON-native data, recursively freeze it, and enforce a size bound."""

    if not isinstance(value, Mapping):
        fail(field_name, "must be a mapping")

    active_ids: set[int] = set()

    def freeze(item: Any, path: str, depth: int) -> Any:
        if depth > 12:
            fail(path, "nesting exceeds 12 levels")
        if item is None or isinstance(item, (str, bool, int)):
            return item
        if isinstance(item, float):
            if not math.isfinite(item):
                fail(path, "floating-point JSON values must be finite")
            return item
        if isinstance(item, Mapping):
            item_id = id(item)
            if item_id in active_ids:
                fail(path, "cyclic data is not permitted")
            active_ids.add(item_id)
            try:
                frozen: dict[str, Any] = {}
                if not all(isinstance(key, str) for key in item):
                    fail(path, "all object keys must be strings")
                for key in sorted(item):
                    if reject_sensitive_keys:
                        _reject_sensitive_key(key, f"{path}.{key}")
                    frozen[key] = freeze(item[key], f"{path}.{key}", depth + 1)
                return MappingProxyType(frozen)
            finally:
                active_ids.remove(item_id)
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            item_id = id(item)
            if item_id in active_ids:
                fail(path, "cyclic data is not permitted")
            active_ids.add(item_id)
            try:
                return tuple(
                    freeze(child, f"{path}[{index}]", depth + 1) for index, child in enumerate(item)
                )
            finally:
                active_ids.remove(item_id)
        fail(path, f"unsupported JSON value type {type(item).__name__}")

    frozen_value = freeze(value, field_name, 0)
    encoded = json.dumps(
        thaw_json(frozen_value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > max_bytes:
        fail(field_name, f"canonical JSON exceeds {max_bytes} bytes")
    return cast(Mapping[str, Any], frozen_value)


def thaw_json(value: Any) -> Any:
    """Return ordinary JSON containers from recursively frozen domain data."""

    if isinstance(value, Mapping):
        return {key: thaw_json(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(child) for child in value]
    return value
