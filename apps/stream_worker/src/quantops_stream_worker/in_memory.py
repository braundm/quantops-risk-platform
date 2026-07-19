"""Deterministic adapters for tests, local replay, and offline demonstrations."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from quantops_contracts import (
    EventEnvelope,
    EventType,
    PortfolioChangedPayload,
    RecomputeReason,
    RiskRecomputeRequestedPayload,
)
from quantops_domain import OutboxEvent

from quantops_stream_worker.config import WorkerConfig
from quantops_stream_worker.errors import BrokerUnavailableError, TransientProcessingError
from quantops_stream_worker.models import (
    BrokerRecord,
    DeadLetterRecord,
    IdempotencyDisposition,
    Publication,
)

_NAMESPACE = uuid5(NAMESPACE_URL, "https://quantops.dev/stream-worker/v1")


def _idempotency_key(envelope: EventEnvelope) -> str:
    key = envelope.idempotency_key
    if key is None:  # EventEnvelope validation always derives it; retain a typed guard.
        raise RuntimeError("validated event envelope has no idempotency key")
    return key


def _content_fingerprint(envelope: EventEnvelope) -> str:
    """Exclude delivery metadata while detecting identity/content collisions."""

    return f"{envelope.event_type.value}:{envelope.schema_version}:{envelope.payload_sha256}"


class InMemoryOutboxRepository:
    """Stable in-memory implementation of the domain outbox repository contract."""

    def __init__(self, *, trace: list[str] | None = None) -> None:
        self._events: dict[UUID, OutboxEvent] = {}
        self.trace = trace if trace is not None else []
        self.fail_writes_remaining = 0

    async def add(self, event: OutboxEvent) -> None:
        self._check_write()
        existing = self._events.get(event.id)
        if existing is not None:
            if existing.serialized_envelope != event.serialized_envelope:
                raise TransientProcessingError("outbox_identity_conflict")
            return
        self._events[event.id] = event
        self.trace.append(f"outbox:add:{event.id}")

    async def claim_available(
        self,
        *,
        at: datetime,
        limit: int,
        worker_id: str,
    ) -> Sequence[OutboxEvent]:
        del worker_id
        if limit < 1:
            raise ValueError("claim limit must be positive")
        values = (event for event in self._events.values() if event.is_available(at))
        return tuple(
            sorted(values, key=lambda item: (item.available_at, item.occurred_at, item.id))[:limit]
        )

    async def save(self, event: OutboxEvent) -> None:
        self._check_write()
        if event.id not in self._events:
            raise TransientProcessingError("outbox_event_missing")
        self._events[event.id] = event
        self.trace.append(f"outbox:save:{event.id}:{event.status.value}")

    def get(self, event_id: UUID) -> OutboxEvent:
        return self._events[event_id]

    @property
    def events(self) -> tuple[OutboxEvent, ...]:
        return tuple(sorted(self._events.values(), key=lambda item: (item.occurred_at, item.id)))

    def _check_write(self) -> None:
        if self.fail_writes_remaining > 0:
            self.fail_writes_remaining -= 1
            raise TransientProcessingError("outbox_write_unavailable")


class InMemoryDurableEventProcessor:
    """Atomic in-memory input ledger with controlled risk-request derivation."""

    def __init__(
        self,
        *,
        outbox: InMemoryOutboxRepository,
        config: WorkerConfig,
        trace: list[str] | None = None,
    ) -> None:
        self._outbox = outbox
        self._config = config
        self._processed: dict[str, tuple[str, EventEnvelope, bool]] = {}
        self.trace = trace if trace is not None else []
        self.failures_remaining = 0

    async def inspect(self, envelope: EventEnvelope) -> IdempotencyDisposition:
        key = _idempotency_key(envelope)
        existing = self._processed.get(key)
        if existing is None:
            return IdempotencyDisposition.NEW
        return (
            IdempotencyDisposition.DUPLICATE
            if existing[0] == _content_fingerprint(envelope)
            else IdempotencyDisposition.CONFLICT
        )

    async def process(
        self,
        envelope: EventEnvelope,
        *,
        late: bool,
    ) -> IdempotencyDisposition:
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise TransientProcessingError("durable_store_unavailable")
        disposition = await self.inspect(envelope)
        if disposition is not IdempotencyDisposition.NEW:
            return disposition
        output = self._risk_recompute_output(envelope)
        if output is not None:
            await self._outbox.add(output)
        key = _idempotency_key(envelope)
        self._processed[key] = (_content_fingerprint(envelope), envelope, late)
        self.trace.append(f"processor:persist:{envelope.event_id}")
        return IdempotencyDisposition.NEW

    @property
    def processed(self) -> tuple[EventEnvelope, ...]:
        return tuple(
            value[1] for _, value in sorted(self._processed.items(), key=lambda item: item[0])
        )

    def was_late(self, envelope: EventEnvelope) -> bool:
        return self._processed[_idempotency_key(envelope)][2]

    def _risk_recompute_output(self, envelope: EventEnvelope) -> OutboxEvent | None:
        if envelope.event_type is not EventType.PORTFOLIO_CHANGED_V1:
            return None
        payload = envelope.payload
        if not isinstance(payload, PortfolioChangedPayload):
            raise RuntimeError("validated portfolio event has unexpected payload type")
        source_key = _idempotency_key(envelope)
        request_id = uuid5(_NAMESPACE, f"risk-request:{source_key}")
        output_payload = RiskRecomputeRequestedPayload(
            request_id=request_id,
            portfolio_id=payload.portfolio_id,
            portfolio_version=payload.portfolio_version,
            valuation_at=payload.changed_at,
            methodology_version=self._config.methodology_version,
            price_dataset_hash=self._config.price_dataset_hash,
            reason=RecomputeReason.PORTFOLIO_CHANGED,
            is_synthetic=payload.is_synthetic,
        )
        output_envelope = EventEnvelope(
            event_id=uuid5(_NAMESPACE, f"risk-event:{source_key}"),
            event_type=EventType.RISK_RECOMPUTE_REQUESTED_V1,
            schema_version=1,
            occurred_at=envelope.received_at,
            received_at=envelope.received_at,
            producer=self._config.producer,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.event_id,
            payload=output_payload,
        )
        return OutboxEvent.pending(
            event_id=output_envelope.event_id,
            aggregate_type="portfolio",
            aggregate_id=payload.portfolio_id,
            event_type=output_envelope.event_type.value,
            schema_version=output_envelope.schema_version,
            producer=output_envelope.producer,
            idempotency_key=_idempotency_key(output_envelope),
            occurred_at=output_envelope.occurred_at,
            available_at=output_envelope.occurred_at,
            correlation_id=output_envelope.correlation_id,
            causation_id=output_envelope.causation_id,
            payload=output_payload.model_dump(mode="json"),
        )


class InMemoryDeadLetterSink:
    def __init__(self, *, trace: list[str] | None = None) -> None:
        self.records: list[DeadLetterRecord] = []
        self.failures_remaining = 0
        self.trace = trace if trace is not None else []

    async def put(self, record: DeadLetterRecord) -> None:
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise TransientProcessingError("dead_letter_store_unavailable")
        if all(existing.id != record.id for existing in self.records):
            self.records.append(record)
        self.trace.append(f"dlq:put:{record.id}")


class InMemoryOffsetCommitter:
    def __init__(self, *, trace: list[str] | None = None) -> None:
        self.committed: list[tuple[str, int, int]] = []
        self.failures_remaining = 0
        self.trace = trace if trace is not None else []

    async def commit(self, record: BrokerRecord) -> None:
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise BrokerUnavailableError
        self.committed.append(record.coordinate)
        self.trace.append(f"offset:commit:{record.topic}:{record.partition}:{record.offset}")


class InMemoryBrokerPublisher:
    def __init__(self, *, trace: list[str] | None = None) -> None:
        self.publications: list[Publication] = []
        self.failures_remaining = 0
        self.trace = trace if trace is not None else []

    async def publish(self, publication: Publication) -> None:
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            self.trace.append(f"broker:unavailable:{publication.topic}")
            raise BrokerUnavailableError
        self.publications.append(publication)
        self.trace.append(f"broker:publish:{publication.topic}")
