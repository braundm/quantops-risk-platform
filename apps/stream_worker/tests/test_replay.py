"""Replay ordering, duplicate-coordinate, and partition-barrier tests."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from quantops_stream_worker import (
    DeliveryStatus,
    EventConsumer,
    InMemoryDeadLetterSink,
    InMemoryDurableEventProcessor,
    InMemoryOffsetCommitter,
    InMemoryOutboxRepository,
    ReplayService,
    WorkerConfig,
)

from .factories import AT, broker_record, portfolio_event


def _replay_stack() -> tuple[
    ReplayService,
    EventConsumer,
    InMemoryDurableEventProcessor,
    InMemoryOutboxRepository,
    InMemoryOffsetCommitter,
]:
    config = WorkerConfig()
    outbox = InMemoryOutboxRepository()
    processor = InMemoryDurableEventProcessor(outbox=outbox, config=config)
    committer = InMemoryOffsetCommitter()
    consumer = EventConsumer(
        processor=processor,
        dead_letters=InMemoryDeadLetterSink(),
        committer=committer,
        config=config,
    )
    return ReplayService(consumer), consumer, processor, outbox, committer


def test_replay_sorts_by_coordinate_and_is_idempotent_on_a_second_pass() -> None:
    replay, _, processor, outbox, committer = _replay_stack()
    records = tuple(
        broker_record(
            portfolio_event(
                version=version,
                occurred_at=AT + timedelta(minutes=offset),
                delivery_identity=f"v{version}",
            ),
            offset=offset,
        )
        for version, offset in ((4, 2), (2, 0), (3, 1))
    )

    first = asyncio.run(replay.replay(records))
    second = asyncio.run(replay.replay(tuple(reversed(records))))

    assert [item.coordinate[2] for item in first] == [0, 1, 2]
    assert [item.status for item in first] == [DeliveryStatus.PROCESSED] * 3
    assert [item.status for item in second] == [DeliveryStatus.DUPLICATE] * 3
    assert len(processor.processed) == 3
    assert len(outbox.events) == 3
    assert len(committer.committed) == 6


def test_uncommitted_offset_blocks_later_offsets_only_in_that_partition() -> None:
    replay, _, processor, _, committer = _replay_stack()
    committer.failures_remaining = 3
    records = (
        broker_record(portfolio_event(version=2), partition=0, offset=0),
        broker_record(
            portfolio_event(version=3, occurred_at=AT + timedelta(minutes=1)),
            partition=0,
            offset=1,
        ),
        broker_record(
            portfolio_event(version=4, occurred_at=AT + timedelta(minutes=2)),
            partition=1,
            offset=0,
        ),
    )

    results = asyncio.run(replay.replay(records))

    assert [item.status for item in results] == [
        DeliveryStatus.COMMIT_DEFERRED,
        DeliveryStatus.PARTITION_BLOCKED,
        DeliveryStatus.PROCESSED,
    ]
    assert len(processor.processed) == 2
    assert committer.committed == [(records[2].topic, 1, 0)]


def test_duplicate_broker_coordinates_are_rejected_before_replay() -> None:
    replay, _, processor, _, _ = _replay_stack()
    record = broker_record(portfolio_event(), offset=0)

    with pytest.raises(ValueError, match="duplicate broker coordinate"):
        asyncio.run(replay.replay((record, record)))

    assert processor.processed == ()
