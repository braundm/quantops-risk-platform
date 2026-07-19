"""Deterministic broker-neutral streaming and transactional-outbox services."""

from quantops_stream_worker.config import RetryPolicy, TopicRoutes, WorkerConfig
from quantops_stream_worker.consumer import EventConsumer
from quantops_stream_worker.errors import (
    BrokerUnavailableError,
    IdempotencyConflictError,
    PermanentProcessingError,
    StreamWorkerError,
    TransientProcessingError,
)
from quantops_stream_worker.in_memory import (
    InMemoryBrokerPublisher,
    InMemoryDeadLetterSink,
    InMemoryDurableEventProcessor,
    InMemoryOffsetCommitter,
    InMemoryOutboxRepository,
)
from quantops_stream_worker.metrics import MetricsSnapshot, WorkerMetrics
from quantops_stream_worker.models import (
    BrokerRecord,
    DeadLetterRecord,
    DeliveryResult,
    DeliveryStatus,
    IdempotencyDisposition,
    OutboxPublishResult,
    OutboxPublishStatus,
    Publication,
)
from quantops_stream_worker.outbox_publisher import OutboxPublisher
from quantops_stream_worker.replay import ReplayService

__all__ = [
    "BrokerRecord",
    "BrokerUnavailableError",
    "DeadLetterRecord",
    "DeliveryResult",
    "DeliveryStatus",
    "EventConsumer",
    "IdempotencyConflictError",
    "IdempotencyDisposition",
    "InMemoryBrokerPublisher",
    "InMemoryDeadLetterSink",
    "InMemoryDurableEventProcessor",
    "InMemoryOffsetCommitter",
    "InMemoryOutboxRepository",
    "MetricsSnapshot",
    "OutboxPublishResult",
    "OutboxPublishStatus",
    "OutboxPublisher",
    "PermanentProcessingError",
    "Publication",
    "ReplayService",
    "RetryPolicy",
    "StreamWorkerError",
    "TopicRoutes",
    "TransientProcessingError",
    "WorkerConfig",
    "WorkerMetrics",
]

__version__ = "0.1.0"
