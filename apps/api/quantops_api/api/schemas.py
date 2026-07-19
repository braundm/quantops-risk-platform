"""Explicit public request and response contracts for the versioned API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractModel(BaseModel):
    """Immutable response model that rejects accidental transport fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProblemIssue(ContractModel):
    location: tuple[str | int, ...]
    message: str
    code: str


class ProblemDetails(ContractModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    request_id: str
    correlation_id: str
    errors: tuple[ProblemIssue, ...] | None = None


class HealthResponse(ContractModel):
    status: Literal["ok"] = "ok"
    service: Literal["quantops-api"] = "quantops-api"
    version: str


class ReadinessResponse(ContractModel):
    status: Literal["ready", "degraded"]
    service: Literal["quantops-api"] = "quantops-api"
    version: str
    mode: Literal["deterministic-demo", "infrastructure-required"]
    checks: dict[str, Literal["ready", "not_configured"]]


class VersionResponse(ContractModel):
    name: Literal["QuantOps"] = "QuantOps"
    version: str
    methodology_version: str


class Page[ItemT](ContractModel):
    items: tuple[ItemT, ...]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None


class InstrumentResponse(ContractModel):
    id: UUID
    source: str
    symbol: str
    name: str
    asset_class: str
    quote_currency: str
    price_scale: int
    timezone: str
    calendar: str
    is_demo: bool
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]


class PriceBarResponse(ContractModel):
    instrument_id: UUID
    observed_at: datetime
    interval: Literal["1d"]
    open: str
    high: str
    low: str
    close: str
    volume: str
    currency: str
    source: str
    quality_status: str
    is_synthetic: bool


class PortfolioResponse(ContractModel):
    id: UUID
    name: str
    base_currency: str
    description: str | None
    is_demo: bool
    version: int
    created_at: datetime
    updated_at: datetime


class PortfolioCreate(ContractModel):
    name: str = Field(min_length=1, max_length=120)
    base_currency: str = Field(default="USD", min_length=3, max_length=3)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("base_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class PortfolioPatch(ContractModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def at_least_one_field(cls, value: str | None) -> str | None:
        return value


class PositionResponse(ContractModel):
    id: UUID
    portfolio_id: UUID
    instrument_id: UUID
    quantity: str
    average_cost: str
    currency: str
    as_of: datetime
    tags: dict[str, str]


class PositionWrite(ContractModel):
    instrument_id: UUID
    quantity: Decimal
    average_cost: Decimal = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    tags: dict[str, str] = Field(default_factory=dict, max_length=20)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class PositionReplacement(ContractModel):
    items: tuple[PositionWrite, ...] = Field(max_length=500)


class PositionReplacementResponse(ContractModel):
    portfolio: PortfolioResponse
    positions: tuple[PositionResponse, ...]


class RiskRecomputeRequest(ContractModel):
    confidence_level: float = Field(default=0.95, gt=0.5, lt=1)


class RiskSnapshotResponse(ContractModel):
    id: UUID
    portfolio_id: UUID
    portfolio_version: int
    as_of: datetime
    created_at: datetime
    methodology_version: str
    window_start: datetime
    window_end: datetime
    confidence_level: float
    base_currency: str
    portfolio_value: str
    daily_pnl: str
    volatility_annualized: float | None
    var_historical: float | None
    var_parametric: float | None
    expected_shortfall: float | None
    max_drawdown: float | None
    data_completeness: float
    quality_status: str
    observation_count: int
    concentration_hhi: float | None
    largest_absolute_weight: float | None
    evidence_id: str
    assumptions: tuple[str, ...]


ShockKind = Literal[
    "instrument_price",
    "asset_class",
    "fx",
    "volatility_multiplier",
    "correlation_override",
]


class ScenarioShockWrite(ContractModel):
    kind: ShockKind
    target: str = Field(default="portfolio", min_length=1, max_length=120)
    value: Decimal


class ScenarioCreate(ContractModel):
    title: str = Field(min_length=1, max_length=160)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    shocks: tuple[ScenarioShockWrite, ...] = Field(min_length=1, max_length=50)
    assumptions: tuple[str, ...] = Field(min_length=1, max_length=50)


class ScenarioShockResponse(ContractModel):
    kind: str
    target: str
    value: str


class ScenarioResponse(ContractModel):
    id: str
    title: str
    version: str
    shocks: tuple[ScenarioShockResponse, ...]
    assumptions: tuple[str, ...]
    hypothetical: bool


class ScenarioPositionResultResponse(ContractModel):
    instrument_id: str
    base_market_value: str
    stressed_market_value: str
    pnl: str
    applied_price_multiplier: str
    applied_fx_multiplier: str


class ScenarioRunResponse(ContractModel):
    id: str
    portfolio_id: UUID
    portfolio_version: int
    run_at: datetime
    scenario_id: str
    scenario_version: str
    methodology_version: str
    base_currency: str
    base_value: str
    stressed_value: str
    pnl: str
    positions: tuple[ScenarioPositionResultResponse, ...]
    volatility_multiplier: str
    assumptions: tuple[str, ...]
    hypothetical: bool


class PipelineRunResponse(ContractModel):
    id: UUID
    pipeline_name: str
    code_version: str
    started_at: datetime
    finished_at: datetime
    status: str
    records_read: int
    accepted: int
    updated: int
    duplicated: int
    rejected: int
    late: int
    watermark_after: datetime
    is_synthetic: bool


class DataQualityIssueResponse(ContractModel):
    id: UUID
    pipeline_run_id: UUID
    entity_type: str
    entity_reference: str
    rule_code: str
    severity: str
    observed_value: str
    expected_constraint: str
    created_at: datetime
    resolved_at: datetime | None
    intentional_fixture: bool


class DataQualitySummaryResponse(ContractModel):
    status: Literal["healthy", "attention_required"]
    total_issues: int
    unresolved_issues: int
    warning_issues: int
    intentional_fixture_issues: int
    latest_pipeline_status: str


class ModelCatalogResponse(ContractModel):
    items: tuple[Any, ...] = ()
    total: Literal[0] = 0
    status: Literal["not_configured"] = "not_configured"
    detail: str


class AuditEventResponse(ContractModel):
    id: UUID
    action: str
    aggregate_type: str
    aggregate_id: UUID | None
    actor_id: str
    occurred_at: datetime
    correlation_id: UUID
    details: dict[str, Any]


class UnsupportedRequest(ContractModel):
    parameters: dict[str, Any] = Field(default_factory=dict, max_length=20)
