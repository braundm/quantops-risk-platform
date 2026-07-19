"""Round-trip, pairing, deterministic JSON, and idempotency contract tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from quantops_contracts import (
    EventEnvelope,
    EventType,
    Payload,
    PortfolioChangedPayload,
    canonical_json,
    parse_event_json,
)

from .factories import AT, envelope, event_cases, portfolio_changed, price_bar


@pytest.mark.parametrize(("event_type", "payload", "occurred_at"), event_cases())
def test_each_v1_contract_round_trips_byte_identically(
    event_type: EventType,
    payload: Payload,
    occurred_at: datetime,
) -> None:
    event = envelope(event_type, payload, occurred_at)

    encoded = event.to_canonical_json()
    decoded = parse_event_json(encoded)

    assert decoded == event
    assert decoded.to_canonical_json() == encoded
    assert len(event.idempotency_key or "") <= 200
    assert len(event.message_sha256) == 64
    assert len(event.payload_sha256) == 64


def test_decimal_json_is_string_safe_scale_normalized_and_sorted() -> None:
    event = envelope(EventType.MARKET_PRICE_BAR_V1, price_bar(), AT)
    encoded = event.to_canonical_json()

    assert '"open":"100.1"' in encoded
    assert '"close":"102.4"' in encoded
    assert '"timestamp":"2024-03-04T21:00:00.000000Z"' in encoded
    assert " " not in encoded
    assert encoded == canonical_json(event)


def test_duplicate_deliveries_keep_key_when_delivery_metadata_changes() -> None:
    payload = price_bar()
    first = envelope(EventType.MARKET_PRICE_BAR_V1, payload, AT)
    second = envelope(
        EventType.MARKET_PRICE_BAR_V1,
        payload,
        AT,
        event_id=UUID("10000000-0000-4000-8000-000000000002"),
        correlation_id=UUID("20000000-0000-4000-8000-000000000002"),
        received_delay=timedelta(minutes=2),
    )

    assert first.event_id != second.event_id
    assert first.idempotency_key == second.idempotency_key
    assert first.to_canonical_json() != second.to_canonical_json()


def test_conflicting_price_with_same_source_identity_keeps_duplicate_key() -> None:
    original = price_bar()
    corrected = price_bar(close=Decimal("101.25"), high=Decimal("103.00"))

    first = envelope(EventType.MARKET_PRICE_BAR_V1, original, AT)
    second = envelope(EventType.MARKET_PRICE_BAR_V1, corrected, AT)

    assert first.payload != second.payload
    assert first.idempotency_key == second.idempotency_key


def test_matching_explicit_idempotency_key_is_accepted() -> None:
    first = envelope(EventType.PORTFOLIO_CHANGED_V1, portfolio_changed(), AT)
    repeated = envelope(
        EventType.PORTFOLIO_CHANGED_V1,
        portfolio_changed(),
        AT,
        idempotency_key=first.idempotency_key,
    )
    assert repeated.idempotency_key == first.idempotency_key


def test_mismatched_explicit_idempotency_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="idempotency_key does not match"):
        envelope(
            EventType.PORTFOLIO_CHANGED_V1,
            portfolio_changed(),
            AT,
            idempotency_key="portfolio.changed.v1:not-the-derived-key",
        )


def test_event_type_payload_pairing_is_enforced() -> None:
    with pytest.raises(ValidationError, match="requires payload PriceBarPayload"):
        envelope(EventType.MARKET_PRICE_BAR_V1, portfolio_changed(), AT)


def test_received_timestamp_cannot_precede_occurrence() -> None:
    with pytest.raises(ValidationError, match="received_at must be"):
        envelope(
            EventType.MARKET_PRICE_BAR_V1,
            price_bar(),
            AT,
            received_delay=timedelta(seconds=-1),
        )


def test_authoritative_payload_time_must_match_occurrence() -> None:
    with pytest.raises(ValidationError, match="authoritative event timestamp"):
        envelope(EventType.MARKET_PRICE_BAR_V1, price_bar(), AT + timedelta(seconds=1))


def test_envelope_forbids_unknown_headers() -> None:
    raw = json.loads(envelope(EventType.MARKET_PRICE_BAR_V1, price_bar(), AT).to_canonical_json())
    raw["authorization"] = "Bearer secret-value"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EventEnvelope.model_validate(raw)


def test_payload_model_remains_immutable() -> None:
    payload = portfolio_changed()
    with pytest.raises(ValidationError, match="frozen"):
        payload.portfolio_version = 3  # type: ignore[misc]
    assert isinstance(payload, PortfolioChangedPayload)
