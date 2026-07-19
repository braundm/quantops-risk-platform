"""Deterministic valid contract examples shared by tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from quantops_contracts import (
    AiBriefCreatedPayload,
    AiBriefRequestedPayload,
    BriefStatus,
    EventEnvelope,
    EventType,
    Payload,
    PortfolioChangedPayload,
    PortfolioChangeKind,
    PriceBarPayload,
    RecomputeReason,
    RiskQualityStatus,
    RiskRecomputeRequestedPayload,
    RiskSnapshotCreatedPayload,
)

EVENT_ID = UUID("10000000-0000-4000-8000-000000000001")
CORRELATION_ID = UUID("20000000-0000-4000-8000-000000000001")
PORTFOLIO_ID = UUID("30000000-0000-4000-8000-000000000001")
INSTRUMENT_ID = UUID("40000000-0000-4000-8000-000000000001")
REQUEST_ID = UUID("50000000-0000-4000-8000-000000000001")
SNAPSHOT_ID = UUID("60000000-0000-4000-8000-000000000001")
BRIEF_ID = UUID("70000000-0000-4000-8000-000000000001")
CHANGE_ID = UUID("80000000-0000-4000-8000-000000000001")
POSITION_ID = UUID("90000000-0000-4000-8000-000000000001")
AT = datetime(2024, 3, 4, 21, 0, tzinfo=UTC)
HASH = "a" * 64


def price_bar(**changes: object) -> PriceBarPayload:
    values: dict[str, object] = {
        "source_event_id": "synthetic:1.0.0:QTECH:2024-03-04",
        "source": "quantops.synthetic",
        "instrument_id": INSTRUMENT_ID,
        "symbol": "QTECH",
        "timestamp": AT,
        "open": Decimal("100.100000"),
        "high": Decimal("103.000000"),
        "low": Decimal("99.500000"),
        "close": Decimal("102.400000"),
        "volume": 1_500_000,
        "currency": "USD",
        "regime": "normal",
        "is_synthetic": True,
    }
    values.update(changes)
    return PriceBarPayload.model_validate(values)


def portfolio_changed() -> PortfolioChangedPayload:
    return PortfolioChangedPayload(
        change_id=CHANGE_ID,
        portfolio_id=PORTFOLIO_ID,
        portfolio_version=2,
        change_kind=PortfolioChangeKind.POSITION_UPDATED,
        changed_at=AT,
        changed_position_ids=(POSITION_ID,),
        base_currency="USD",
        is_synthetic=True,
    )


def recompute_requested() -> RiskRecomputeRequestedPayload:
    return RiskRecomputeRequestedPayload(
        request_id=REQUEST_ID,
        portfolio_id=PORTFOLIO_ID,
        portfolio_version=2,
        valuation_at=AT,
        methodology_version="historical-v1",
        price_dataset_hash=HASH,
        reason=RecomputeReason.PORTFOLIO_CHANGED,
        is_synthetic=True,
    )


def snapshot_created() -> RiskSnapshotCreatedPayload:
    return RiskSnapshotCreatedPayload(
        snapshot_id=SNAPSHOT_ID,
        portfolio_id=PORTFOLIO_ID,
        portfolio_version=2,
        as_of=AT,
        methodology_version="historical-v1",
        base_currency="USD",
        portfolio_value=Decimal("1000000.00"),
        value_at_risk_95=Decimal("25000.50"),
        expected_shortfall_95=Decimal("31000.75"),
        annualized_volatility=Decimal("0.184200"),
        quality_status=RiskQualityStatus.COMPLETE,
        evidence_manifest_hash=HASH,
        is_synthetic=True,
    )


def brief_requested() -> AiBriefRequestedPayload:
    return AiBriefRequestedPayload(
        request_id=REQUEST_ID,
        snapshot_id=SNAPSHOT_ID,
        requested_at=AT,
        question="Why did synthetic portfolio risk increase?",
        evidence_ids=("risk:snapshot:6000", "quality:run:792e"),
        is_synthetic=True,
    )


def brief_created(**changes: object) -> AiBriefCreatedPayload:
    content = str(changes.pop("content", "Synthetic risk increased during the shock regime."))
    values: dict[str, object] = {
        "brief_id": BRIEF_ID,
        "request_id": REQUEST_ID,
        "snapshot_id": SNAPSHOT_ID,
        "created_at": AT,
        "provider": "deterministic-template",
        "status": BriefStatus.COMPLETED,
        "content": content,
        "cited_evidence_ids": ("risk:snapshot:6000",),
        "content_hash": hashlib.sha256(content.encode()).hexdigest(),
        "is_synthetic": True,
    }
    values.update(changes)
    return AiBriefCreatedPayload.model_validate(values)


def event_cases() -> tuple[tuple[EventType, Payload, datetime], ...]:
    return (
        (EventType.MARKET_PRICE_BAR_V1, price_bar(), AT),
        (EventType.PORTFOLIO_CHANGED_V1, portfolio_changed(), AT),
        (
            EventType.RISK_RECOMPUTE_REQUESTED_V1,
            recompute_requested(),
            AT + timedelta(minutes=1),
        ),
        (EventType.RISK_SNAPSHOT_CREATED_V1, snapshot_created(), AT + timedelta(minutes=2)),
        (EventType.AI_BRIEF_REQUESTED_V1, brief_requested(), AT),
        (EventType.AI_BRIEF_CREATED_V1, brief_created(), AT),
    )


def envelope(
    event_type: EventType,
    payload: Payload,
    occurred_at: datetime,
    *,
    event_id: UUID = EVENT_ID,
    correlation_id: UUID = CORRELATION_ID,
    received_delay: timedelta = timedelta(seconds=5),
    idempotency_key: str | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        schema_version=1,
        occurred_at=occurred_at,
        received_at=occurred_at + received_delay,
        producer="quantops-contract-tests",
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        payload=payload,
    )
