"""Untrusted JSON boundary with version routing and pre-parse size limits."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import cast

from quantops_contracts._base import MAX_RAW_INPUT_BYTES
from quantops_contracts.envelope import (
    EVENT_PAYLOAD_TYPES,
    SUPPORTED_SCHEMA_VERSIONS,
    EventEnvelope,
    EventType,
)
from quantops_contracts.errors import (
    MalformedEventError,
    MessageTooLargeError,
    UnsupportedEventTypeError,
    UnsupportedVersionError,
)

_VERSIONED_EVENT_TYPE = re.compile(r"^(?P<family>[a-z0-9._-]+)\.v(?P<version>[0-9]+)$")
_EVENT_FAMILIES = {event_type.value.rsplit(".v", maxsplit=1)[0] for event_type in EventType}


def parse_event_json(raw: str | bytes | bytearray) -> EventEnvelope:
    """Decode one bounded JSON message and route it to its exact v1 payload schema."""

    raw_bytes = _raw_bytes(raw)
    if len(raw_bytes) > MAX_RAW_INPUT_BYTES:
        raise MessageTooLargeError("raw message", len(raw_bytes), MAX_RAW_INPUT_BYTES)
    try:
        text = raw_bytes.decode("utf-8")
        decoded: object = json.loads(
            text,
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_unique_object,
        )
    except UnicodeDecodeError as error:
        raise MalformedEventError("event must be valid UTF-8") from error
    except json.JSONDecodeError as error:
        raise MalformedEventError(f"event is not valid JSON: {error.msg}") from error
    return parse_event_mapping(_mapping(decoded, "event"))


def parse_event_mapping(raw: Mapping[str, object]) -> EventEnvelope:
    """Validate an already-decoded mapping with explicit type/version dispatch."""

    event_type = _resolve_event_type(raw.get("event_type"), raw.get("schema_version"))
    payload_raw = _mapping(raw.get("payload"), "payload")
    payload_type = EVENT_PAYLOAD_TYPES[event_type]
    payload = payload_type.model_validate(payload_raw)
    envelope_raw = dict(raw)
    envelope_raw["event_type"] = event_type
    envelope_raw["payload"] = payload
    return EventEnvelope.model_validate(envelope_raw)


def _resolve_event_type(event_type_raw: object, schema_version_raw: object) -> EventType:
    if isinstance(schema_version_raw, bool) or not isinstance(schema_version_raw, int):
        raise UnsupportedVersionError("event", schema_version_raw)
    if isinstance(event_type_raw, str):
        try:
            event_type = EventType(event_type_raw)
        except ValueError:
            match = _VERSIONED_EVENT_TYPE.fullmatch(event_type_raw)
            if match is not None and match.group("family") in _EVENT_FAMILIES:
                raise UnsupportedVersionError(
                    match.group("family"),
                    int(match.group("version")),
                    SUPPORTED_SCHEMA_VERSIONS,
                ) from None
            raise UnsupportedEventTypeError(event_type_raw) from None
        if schema_version_raw not in SUPPORTED_SCHEMA_VERSIONS:
            raise UnsupportedVersionError(
                event_type.value.rsplit(".v", maxsplit=1)[0],
                schema_version_raw,
                SUPPORTED_SCHEMA_VERSIONS,
            )
        return event_type
    raise UnsupportedEventTypeError(event_type_raw)


def _raw_bytes(raw: str | bytes | bytearray) -> bytes:
    if isinstance(raw, str):
        return raw.encode("utf-8")
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, bytearray):
        return bytes(raw)
    raise TypeError("raw event must be str, bytes, or bytearray")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise MalformedEventError(f"{label} must be a JSON object with string keys")
    return cast(dict[str, object], value)


def _reject_json_constant(value: str) -> object:
    raise MalformedEventError(f"non-finite JSON number is forbidden: {value}")


def _unique_object(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MalformedEventError(f"duplicate JSON object key is forbidden: {key}")
        result[key] = value
    return result
