"""Consumer idempotency, policy, durability ordering, retry, and DLQ tests."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import timedelta

from quantops_contracts import (
    PortfolioChangedPayload,
    PortfolioChangeKind,
    RiskRecomputeRequestedPayload,
)

from quantops_stream_worker import (
    BrokerRecord,
    DeliveryStatus,
    EventConsumer,
    InMemoryDeadLetterSink,
    InMemoryDurableEventProcessor,
    InMemoryOffsetCommitter,
    InMemoryOutboxRepository,
    RetryPolicy,
    WorkerConfig,
)

from .factories import AT, broker_record, portfolio_event, price_event


def _stack(
    config: WorkerConfig | None = None,
) -> tuple[
    EventConsumer,
    InMemoryDurableEventProcessor,
    InMemoryOutboxRepository,
    InMemoryDeadLetterSink,
    InMemoryOffsetCommitter,
    list[str],
]:
    runtime = config or WorkerConfig()
    trace: list[str] = []
    outbox = InMemoryOutboxRepository(trace=trace)
    processor = InMemoryDurableEventProcessor(outbox=outbox, config=runtime, trace=trace)
    dead_letters = InMemoryDeadLetterSink(trace=trace)
    committer = InMemoryOffsetCommitter(trace=trace)
    consumer = EventConsumer(
        processor=processor,
        dead_letters=dead_letters,
        committer=committer,
        config=runtime,
    )
    return consumer, processor, outbox, dead_letters, committer, trace


def test_portfolio_event_is_durable_before_commit_and_emits_one_controlled_request() -> None:
    consumer, processor, outbox, dead_letters, committer, trace = _stack()
    envelope = portfolio_event()
    record = broker_record(envelope, offset=10)

    result = asyncio.run(consumer.consume(record))

    assert result.status is DeliveryStatus.PROCESSED
    assert len(processor.processed) == 1
    assert len(outbox.events) == 1
    assert dead_letters.records == []
    assert committer.committed == [record.coordinate]
    output = outbox.events[0]
    payload = RiskRecomputeRequestedPayload.model_validate(output.payload)
    assert isinstance(envelope.payload, PortfolioChangedPayload)
    assert payload.portfolio_id == envelope.payload.portfolio_id
    assert payload.portfolio_version == 2
    assert payload.methodology_version == "1.0.0"
    assert payload.price_dataset_hash == "d" * 64
    assert output.correlation_id == envelope.correlation_id
    assert output.causation_id == envelope.event_id
    assert trace.index(f"outbox:add:{output.id}") < trace.index(
        f"processor:persist:{envelope.event_id}"
    )
    assert trace.index(f"processor:persist:{envelope.event_id}") < next(
        index for index, value in enumerate(trace) if value.startswith("offset:commit:")
    )
    assert consumer.metrics.snapshot().processed == 1
    assert consumer.metrics.snapshot().commits == 1


def test_delivery_metadata_changes_do_not_break_stable_duplicate_detection() -> None:
    consumer, processor, outbox, _, committer, _ = _stack()
    first = portfolio_event(delivery_identity="first")
    redelivery = portfolio_event(
        delivery_identity="redelivery",
        received_at=AT + timedelta(seconds=30),
    )

    first_result = asyncio.run(consumer.consume(broker_record(first, offset=0)))
    duplicate_result = asyncio.run(
        consumer.consume(
            broker_record(
                redelivery,
                offset=1,
                received_at=AT + timedelta(seconds=30),
            )
        )
    )

    assert first_result.status is DeliveryStatus.PROCESSED
    assert duplicate_result.status is DeliveryStatus.DUPLICATE
    assert len(processor.processed) == 1
    assert len(outbox.events) == 1
    assert len(committer.committed) == 2
    assert consumer.metrics.snapshot().duplicates == 1


def test_same_identity_with_different_payload_is_dead_lettered_not_overwritten() -> None:
    consumer, processor, outbox, dead_letters, committer, _ = _stack()
    accepted = portfolio_event(change_kind=PortfolioChangeKind.POSITION_UPDATED)
    conflicting = portfolio_event(
        change_kind=PortfolioChangeKind.METADATA_UPDATED,
        delivery_identity="conflict",
    )

    asyncio.run(consumer.consume(broker_record(accepted, offset=0)))
    result = asyncio.run(consumer.consume(broker_record(conflicting, offset=1)))

    assert result.status is DeliveryStatus.REJECTED_DEAD_LETTERED
    assert len(processor.processed) == 1
    assert len(outbox.events) == 1
    assert committer.committed[-1][2] == 1
    assert dead_letters.records[0].failure_code == "idempotency_conflict"
    assert dead_letters.records[0].idempotency_key_sha256 is not None
    assert consumer.metrics.snapshot().rejected == 1
    assert consumer.metrics.snapshot().dead_lettered == 1


def test_invalid_envelope_dlq_metadata_never_contains_raw_secret_or_exception_text() -> None:
    consumer, _, _, dead_letters, committer, _ = _stack()
    raw = b'{"event_type":"unknown.v1","schema_version":1,"api_key":"super-secret"}'
    record = BrokerRecord(
        topic=WorkerConfig().topics.portfolio_changes,
        partition=0,
        offset=7,
        value=raw,
        received_at=AT,
    )

    result = asyncio.run(consumer.consume(record))

    assert result.status is DeliveryStatus.REJECTED_DEAD_LETTERED
    assert committer.committed == [record.coordinate]
    assert len(dead_letters.records) == 1
    metadata = asdict(dead_letters.records[0])
    rendered = repr(metadata)
    assert dead_letters.records[0].failure_code == "unsupported_event_type"
    assert "super-secret" not in rendered
    assert "api_key" not in rendered
    assert "unknown.v1" not in rendered
    assert set(metadata) == {
        "id",
        "source_topic",
        "source_partition",
        "source_offset",
        "source_sha256",
        "source_size_bytes",
        "failure_code",
        "failure_kind",
        "created_at",
        "attempts",
        "event_id",
        "idempotency_key_sha256",
    }


def test_bounded_out_of_order_event_is_processed_but_excessive_lateness_is_dlq() -> None:
    config = WorkerConfig(max_out_of_order=timedelta(minutes=5))
    consumer, processor, _, dead_letters, committer, _ = _stack(config)
    newest = price_event(
        day_identity="newest",
        occurred_at=AT + timedelta(minutes=10),
        received_at=AT + timedelta(minutes=10, seconds=1),
    )
    within_bound = price_event(
        day_identity="within",
        occurred_at=AT + timedelta(minutes=8),
        received_at=AT + timedelta(minutes=11),
    )
    too_late = price_event(
        day_identity="too-late",
        occurred_at=AT,
        received_at=AT + timedelta(minutes=12),
    )

    first = asyncio.run(
        consumer.consume(
            broker_record(newest, offset=0, received_at=newest.received_at, config=config)
        )
    )
    late = asyncio.run(
        consumer.consume(
            broker_record(
                within_bound,
                offset=1,
                received_at=within_bound.received_at,
                config=config,
            )
        )
    )
    rejected = asyncio.run(
        consumer.consume(
            broker_record(
                too_late,
                offset=2,
                received_at=too_late.received_at,
                config=config,
            )
        )
    )

    assert first.status is DeliveryStatus.PROCESSED
    assert late.status is DeliveryStatus.PROCESSED_LATE
    assert rejected.status is DeliveryStatus.REJECTED_DEAD_LETTERED
    assert len(processor.processed) == 2
    assert processor.was_late(within_bound) is True
    assert dead_letters.records[0].failure_code == "late_beyond_policy"
    assert len(committer.committed) == 3
    assert consumer.metrics.snapshot().late == 1


def test_first_event_outside_age_bound_and_future_event_are_policy_rejected() -> None:
    config = WorkerConfig(max_event_age=timedelta(hours=1))
    consumer, processor, _, dead_letters, committer, _ = _stack(config)
    old = price_event(
        day_identity="old",
        occurred_at=AT,
        received_at=AT + timedelta(hours=2),
    )
    future = price_event(
        day_identity="future",
        occurred_at=AT + timedelta(hours=3),
        received_at=AT + timedelta(hours=3, seconds=1),
    )

    old_result = asyncio.run(
        consumer.consume(
            broker_record(
                old,
                offset=0,
                received_at=old.received_at,
                config=config,
            )
        )
    )
    future_result = asyncio.run(
        consumer.consume(
            broker_record(
                future,
                offset=1,
                received_at=AT + timedelta(hours=2, minutes=59),
                config=config,
            )
        )
    )

    assert old_result.status is DeliveryStatus.REJECTED_DEAD_LETTERED
    assert future_result.status is DeliveryStatus.REJECTED_DEAD_LETTERED
    assert processor.processed == ()
    assert [item.failure_code for item in dead_letters.records] == [
        "event_too_old",
        "future_event",
    ]
    assert len(committer.committed) == 2


def test_transient_processing_retries_without_sleep_then_commits() -> None:
    config = WorkerConfig(
        retry=RetryPolicy(
            max_attempts=3,
            initial_backoff_ms=25,
            multiplier=2,
            max_backoff_ms=100,
        )
    )
    consumer, processor, _, _, committer, _ = _stack(config)
    processor.failures_remaining = 2
    record = broker_record(portfolio_event(), offset=0, config=config)

    result = asyncio.run(consumer.consume(record))

    assert result.status is DeliveryStatus.PROCESSED
    assert result.retry_delays_ms == (25, 50)
    assert len(processor.processed) == 1
    assert committer.committed == [record.coordinate]
    assert consumer.metrics.snapshot().retries == 2


def test_exhausted_transient_processing_neither_commits_nor_dead_letters() -> None:
    consumer, processor, _, dead_letters, committer, _ = _stack()
    processor.failures_remaining = 3
    record = broker_record(portfolio_event(), offset=0)

    result = asyncio.run(consumer.consume(record))

    assert result.status is DeliveryStatus.RETRY_EXHAUSTED
    assert result.retry_delays_ms == (100, 200)
    assert processor.processed == ()
    assert dead_letters.records == []
    assert committer.committed == []
    assert consumer.metrics.snapshot().retries == 2


def test_commit_outage_leaves_durable_event_uncommitted_then_redelivery_commits_duplicate() -> None:
    consumer, processor, outbox, _, committer, _ = _stack()
    committer.failures_remaining = 3
    envelope = portfolio_event()
    first_record = broker_record(envelope, offset=0)

    first = asyncio.run(consumer.consume(first_record))

    assert first.status is DeliveryStatus.COMMIT_DEFERRED
    assert len(processor.processed) == 1
    assert len(outbox.events) == 1
    assert committer.committed == []

    redelivery = asyncio.run(consumer.consume(broker_record(envelope, offset=0)))

    assert redelivery.status is DeliveryStatus.DUPLICATE
    assert committer.committed == [first_record.coordinate]
    assert consumer.metrics.snapshot().processed == 1
    assert consumer.metrics.snapshot().duplicates == 1
    assert consumer.metrics.snapshot().broker_outages == 3


def test_dead_letter_store_outage_prevents_offset_commit_until_durable() -> None:
    consumer, _, _, dead_letters, committer, _ = _stack()
    dead_letters.failures_remaining = 3
    record = BrokerRecord(
        topic=WorkerConfig().topics.portfolio_changes,
        partition=0,
        offset=4,
        value=b"not-json",
        received_at=AT,
    )

    deferred = asyncio.run(consumer.consume(record))

    assert deferred.status is DeliveryStatus.RETRY_EXHAUSTED
    assert dead_letters.records == []
    assert committer.committed == []

    terminal = asyncio.run(consumer.consume(record))

    assert terminal.status is DeliveryStatus.REJECTED_DEAD_LETTERED
    assert len(dead_letters.records) == 1
    assert committer.committed == [record.coordinate]


def test_valid_event_on_wrong_topic_is_policy_rejected_and_committed_after_dlq() -> None:
    consumer, processor, _, dead_letters, committer, _ = _stack()
    envelope = portfolio_event()
    record = broker_record(
        envelope,
        offset=1,
        topic=WorkerConfig().topics.market_prices,
    )

    result = asyncio.run(consumer.consume(record))

    assert result.status is DeliveryStatus.REJECTED_DEAD_LETTERED
    assert processor.processed == ()
    assert dead_letters.records[0].failure_code == "event_topic_mismatch"
    assert committer.committed == [record.coordinate]
