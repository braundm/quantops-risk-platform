"""Configuration bounds, model invariants, namespace, and structural-port tests."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from quantops_stream_worker import (
    BrokerRecord,
    InMemoryBrokerPublisher,
    InMemoryDeadLetterSink,
    InMemoryDurableEventProcessor,
    InMemoryOffsetCommitter,
    InMemoryOutboxRepository,
    RetryPolicy,
    TopicRoutes,
    WorkerConfig,
)
from quantops_stream_worker.ports import (
    BrokerPublisher,
    DeadLetterSink,
    DurableEventProcessor,
    OffsetCommitter,
    OutboxRepository,
)

from .factories import AT


def test_retry_policy_is_bounded_and_does_not_perform_sleeping() -> None:
    policy = RetryPolicy(
        max_attempts=4,
        initial_backoff_ms=100,
        multiplier=10,
        max_backoff_ms=500,
    )

    assert tuple(policy.delay_ms(number) for number in (1, 2, 3)) == (100, 500, 500)
    with pytest.raises(ValueError, match="configured retry"):
        policy.delay_ms(4)


@pytest.mark.parametrize(
    "factory",
    (
        lambda: RetryPolicy(max_attempts=0),
        lambda: WorkerConfig(batch_size=0),
        lambda: WorkerConfig(max_event_age=timedelta(days=32)),
        lambda: WorkerConfig(max_out_of_order=timedelta(0)),
        lambda: WorkerConfig(price_dataset_hash="not-a-hash"),
        lambda: TopicRoutes(market_prices="unsafe topic"),
    ),
)
def test_invalid_configuration_fails_closed(factory: object) -> None:
    with pytest.raises(ValueError):
        factory()  # type: ignore[operator]


def test_in_memory_adapters_satisfy_framework_independent_ports() -> None:
    config = WorkerConfig()
    outbox = InMemoryOutboxRepository()
    processor = InMemoryDurableEventProcessor(outbox=outbox, config=config)

    assert isinstance(outbox, OutboxRepository)
    assert isinstance(processor, DurableEventProcessor)
    assert isinstance(InMemoryDeadLetterSink(), DeadLetterSink)
    assert isinstance(InMemoryOffsetCommitter(), OffsetCommitter)
    assert isinstance(InMemoryBrokerPublisher(), BrokerPublisher)


def test_broker_record_requires_bounded_coordinate_bytes_and_utc() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        BrokerRecord("topic", 0, -1, b"value", AT)
    with pytest.raises(TypeError, match="bytes"):
        BrokerRecord("topic", 0, 0, "value", AT)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="UTC"):
        BrokerRecord("topic", 0, 0, b"value", AT.replace(tzinfo=None))


def test_repository_discovery_namespace_markers_exist() -> None:
    package_root = Path(__file__).parents[1]

    assert (package_root / "__init__.py").is_file()
    assert (package_root / "tests" / "__init__.py").is_file()
    assert (package_root / "src" / "quantops_stream_worker" / "py.typed").is_file()
