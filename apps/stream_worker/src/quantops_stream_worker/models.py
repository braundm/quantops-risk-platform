"""Broker-neutral records and immutable service outcomes."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

_TOPIC = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,249}$")
_FAILURE_CODE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be timezone-aware UTC")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class BrokerRecord:
    topic: str
    partition: int
    offset: int
    value: bytes
    received_at: datetime

    def __post_init__(self) -> None:
        if _TOPIC.fullmatch(self.topic) is None:
            raise ValueError("topic must be a bounded broker-safe name")
        if self.partition < 0 or self.offset < 0:
            raise ValueError("partition and offset must be non-negative")
        if not isinstance(self.value, bytes):
            raise TypeError("record value must be bytes")
        object.__setattr__(self, "received_at", _utc(self.received_at, "received_at"))

    @property
    def coordinate(self) -> tuple[str, int, int]:
        return self.topic, self.partition, self.offset


class DeliveryStatus(StrEnum):
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    PROCESSED_LATE = "processed_late"
    REJECTED_DEAD_LETTERED = "rejected_dead_lettered"
    RETRY_EXHAUSTED = "retry_exhausted"
    COMMIT_DEFERRED = "commit_deferred"
    PARTITION_BLOCKED = "partition_blocked"


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    coordinate: tuple[str, int, int]
    status: DeliveryStatus
    event_id: UUID | None = None
    attempts: int = 0
    retry_delays_ms: tuple[int, ...] = ()


class IdempotencyDisposition(StrEnum):
    NEW = "new"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class DeadLetterRecord:
    id: UUID
    source_topic: str
    source_partition: int
    source_offset: int
    source_sha256: str
    source_size_bytes: int
    failure_code: str
    failure_kind: str
    created_at: datetime
    attempts: int
    event_id: UUID | None = None
    idempotency_key_sha256: str | None = None

    def __post_init__(self) -> None:
        if _FAILURE_CODE.fullmatch(self.failure_code) is None:
            raise ValueError("failure_code must be a safe identifier")
        if self.failure_kind not in {"contract", "permanent", "policy"}:
            raise ValueError("failure_kind is not an allowed terminal classification")
        if self.source_partition < 0 or self.source_offset < 0:
            raise ValueError("source coordinate must be non-negative")
        if _SHA256.fullmatch(self.source_sha256) is None or (
            self.idempotency_key_sha256 is not None
            and _SHA256.fullmatch(self.idempotency_key_sha256) is None
        ):
            raise ValueError("dead-letter digests must be SHA-256 hex")
        if self.source_size_bytes < 0 or self.attempts < 1:
            raise ValueError("dead-letter sizes and attempts must be positive")
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class Publication:
    topic: str
    key: bytes
    value: bytes
    published_at: datetime
    headers: Mapping[str, bytes] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if _TOPIC.fullmatch(self.topic) is None:
            raise ValueError("publication topic must be broker-safe")
        if not self.key or not self.value:
            raise ValueError("publication key and value must be non-empty")
        if not all(
            isinstance(key, str) and isinstance(value, bytes) for key, value in self.headers.items()
        ):
            raise TypeError("publication headers must map strings to bytes")
        object.__setattr__(self, "published_at", _utc(self.published_at, "published_at"))
        object.__setattr__(self, "headers", MappingProxyType(dict(sorted(self.headers.items()))))


class OutboxPublishStatus(StrEnum):
    PUBLISHED = "published"
    RETRY_SCHEDULED = "retry_scheduled"
    DEAD_LETTERED = "dead_lettered"


@dataclass(frozen=True, slots=True)
class OutboxPublishResult:
    event_id: UUID
    status: OutboxPublishStatus
    attempts: int
    retry_at: datetime | None = None
