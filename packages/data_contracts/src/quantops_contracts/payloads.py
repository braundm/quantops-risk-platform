"""Pydantic v2 payload schemas for every supported v1 event."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from quantops_contracts._base import (
    BoundedIdentifier,
    BriefContent,
    ContractModel,
    CurrencyCode,
    EvidenceId,
    InstrumentSymbol,
    MethodologyVersion,
    NonNegativeDecimal,
    NonNilUuid,
    PositiveDecimal,
    QuestionText,
    Sha256Hex,
    UtcDateTime,
)


class EventPayload(ContractModel):
    """Base interface for stable payload idempotency identities."""

    def idempotency_parts(self) -> tuple[str, ...]:
        raise NotImplementedError


class PortfolioChangeKind(StrEnum):
    CREATED = "created"
    POSITION_ADDED = "position_added"
    POSITION_UPDATED = "position_updated"
    POSITION_REMOVED = "position_removed"
    METADATA_UPDATED = "metadata_updated"


class RecomputeReason(StrEnum):
    PORTFOLIO_CHANGED = "portfolio_changed"
    PRICE_WATERMARK_ADVANCED = "price_watermark_advanced"
    MANUAL_DEMO_REQUEST = "manual_demo_request"
    REPLAY_CHECKPOINT = "replay_checkpoint"


class RiskQualityStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    STALE = "stale"
    INSUFFICIENT = "insufficient"


class BriefStatus(StrEnum):
    COMPLETED = "completed"
    REFUSED = "refused"
    FALLBACK = "fallback"


class PriceBarPayload(EventPayload):
    """A validated synthetic or explicitly non-synthetic daily price bar."""

    source_event_id: BoundedIdentifier
    source: BoundedIdentifier
    instrument_id: NonNilUuid
    symbol: InstrumentSymbol
    timestamp: UtcDateTime
    interval: Literal["1d"] = "1d"
    open: PositiveDecimal
    high: PositiveDecimal
    low: PositiveDecimal
    close: PositiveDecimal
    volume: Annotated[int, Field(ge=0, le=9_223_372_036_854_775_807)]
    currency: CurrencyCode
    regime: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    is_synthetic: bool

    @model_validator(mode="after")
    def validate_ohlc(self) -> Self:
        if self.high < max(self.open, self.close):
            raise ValueError("high must be greater than or equal to max(open, close)")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be less than or equal to min(open, close)")
        return self

    def idempotency_parts(self) -> tuple[str, ...]:
        return self.source, self.source_event_id


class PortfolioChangedPayload(EventPayload):
    """Immutable notification that a portfolio aggregate reached a new version."""

    change_id: NonNilUuid
    portfolio_id: NonNilUuid
    portfolio_version: Annotated[int, Field(ge=1)]
    change_kind: PortfolioChangeKind
    changed_at: UtcDateTime
    changed_position_ids: Annotated[tuple[NonNilUuid, ...], Field(max_length=1_000)] = ()
    base_currency: CurrencyCode
    is_synthetic: bool

    @model_validator(mode="after")
    def unique_positions(self) -> Self:
        if len(set(self.changed_position_ids)) != len(self.changed_position_ids):
            raise ValueError("changed_position_ids must be unique")
        return self

    def idempotency_parts(self) -> tuple[str, ...]:
        return str(self.portfolio_id), str(self.portfolio_version)


class RiskRecomputeRequestedPayload(EventPayload):
    """A bounded request for deterministic risk recomputation."""

    request_id: NonNilUuid
    portfolio_id: NonNilUuid
    portfolio_version: Annotated[int, Field(ge=1)]
    valuation_at: UtcDateTime
    methodology_version: MethodologyVersion
    price_dataset_hash: Sha256Hex
    reason: RecomputeReason
    is_synthetic: bool

    def idempotency_parts(self) -> tuple[str, ...]:
        return (str(self.request_id),)


class RiskSnapshotCreatedPayload(EventPayload):
    """Summary of an immutable authoritative risk snapshot."""

    snapshot_id: NonNilUuid
    portfolio_id: NonNilUuid
    portfolio_version: Annotated[int, Field(ge=1)]
    as_of: UtcDateTime
    methodology_version: MethodologyVersion
    base_currency: CurrencyCode
    portfolio_value: PositiveDecimal
    value_at_risk_95: NonNegativeDecimal
    expected_shortfall_95: NonNegativeDecimal
    annualized_volatility: NonNegativeDecimal
    quality_status: RiskQualityStatus
    evidence_manifest_hash: Sha256Hex
    is_synthetic: bool

    @model_validator(mode="after")
    def validate_tail_metrics(self) -> Self:
        if self.expected_shortfall_95 < self.value_at_risk_95:
            raise ValueError("expected_shortfall_95 must be >= value_at_risk_95")
        return self

    def idempotency_parts(self) -> tuple[str, ...]:
        return (str(self.snapshot_id),)


class AiBriefRequestedPayload(EventPayload):
    """Read-only request for a brief grounded in explicit evidence IDs."""

    request_id: NonNilUuid
    snapshot_id: NonNilUuid
    requested_at: UtcDateTime
    question: QuestionText
    evidence_ids: Annotated[tuple[EvidenceId, ...], Field(min_length=1, max_length=200)]
    is_synthetic: bool

    @model_validator(mode="after")
    def unique_evidence(self) -> Self:
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")
        return self

    def idempotency_parts(self) -> tuple[str, ...]:
        return (str(self.request_id),)


class AiBriefCreatedPayload(EventPayload):
    """Bounded generated brief result with verifiable citations."""

    brief_id: NonNilUuid
    request_id: NonNilUuid
    snapshot_id: NonNilUuid
    created_at: UtcDateTime
    provider: BoundedIdentifier
    status: BriefStatus
    content: BriefContent
    cited_evidence_ids: Annotated[tuple[EvidenceId, ...], Field(max_length=200)] = ()
    content_hash: Sha256Hex
    is_synthetic: bool

    @model_validator(mode="after")
    def validate_citations(self) -> Self:
        if len(set(self.cited_evidence_ids)) != len(self.cited_evidence_ids):
            raise ValueError("cited_evidence_ids must be unique")
        if self.status is BriefStatus.COMPLETED and not self.cited_evidence_ids:
            raise ValueError("completed briefs require at least one cited evidence ID")
        return self

    def idempotency_parts(self) -> tuple[str, ...]:
        return (str(self.brief_id),)


type Payload = (
    PriceBarPayload
    | PortfolioChangedPayload
    | RiskRecomputeRequestedPayload
    | RiskSnapshotCreatedPayload
    | AiBriefRequestedPayload
    | AiBriefCreatedPayload
)
