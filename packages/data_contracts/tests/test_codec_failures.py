"""Untrusted-boundary tests for versions, malformed JSON, secrets, and size limits."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import cast

import pytest
from pydantic import ValidationError

from quantops_contracts import (
    MAX_PAYLOAD_BYTES,
    MAX_RAW_INPUT_BYTES,
    AiBriefCreatedPayload,
    BriefStatus,
    EventEnvelope,
    EventType,
    MalformedEventError,
    MessageTooLargeError,
    UnsupportedEventTypeError,
    UnsupportedVersionError,
    parse_event_json,
)

from .factories import (
    AT,
    BRIEF_ID,
    CORRELATION_ID,
    EVENT_ID,
    REQUEST_ID,
    SNAPSHOT_ID,
    envelope,
    price_bar,
)


def _raw_event() -> dict[str, object]:
    decoded: object = json.loads(
        envelope(EventType.MARKET_PRICE_BAR_V1, price_bar(), AT).to_canonical_json()
    )
    assert isinstance(decoded, dict)
    return cast(dict[str, object], decoded)


@pytest.mark.parametrize("version", [0, 2, 99])
def test_future_or_invalid_schema_version_has_explicit_error(version: int) -> None:
    raw = _raw_event()
    raw["schema_version"] = version
    with pytest.raises(UnsupportedVersionError) as captured:
        parse_event_json(json.dumps(raw))
    assert captured.value.received_version == version
    assert captured.value.supported_versions == (1,)


def test_future_event_type_suffix_has_explicit_version_error() -> None:
    raw = _raw_event()
    raw["event_type"] = "market.price_bar.v2"
    raw["schema_version"] = 2
    with pytest.raises(UnsupportedVersionError, match=r"market\.price_bar"):
        parse_event_json(json.dumps(raw))


def test_unknown_event_family_is_explicitly_rejected() -> None:
    raw = _raw_event()
    raw["event_type"] = "orders.execute.v1"
    with pytest.raises(UnsupportedEventTypeError, match=r"orders\.execute\.v1"):
        parse_event_json(json.dumps(raw))


@pytest.mark.parametrize(
    "raw",
    [
        "not-json",
        "[]",
        '{"event_type":"market.price_bar.v1","event_type":"market.price_bar.v1"}',
        '{"value":NaN}',
    ],
)
def test_malformed_json_or_shape_is_rejected(raw: str) -> None:
    with pytest.raises(MalformedEventError):
        parse_event_json(raw)


def test_invalid_utf8_is_rejected() -> None:
    with pytest.raises(MalformedEventError, match="UTF-8"):
        parse_event_json(b"\xff\xfe")


def test_secret_shaped_extra_payload_field_is_forbidden() -> None:
    raw = _raw_event()
    payload = raw["payload"]
    assert isinstance(payload, dict)
    payload["api_key"] = "sk-" + "test-secret-must-not-enter-contract"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        parse_event_json(json.dumps(raw))


def test_raw_message_limit_applies_before_json_decoding() -> None:
    oversized = b" " * (MAX_RAW_INPUT_BYTES + 1)
    with pytest.raises(MessageTooLargeError) as captured:
        parse_event_json(oversized)
    assert captured.value.scope == "raw message"
    assert captured.value.actual_bytes == MAX_RAW_INPUT_BYTES + 1


def test_canonical_payload_limit_rejects_large_but_field_valid_content() -> None:
    content = "x" * (MAX_PAYLOAD_BYTES + 1_000)
    payload = AiBriefCreatedPayload(
        brief_id=BRIEF_ID,
        request_id=REQUEST_ID,
        snapshot_id=SNAPSHOT_ID,
        created_at=AT,
        provider="deterministic-template",
        status=BriefStatus.FALLBACK,
        content=content,
        cited_evidence_ids=(),
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        is_synthetic=True,
    )
    with pytest.raises(ValidationError, match="canonical payload"):
        EventEnvelope(
            event_id=EVENT_ID,
            event_type=EventType.AI_BRIEF_CREATED_V1,
            occurred_at=AT,
            received_at=AT + timedelta(seconds=1),
            producer="quantops-contract-tests",
            correlation_id=CORRELATION_ID,
            payload=payload,
        )


def test_input_type_must_be_text_or_bytes() -> None:
    with pytest.raises(TypeError, match="str, bytes, or bytearray"):
        parse_event_json(123)  # type: ignore[arg-type]
