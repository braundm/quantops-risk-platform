"""Transactional-outbox domain record and bounded retry state machine."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from quantops_domain._validation import (
    as_utc,
    fail,
    freeze_json_object,
    require_event_name,
    require_int,
    require_optional_uuid,
    require_text,
    require_uuid,
    thaw_json,
)
from quantops_domain.enums import OutboxStatus
from quantops_domain.errors import InvalidStateTransitionError
from quantops_domain.serialization import canonical_json


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    """An immutable domain event awaiting durable, at-least-once publication."""

    id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    schema_version: int
    producer: str
    idempotency_key: str
    occurred_at: datetime
    available_at: datetime
    correlation_id: UUID
    payload: Mapping[str, Any] = field(hash=False, repr=False)
    causation_id: UUID | None = None
    status: OutboxStatus = OutboxStatus.PENDING
    attempts: int = 0
    published_at: datetime | None = None
    error_summary: str | None = None

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        aggregate_type = require_text(self.aggregate_type, "aggregate_type", maximum=80).casefold()
        require_uuid(self.aggregate_id, "aggregate_id")
        event_type = require_event_name(self.event_type)
        require_int(self.schema_version, "schema_version", minimum=1, maximum=2_147_483_647)
        producer = require_text(self.producer, "producer", maximum=80).casefold()
        idempotency_key = require_text(
            self.idempotency_key,
            "idempotency_key",
            maximum=200,
        )
        occurred_at = as_utc(self.occurred_at, "occurred_at")
        available_at = as_utc(self.available_at, "available_at")
        if available_at < occurred_at:
            fail("available_at", "must not precede occurred_at")
        require_uuid(self.correlation_id, "correlation_id")
        require_optional_uuid(self.causation_id, "causation_id")
        if not isinstance(self.status, OutboxStatus):
            fail("status", "must be OutboxStatus")
        require_int(self.attempts, "attempts", minimum=0)
        published_at = (
            as_utc(self.published_at, "published_at") if self.published_at is not None else None
        )
        if published_at is not None and published_at < occurred_at:
            fail("published_at", "must not precede occurred_at")
        error_summary = self.error_summary
        if error_summary is not None:
            error_summary = require_text(error_summary, "error_summary", maximum=512)
        payload = freeze_json_object(
            self.payload,
            "payload",
            max_bytes=65_536,
            reject_sensitive_keys=True,
        )

        if self.status is OutboxStatus.PENDING:
            if self.attempts != 0 or published_at is not None or error_summary is not None:
                fail("status", "pending events cannot have attempts, publication, or error state")
        elif self.status is OutboxStatus.RETRY_SCHEDULED:
            if self.attempts < 1 or published_at is not None or error_summary is None:
                fail("status", "retry events require attempts and an error, but no publication")
        elif self.status is OutboxStatus.PUBLISHED:
            if self.attempts < 1 or published_at is None or error_summary is not None:
                fail("status", "published events require a successful attempt and timestamp")
        elif self.status is OutboxStatus.DEAD_LETTER and (
            self.attempts < 1 or published_at is not None or error_summary is None
        ):
            fail("status", "dead-letter events require attempts and an error, but no publication")

        object.__setattr__(self, "aggregate_type", aggregate_type)
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "producer", producer)
        object.__setattr__(self, "idempotency_key", idempotency_key)
        object.__setattr__(self, "occurred_at", occurred_at)
        object.__setattr__(self, "available_at", available_at)
        object.__setattr__(self, "published_at", published_at)
        object.__setattr__(self, "error_summary", error_summary)
        object.__setattr__(self, "payload", payload)

    @classmethod
    def pending(
        cls,
        *,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        schema_version: int,
        producer: str,
        idempotency_key: str,
        occurred_at: datetime,
        payload: Mapping[str, Any],
        available_at: datetime | None = None,
        event_id: UUID | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> OutboxEvent:
        return cls(
            id=event_id or uuid4(),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            schema_version=schema_version,
            producer=producer,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
            available_at=available_at or occurred_at,
            correlation_id=correlation_id or uuid4(),
            causation_id=causation_id,
            payload=payload,
        )

    def is_available(self, at: datetime) -> bool:
        at = as_utc(at, "at")
        return self.status in {OutboxStatus.PENDING, OutboxStatus.RETRY_SCHEDULED} and (
            self.available_at <= at
        )

    def record_failure(
        self,
        *,
        error_summary: str,
        max_attempts: int,
        retry_at: datetime | None = None,
    ) -> OutboxEvent:
        if self.status not in {OutboxStatus.PENDING, OutboxStatus.RETRY_SCHEDULED}:
            raise InvalidStateTransitionError(f"cannot fail an event in {self.status} state")
        require_int(max_attempts, "max_attempts", minimum=1)
        next_attempts = self.attempts + 1
        if next_attempts >= max_attempts:
            return replace(
                self,
                status=OutboxStatus.DEAD_LETTER,
                attempts=next_attempts,
                error_summary=error_summary,
            )
        if retry_at is None:
            fail("retry_at", "is required while retries remain")
        normalized_retry_at = as_utc(retry_at, "retry_at")
        if normalized_retry_at < self.occurred_at:
            fail("retry_at", "must not precede occurred_at")
        return replace(
            self,
            status=OutboxStatus.RETRY_SCHEDULED,
            attempts=next_attempts,
            available_at=normalized_retry_at,
            error_summary=error_summary,
        )

    def mark_published(self, *, published_at: datetime) -> OutboxEvent:
        if self.status not in {OutboxStatus.PENDING, OutboxStatus.RETRY_SCHEDULED}:
            raise InvalidStateTransitionError(f"cannot publish an event in {self.status} state")
        return replace(
            self,
            status=OutboxStatus.PUBLISHED,
            attempts=self.attempts + 1,
            published_at=published_at,
            error_summary=None,
        )

    @property
    def event_envelope(self) -> Mapping[str, Any]:
        return {
            "event_id": str(self.id),
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "occurred_at": self.occurred_at.isoformat().replace("+00:00", "Z"),
            "producer": self.producer,
            "correlation_id": str(self.correlation_id),
            "causation_id": str(self.causation_id) if self.causation_id is not None else None,
            "idempotency_key": self.idempotency_key,
            "payload": thaw_json(self.payload),
        }

    @property
    def serialized_envelope(self) -> str:
        return canonical_json(self.event_envelope)

    @property
    def payload_hash(self) -> str:
        return hashlib.sha256(
            canonical_json(self.payload).encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()
