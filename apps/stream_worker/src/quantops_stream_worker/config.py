"""Validated immutable configuration with bounded workload and retry limits."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta

from quantops_contracts import EventType

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _name(value: str, label: str) -> str:
    normalized = value.strip()
    if _NAME.fullmatch(normalized) is None:
        raise ValueError(f"{label} must be a bounded broker-safe name")
    return normalized


def _positive_duration(value: timedelta, label: str, maximum: timedelta) -> timedelta:
    if value <= timedelta(0) or value > maximum:
        raise ValueError(f"{label} must be positive and at most {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Exponential retry schedule; services expose delays and never sleep."""

    max_attempts: int = 3
    initial_backoff_ms: int = 100
    multiplier: int = 2
    max_backoff_ms: int = 5_000

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")
        if not 1 <= self.initial_backoff_ms <= 60_000:
            raise ValueError("initial_backoff_ms must be between 1 and 60000")
        if not 1 <= self.multiplier <= 10:
            raise ValueError("multiplier must be between 1 and 10")
        if not self.initial_backoff_ms <= self.max_backoff_ms <= 300_000:
            raise ValueError("max_backoff_ms must bound the initial delay and be <= 300000")

    def delay_ms(self, retry_number: int) -> int:
        """Return the one-based retry delay without blocking."""

        if retry_number < 1 or retry_number >= self.max_attempts:
            raise ValueError("retry_number must identify a configured retry")
        delay = self.initial_backoff_ms
        for _ in range(retry_number - 1):
            delay *= self.multiplier
        return min(delay, self.max_backoff_ms)


@dataclass(frozen=True, slots=True)
class TopicRoutes:
    market_prices: str = "quantops.market.price-bars.v1"
    portfolio_changes: str = "quantops.portfolio.changes.v1"
    risk_recompute_requests: str = "quantops.risk.recompute-requests.v1"
    risk_snapshots: str = "quantops.risk.snapshots.v1"
    ai_brief_requests: str = "quantops.ai.brief-requests.v1"
    ai_briefs: str = "quantops.ai.briefs.v1"
    dead_letter: str = "quantops.dead-letter.v1"

    def __post_init__(self) -> None:
        for label in self.__slots__:
            object.__setattr__(self, label, _name(getattr(self, label), label))
        event_topics = self.input_topics
        if len(set(event_topics)) != len(event_topics):
            raise ValueError("event topics must be unique")
        if self.dead_letter in event_topics:
            raise ValueError("dead-letter topic must not be an input topic")

    @property
    def input_topics(self) -> tuple[str, ...]:
        return (
            self.market_prices,
            self.portfolio_changes,
            self.risk_recompute_requests,
            self.risk_snapshots,
            self.ai_brief_requests,
            self.ai_briefs,
        )

    def for_event(self, event_type: EventType) -> str:
        return {
            EventType.MARKET_PRICE_BAR_V1: self.market_prices,
            EventType.PORTFOLIO_CHANGED_V1: self.portfolio_changes,
            EventType.RISK_RECOMPUTE_REQUESTED_V1: self.risk_recompute_requests,
            EventType.RISK_SNAPSHOT_CREATED_V1: self.risk_snapshots,
            EventType.AI_BRIEF_REQUESTED_V1: self.ai_brief_requests,
            EventType.AI_BRIEF_CREATED_V1: self.ai_briefs,
        }[event_type]


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    worker_id: str = "stream-worker-demo-1"
    consumer_group: str = "quantops-risk-projection-v1"
    producer: str = "quantops.stream-worker"
    batch_size: int = 100
    max_event_age: timedelta = timedelta(days=7)
    max_out_of_order: timedelta = timedelta(minutes=5)
    methodology_version: str = "1.0.0"
    price_dataset_hash: str = "d" * 64
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    topics: TopicRoutes = field(default_factory=TopicRoutes)

    def __post_init__(self) -> None:
        object.__setattr__(self, "worker_id", _name(self.worker_id, "worker_id"))
        object.__setattr__(self, "consumer_group", _name(self.consumer_group, "consumer_group"))
        object.__setattr__(self, "producer", _name(self.producer, "producer"))
        if not 1 <= self.batch_size <= 1_000:
            raise ValueError("batch_size must be between 1 and 1000")
        _positive_duration(self.max_event_age, "max_event_age", timedelta(days=31))
        _positive_duration(
            self.max_out_of_order,
            "max_out_of_order",
            self.max_event_age,
        )
        if _NAME.fullmatch(self.methodology_version) is None:
            raise ValueError("methodology_version must be a bounded version identifier")
        if _SHA256.fullmatch(self.price_dataset_hash) is None:
            raise ValueError("price_dataset_hash must be a lowercase SHA-256 hex digest")
