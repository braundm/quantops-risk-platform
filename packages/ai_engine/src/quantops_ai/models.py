"""Immutable schemas for scoped evidence, requests, and grounded risk briefs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Identifier = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z][A-Z0-9_-]{1,63}$", strip_whitespace=True),
]
EvidenceId = Annotated[
    str,
    StringConstraints(
        pattern=r"^(RISK|PRICE|QUALITY|DOC|SCENARIO|METHOD|MODEL)-[A-Z0-9_-]{2,80}$",
        strip_whitespace=True,
    ),
]


class FrozenModel(BaseModel):
    """Strict immutable Pydantic base used at every provider and tool boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class EvidenceKind(StrEnum):
    RISK = "risk"
    PRICE = "price"
    QUALITY = "quality"
    DOCUMENT = "document"
    SCENARIO = "scenario"
    METHODOLOGY = "methodology"
    MODEL = "model"


class CanonicalUnit(StrEnum):
    RATIO = "ratio"
    PERCENT = "percent"
    BASIS_POINTS = "basis_points"
    USD = "usd"
    DAYS = "days"
    COUNT = "count"


class EvidenceItem(FrozenModel):
    evidence_id: EvidenceId
    kind: EvidenceKind
    portfolio_id: Identifier
    source_timestamp: AwareDatetime
    title: Annotated[str, Field(min_length=1, max_length=200)]
    content: Annotated[str, Field(min_length=1, max_length=4_000)]
    metric_name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{1,79}")] | None = None
    canonical_value: Decimal | None = None
    canonical_unit: CanonicalUnit | None = None
    display_precision: Annotated[int, Field(ge=0, le=6)] = 2
    document_id: Identifier | None = None
    section: Annotated[str, Field(max_length=120)] | None = None
    source_url: Annotated[str, Field(pattern=r"^https://", max_length=500)] | None = None
    publication_date: date | None = None
    synthetic: bool = True

    @model_validator(mode="after")
    def validate_metric_fields(self) -> Self:
        numeric_fields = (self.canonical_value, self.canonical_unit)
        if self.metric_name is None and any(value is not None for value in numeric_fields):
            raise ValueError("numeric evidence requires metric_name")
        if self.metric_name is not None and any(value is None for value in numeric_fields):
            raise ValueError("metric evidence requires canonical value and unit")
        if self.kind is EvidenceKind.DOCUMENT and (
            self.document_id is None or self.source_url is None or self.publication_date is None
        ):
            raise ValueError(
                "document evidence requires document_id, source_url, and publication_date"
            )
        return self


class EvidencePackage(FrozenModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    package_id: Identifier
    portfolio_id: Identifier
    items: Annotated[tuple[EvidenceItem, ...], Field(min_length=1, max_length=32)]
    created_at: AwareDatetime
    max_content_characters: Annotated[int, Field(ge=1, le=64_000)] = 24_000

    @model_validator(mode="after")
    def validate_scope_and_size(self) -> Self:
        ids = [item.evidence_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate evidence IDs are forbidden")
        if any(item.portfolio_id != self.portfolio_id for item in self.items):
            raise ValueError("cross-portfolio evidence is forbidden")
        if sum(len(item.content) for item in self.items) > self.max_content_characters:
            raise ValueError("evidence package exceeds content budget")
        return self

    def by_id(self) -> dict[str, EvidenceItem]:
        return {item.evidence_id: item for item in self.items}

    def metric_items(self, metric_name: str) -> tuple[EvidenceItem, ...]:
        return tuple(item for item in self.items if item.metric_name == metric_name)


class AnalysisRequest(FrozenModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    request_id: Identifier
    portfolio_id: Identifier
    question: Annotated[str, Field(min_length=1, max_length=1_000)]
    snapshot_ids: Annotated[tuple[Identifier, ...], Field(max_length=2)] = ()
    scenario_run_id: Identifier | None = None
    portfolio_name: Annotated[str, Field(max_length=200)] | None = None
    document_query: Annotated[str, Field(max_length=300)] | None = None

    @field_validator("snapshot_ids")
    @classmethod
    def unique_snapshots(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("snapshot IDs must be unique")
        return value


class ClaimType(StrEnum):
    METRIC = "metric"
    DOCUMENT = "document"
    QUALITY = "quality"
    SCENARIO = "scenario"
    METHODOLOGY = "methodology"
    GENERAL = "general"


class MainFactor(FrozenModel):
    statement: Annotated[str, Field(min_length=1, max_length=600)]
    claim_type: ClaimType = ClaimType.GENERAL
    metric: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{1,79}")] | None = None
    value: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    unit: CanonicalUnit | None = None
    evidence_ids: Annotated[tuple[EvidenceId, ...], Field(min_length=1, max_length=8)]

    @model_validator(mode="after")
    def validate_numeric_claim_shape(self) -> Self:
        numeric = (self.metric, self.value, self.unit)
        if any(value is not None for value in numeric) and any(value is None for value in numeric):
            raise ValueError("metric, value, and unit must be supplied together")
        if self.metric is not None and self.claim_type is not ClaimType.METRIC:
            raise ValueError("numeric claims must use claim_type=metric")
        return self


class Uncertainty(FrozenModel):
    statement: Annotated[str, Field(min_length=1, max_length=500)]
    evidence_ids: Annotated[tuple[EvidenceId, ...], Field(min_length=1, max_length=8)]


class RefusalDetail(FrozenModel):
    category: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,63}")]
    safe_alternative: Annotated[str, Field(min_length=1, max_length=400)]


class RiskBrief(FrozenModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    answer_type: Literal["risk_explanation", "comparison", "document_summary", "refusal"]
    summary: Annotated[str, Field(min_length=1, max_length=1_200)]
    main_factors: Annotated[tuple[MainFactor, ...], Field(max_length=12)] = ()
    uncertainties: Annotated[tuple[Uncertainty, ...], Field(max_length=8)] = ()
    recommended_checks: Annotated[tuple[str, ...], Field(max_length=8)] = ()
    limitations: Annotated[tuple[str, ...], Field(max_length=8)] = ()
    refusal: RefusalDetail | None = None

    @model_validator(mode="after")
    def validate_refusal_shape(self) -> Self:
        if self.answer_type == "refusal":
            if self.refusal is None or self.main_factors or self.uncertainties:
                raise ValueError("refusal output requires refusal detail and no factual claims")
        elif self.refusal is not None:
            raise ValueError("non-refusal output cannot contain refusal detail")
        return self


def utc_timestamp(value: datetime) -> datetime:
    """Validate a timestamp used by non-Pydantic helpers."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value
