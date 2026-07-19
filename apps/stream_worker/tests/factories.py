"""Typed deterministic event and broker-record factories."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from quantops_contracts import (
    EventEnvelope,
    EventType,
    PortfolioChangedPayload,
    PortfolioChangeKind,
    PriceBarPayload,
    RecomputeReason,
    RiskRecomputeRequestedPayload,
)
from quantops_domain import OutboxEvent

from quantops_stream_worker.config import WorkerConfig
from quantops_stream_worker.models import BrokerRecord

AT = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
PORTFOLIO_ID = UUID("11111111-1111-4111-8111-111111111111")
INSTRUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")
CORRELATION_ID = UUID("33333333-3333-4333-8333-333333333333")
NAMESPACE = UUID("44444444-4444-4444-8444-444444444444")


def portfolio_event(
    *,
    version: int = 2,
    occurred_at: datetime = AT,
    received_at: datetime | None = None,
    change_kind: PortfolioChangeKind = PortfolioChangeKind.POSITION_UPDATED,
    delivery_identity: str = "default",
) -> EventEnvelope:
    payload = PortfolioChangedPayload(
        change_id=uuid5(NAMESPACE, f"change:{version}:{change_kind.value}"),
        portfolio_id=PORTFOLIO_ID,
        portfolio_version=version,
        change_kind=change_kind,
        changed_at=occurred_at,
        changed_position_ids=(uuid5(NAMESPACE, f"position:{version}"),),
        base_currency="USD",
        is_synthetic=True,
    )
    return EventEnvelope(
        event_id=uuid5(NAMESPACE, f"event:{version}:{delivery_identity}"),
        event_type=EventType.PORTFOLIO_CHANGED_V1,
        schema_version=1,
        occurred_at=occurred_at,
        received_at=received_at or occurred_at + timedelta(seconds=1),
        producer="quantops.stream-tests",
        correlation_id=CORRELATION_ID,
        payload=payload,
    )


def price_event(
    *,
    day_identity: str,
    occurred_at: datetime,
    received_at: datetime | None = None,
) -> EventEnvelope:
    payload = PriceBarPayload(
        source_event_id=f"synthetic:{day_identity}",
        source="quantops.synthetic",
        instrument_id=INSTRUMENT_ID,
        symbol="QTECH",
        timestamp=occurred_at,
        open=Decimal("100"),
        high=Decimal("103"),
        low=Decimal("99"),
        close=Decimal("102"),
        volume=1_000,
        currency="USD",
        regime="normal",
        is_synthetic=True,
    )
    return EventEnvelope(
        event_id=uuid5(NAMESPACE, f"price-event:{day_identity}"),
        event_type=EventType.MARKET_PRICE_BAR_V1,
        schema_version=1,
        occurred_at=occurred_at,
        received_at=received_at or occurred_at + timedelta(seconds=1),
        producer="quantops.stream-tests",
        correlation_id=CORRELATION_ID,
        payload=payload,
    )


def broker_record(
    envelope: EventEnvelope,
    *,
    offset: int,
    partition: int = 0,
    topic: str | None = None,
    received_at: datetime | None = None,
    config: WorkerConfig | None = None,
) -> BrokerRecord:
    runtime = config or WorkerConfig()
    return BrokerRecord(
        topic=topic or runtime.topics.for_event(envelope.event_type),
        partition=partition,
        offset=offset,
        value=envelope.to_canonical_bytes(),
        received_at=received_at or envelope.received_at,
    )


def risk_outbox(*, occurred_at: datetime = AT, identity: str = "default") -> OutboxEvent:
    request_id = uuid5(NAMESPACE, f"standalone-risk-request:{identity}")
    payload = RiskRecomputeRequestedPayload(
        request_id=request_id,
        portfolio_id=PORTFOLIO_ID,
        portfolio_version=2,
        valuation_at=occurred_at,
        methodology_version="1.0.0",
        price_dataset_hash="a" * 64,
        reason=RecomputeReason.REPLAY_CHECKPOINT,
        is_synthetic=True,
    )
    envelope = EventEnvelope(
        event_id=uuid5(NAMESPACE, f"standalone-risk-event:{identity}"),
        event_type=EventType.RISK_RECOMPUTE_REQUESTED_V1,
        schema_version=1,
        occurred_at=occurred_at,
        received_at=occurred_at,
        producer="quantops.stream-tests",
        correlation_id=CORRELATION_ID,
        payload=payload,
    )
    assert envelope.idempotency_key is not None
    return OutboxEvent.pending(
        event_id=envelope.event_id,
        aggregate_type="portfolio",
        aggregate_id=PORTFOLIO_ID,
        event_type=envelope.event_type.value,
        schema_version=1,
        producer=envelope.producer,
        idempotency_key=envelope.idempotency_key,
        occurred_at=occurred_at,
        correlation_id=envelope.correlation_id,
        payload=payload.model_dump(mode="json"),
    )
