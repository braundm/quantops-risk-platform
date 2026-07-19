"""Versioned envelope, type pairing, idempotency, and bounded serialization."""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from quantops_contracts._base import (
    MAX_MESSAGE_BYTES,
    MAX_PAYLOAD_BYTES,
    ContractModel,
    NonNilUuid,
    ProducerName,
    UtcDateTime,
    canonical_json,
)
from quantops_contracts.errors import MessageTooLargeError
from quantops_contracts.payloads import (
    AiBriefCreatedPayload,
    AiBriefRequestedPayload,
    EventPayload,
    Payload,
    PortfolioChangedPayload,
    PriceBarPayload,
    RiskRecomputeRequestedPayload,
    RiskSnapshotCreatedPayload,
)

SUPPORTED_SCHEMA_VERSIONS = (1,)


class EventType(StrEnum):
    MARKET_PRICE_BAR_V1 = "market.price_bar.v1"
    PORTFOLIO_CHANGED_V1 = "portfolio.changed.v1"
    RISK_RECOMPUTE_REQUESTED_V1 = "risk.recompute.requested.v1"
    RISK_SNAPSHOT_CREATED_V1 = "risk.snapshot.created.v1"
    AI_BRIEF_REQUESTED_V1 = "ai.brief.requested.v1"
    AI_BRIEF_CREATED_V1 = "ai.brief.created.v1"


EVENT_PAYLOAD_TYPES: dict[EventType, type[EventPayload]] = {
    EventType.MARKET_PRICE_BAR_V1: PriceBarPayload,
    EventType.PORTFOLIO_CHANGED_V1: PortfolioChangedPayload,
    EventType.RISK_RECOMPUTE_REQUESTED_V1: RiskRecomputeRequestedPayload,
    EventType.RISK_SNAPSHOT_CREATED_V1: RiskSnapshotCreatedPayload,
    EventType.AI_BRIEF_REQUESTED_V1: AiBriefRequestedPayload,
    EventType.AI_BRIEF_CREATED_V1: AiBriefCreatedPayload,
}

IdempotencyKey = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=200,
        pattern=r"^[a-z0-9][a-z0-9._:-]+$",
    ),
]


def derive_idempotency_key(
    event_type: EventType,
    schema_version: int,
    payload: EventPayload,
) -> str:
    """Derive a stable key from contract identity, never delivery metadata."""

    identity = {
        "event_type": event_type.value,
        "schema_version": schema_version,
        "identity_parts": payload.idempotency_parts(),
    }
    digest = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
    return f"{event_type.value}:{digest}"


class EventEnvelope(ContractModel):
    """Immutable v1 event envelope shared by all producers and consumers."""

    event_id: NonNilUuid
    event_type: EventType
    schema_version: Annotated[int, Field(ge=1, le=2_147_483_647)] = 1
    occurred_at: UtcDateTime
    received_at: UtcDateTime
    producer: ProducerName
    correlation_id: NonNilUuid
    causation_id: NonNilUuid | None = None
    idempotency_key: IdempotencyKey | None = None
    payload: Payload

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"unsupported schema_version {self.schema_version}; "
                f"supported versions are {SUPPORTED_SCHEMA_VERSIONS}"
            )
        expected_payload_type = EVENT_PAYLOAD_TYPES[self.event_type]
        if type(self.payload) is not expected_payload_type:
            raise ValueError(
                f"event_type {self.event_type.value} requires payload "
                f"{expected_payload_type.__name__}, received {type(self.payload).__name__}"
            )
        if self.received_at < self.occurred_at:
            raise ValueError("received_at must be greater than or equal to occurred_at")
        payload_event_time = _payload_event_time(self.payload)
        if payload_event_time is not None and payload_event_time != self.occurred_at:
            raise ValueError("occurred_at must equal the payload's authoritative event timestamp")

        expected_key = derive_idempotency_key(
            self.event_type,
            self.schema_version,
            self.payload,
        )
        if self.idempotency_key is None:
            object.__setattr__(self, "idempotency_key", expected_key)
        elif self.idempotency_key != expected_key:
            raise ValueError("idempotency_key does not match the payload's stable identity")

        payload_bytes = len(canonical_json(self.payload).encode("utf-8"))
        if payload_bytes > MAX_PAYLOAD_BYTES:
            raise ValueError(
                f"canonical payload is {payload_bytes} bytes; maximum is {MAX_PAYLOAD_BYTES}"
            )
        message_bytes = len(canonical_json(self).encode("utf-8"))
        if message_bytes > MAX_MESSAGE_BYTES:
            raise ValueError(
                f"canonical message is {message_bytes} bytes; maximum is {MAX_MESSAGE_BYTES}"
            )
        return self

    def to_canonical_json(self) -> str:
        """Return deterministic JSON with Decimal strings and normalized UTC timestamps."""

        result = canonical_json(self)
        actual_bytes = len(result.encode("utf-8"))
        if actual_bytes > MAX_MESSAGE_BYTES:
            raise MessageTooLargeError("canonical message", actual_bytes, MAX_MESSAGE_BYTES)
        return result

    def to_canonical_bytes(self) -> bytes:
        return self.to_canonical_json().encode("utf-8")

    @property
    def message_sha256(self) -> str:
        return hashlib.sha256(self.to_canonical_bytes()).hexdigest()

    @property
    def payload_sha256(self) -> str:
        return hashlib.sha256(canonical_json(self.payload).encode("utf-8")).hexdigest()


def _payload_event_time(payload: Payload) -> datetime | None:
    if isinstance(payload, PriceBarPayload):
        return payload.timestamp
    if isinstance(payload, PortfolioChangedPayload):
        return payload.changed_at
    if isinstance(payload, AiBriefRequestedPayload):
        return payload.requested_at
    if isinstance(payload, AiBriefCreatedPayload):
        return payload.created_at
    return None
