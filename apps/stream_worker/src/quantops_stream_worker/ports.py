"""Async broker- and framework-independent worker ports."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from quantops_contracts import EventEnvelope
from quantops_domain import OutboxEvent

from quantops_stream_worker.models import (
    BrokerRecord,
    DeadLetterRecord,
    IdempotencyDisposition,
    Publication,
)


@runtime_checkable
class DurableEventProcessor(Protocol):
    """Durably records input and any derived output as one logical operation."""

    async def inspect(self, envelope: EventEnvelope) -> IdempotencyDisposition: ...

    async def process(
        self,
        envelope: EventEnvelope,
        *,
        late: bool,
    ) -> IdempotencyDisposition: ...


@runtime_checkable
class DeadLetterSink(Protocol):
    async def put(self, record: DeadLetterRecord) -> None: ...


@runtime_checkable
class OffsetCommitter(Protocol):
    async def commit(self, record: BrokerRecord) -> None: ...


@runtime_checkable
class BrokerPublisher(Protocol):
    async def publish(self, publication: Publication) -> None: ...


@runtime_checkable
class OutboxRepository(Protocol):
    async def add(self, event: OutboxEvent) -> None: ...

    async def claim_available(
        self,
        *,
        at: datetime,
        limit: int,
        worker_id: str,
    ) -> Sequence[OutboxEvent]: ...

    async def save(self, event: OutboxEvent) -> None: ...
