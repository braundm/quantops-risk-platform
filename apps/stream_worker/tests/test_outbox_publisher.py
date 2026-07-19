"""Outbox envelope validation, acknowledgement, and outage state-machine tests."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta

from quantops_contracts import EventType, parse_event_json
from quantops_domain import OutboxStatus

from quantops_stream_worker import (
    InMemoryBrokerPublisher,
    InMemoryOutboxRepository,
    OutboxPublisher,
    OutboxPublishStatus,
    WorkerConfig,
)

from .factories import AT, risk_outbox


def _publisher(
    *,
    config: WorkerConfig | None = None,
) -> tuple[
    OutboxPublisher,
    InMemoryOutboxRepository,
    InMemoryBrokerPublisher,
    list[str],
]:
    trace: list[str] = []
    repository = InMemoryOutboxRepository(trace=trace)
    broker = InMemoryBrokerPublisher(trace=trace)
    service = OutboxPublisher(
        repository=repository,
        broker=broker,
        config=config or WorkerConfig(),
    )
    return service, repository, broker, trace


def test_valid_outbox_is_published_with_stable_key_then_marked_after_ack() -> None:
    service, repository, broker, trace = _publisher()
    event = risk_outbox()
    asyncio.run(repository.add(event))

    results = asyncio.run(service.publish_available(at=AT))

    assert results[0].status is OutboxPublishStatus.PUBLISHED
    saved = repository.get(event.id)
    assert saved.status is OutboxStatus.PUBLISHED
    assert saved.attempts == 1
    assert len(broker.publications) == 1
    publication = broker.publications[0]
    parsed = parse_event_json(publication.value)
    assert parsed.event_type is EventType.RISK_RECOMPUTE_REQUESTED_V1
    assert publication.key.decode() == event.idempotency_key
    assert parsed.idempotency_key == event.idempotency_key
    assert trace.index(f"broker:publish:{publication.topic}") < trace.index(
        f"outbox:save:{event.id}:published"
    )
    assert service.metrics.snapshot().processed == 1


def test_broker_outage_schedules_backoff_without_sleep_then_recovers() -> None:
    service, repository, broker, _ = _publisher()
    event = risk_outbox()
    asyncio.run(repository.add(event))
    broker.failures_remaining = 1

    failed = asyncio.run(service.publish_available(at=AT))[0]
    too_early = asyncio.run(service.publish_available(at=AT + timedelta(milliseconds=99)))
    recovered = asyncio.run(service.publish_available(at=failed.retry_at))[0]  # type: ignore[arg-type]

    assert failed.status is OutboxPublishStatus.RETRY_SCHEDULED
    assert failed.retry_at == AT + timedelta(milliseconds=100)
    assert too_early == ()
    assert recovered.status is OutboxPublishStatus.PUBLISHED
    assert repository.get(event.id).status is OutboxStatus.PUBLISHED
    assert repository.get(event.id).attempts == 2
    assert len(broker.publications) == 1
    snapshot = service.metrics.snapshot()
    assert snapshot.retries == 1
    assert snapshot.broker_outages == 1
    assert snapshot.dead_lettered == 0


def test_persistent_broker_outage_dead_letters_after_bounded_attempts() -> None:
    service, repository, broker, _ = _publisher()
    event = risk_outbox()
    asyncio.run(repository.add(event))
    broker.failures_remaining = 3

    first = asyncio.run(service.publish_available(at=AT))[0]
    assert first.retry_at is not None
    second = asyncio.run(service.publish_available(at=first.retry_at))[0]
    assert second.retry_at is not None
    third = asyncio.run(service.publish_available(at=second.retry_at))[0]

    assert first.status is OutboxPublishStatus.RETRY_SCHEDULED
    assert second.status is OutboxPublishStatus.RETRY_SCHEDULED
    assert third.status is OutboxPublishStatus.DEAD_LETTERED
    terminal = repository.get(event.id)
    assert terminal.status is OutboxStatus.DEAD_LETTER
    assert terminal.attempts == 3
    assert terminal.error_summary == "transient:broker_unavailable"
    assert broker.publications == []
    snapshot = service.metrics.snapshot()
    assert snapshot.retries == 2
    assert snapshot.broker_outages == 3
    assert snapshot.dead_lettered == 1


def test_permanently_invalid_outbox_is_never_sent_to_broker() -> None:
    service, repository, broker, _ = _publisher()
    event = replace(risk_outbox(), idempotency_key="wrong-but-safe")
    asyncio.run(repository.add(event))

    result = asyncio.run(service.publish_available(at=AT))[0]

    assert result.status is OutboxPublishStatus.DEAD_LETTERED
    assert repository.get(event.id).status is OutboxStatus.DEAD_LETTER
    assert repository.get(event.id).error_summary == "permanent:invalid_outbox_contract"
    assert broker.publications == []
    assert service.metrics.snapshot().rejected == 1


def test_claim_is_bounded_and_stably_ordered() -> None:
    config = WorkerConfig(batch_size=1)
    service, repository, broker, _ = _publisher(config=config)
    later = risk_outbox(occurred_at=AT + timedelta(seconds=1), identity="later")
    earlier = risk_outbox(occurred_at=AT, identity="earlier")
    asyncio.run(repository.add(later))
    asyncio.run(repository.add(earlier))

    first = asyncio.run(service.publish_available(at=AT + timedelta(seconds=2)))
    second = asyncio.run(service.publish_available(at=AT + timedelta(seconds=2)))

    assert [item.event_id for item in first + second] == [earlier.id, later.id]
    assert len(broker.publications) == 2
