"""Explicit public request and response contracts for the versioned API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from quantops_ai.models import RiskBrief


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


class RiskBriefCreateRequest(ContractModel):
    question: str = Field(
        default="Why did portfolio risk increase?",
        min_length=1,
        max_length=1_000,
    )
    snapshot_ids: tuple[UUID, ...] = Field(default=(), max_length=2)
    document_query: str | None = Field(default=None, min_length=1, max_length=300)

    @field_validator("question")
    @classmethod
    def non_blank_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized

    @field_validator("document_query")
    @classmethod
    def non_blank_document_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("document query must not be blank")
        return normalized

    @field_validator("snapshot_ids")
    @classmethod
    def unique_snapshot_ids(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if len(value) != len(set(value)):
            raise ValueError("snapshot IDs must be unique")
        return value


class AiEvidenceReferenceResponse(ContractModel):
    evidence_id: str
    kind: str
    source_timestamp: datetime
    title: str
    metric_name: str | None
    canonical_value: str | None
    canonical_unit: str | None
    document_id: str | None
    section: str | None
    source_url: str | None
    publication_date: date | None
    synthetic: bool


class AiValidationResponse(ContractModel):
    valid: bool
    citation_valid: bool
    numerical_valid: bool
    citation_precision: float = Field(ge=0, le=1)
    required_citation_coverage: float = Field(ge=0, le=1)
    checked_numeric_claims: int = Field(ge=0)
    issue_codes: tuple[str, ...]


class AiSafeTraceResponse(ContractModel):
    trace_version: str
    request_fingerprint: str
    states: tuple[str, ...]
    tool_names: tuple[str, ...]
    tool_call_count: int = Field(ge=0)
    evidence_ids: tuple[str, ...]
    provider_attempts: tuple[str, ...]
    validation_issue_codes: tuple[str, ...]
    repair_attempted: bool
    fallback_used: bool
    elapsed_ms: float = Field(ge=0)
    contains_prompt_or_document_body: Literal[False] = False
    contains_chain_of_thought: Literal[False] = False


class RiskBriefResponse(ContractModel):
    id: UUID
    portfolio_id: UUID
    snapshot_ids: tuple[UUID, ...]
    source_evidence_ids: tuple[str, ...]
    created_at: datetime
    correlation_id: UUID
    provider: Literal["deterministic-risk-brief-v1"]
    execution_mode: Literal["deterministic-in-memory"] = "deterministic-in-memory"
    completion_state: Literal["completed"] = "completed"
    external_provider_used: Literal[False] = False
    synthetic: Literal[True] = True
    brief: RiskBrief
    evidence: tuple[AiEvidenceReferenceResponse, ...]
    validation: AiValidationResponse
    trace: AiSafeTraceResponse


class AiEvaluationRequest(ContractModel):
    suite_version: Literal["1.0.0"] = "1.0.0"


class AiEvaluationCaseResponse(ContractModel):
    case_id: str
    category: str
    passed: bool
    schema_valid: bool
    citation_valid: bool
    citation_precision: float = Field(ge=0, le=1)
    required_citation_coverage: float = Field(ge=0, le=1)
    numerical_consistency: bool
    refusal_accurate: bool
    tool_selection_correct: bool
    groundedness: bool
    latency_ms: float = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    fallback_used: bool
    issue_codes: tuple[str, ...]


class AiEvaluationResponse(ContractModel):
    id: UUID
    created_at: datetime
    correlation_id: UUID
    execution_mode: Literal["deterministic-in-memory"] = "deterministic-in-memory"
    completion_state: Literal["completed"] = "completed"
    deterministic: Literal[True] = True
    external_provider_used: Literal[False] = False
    report_version: str
    suite_version: str
    case_count: int = Field(ge=1)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    category_count: int = Field(ge=1)
    schema_valid_rate: float = Field(ge=0, le=1)
    citation_valid_rate: float = Field(ge=0, le=1)
    numerical_consistency_rate: float = Field(ge=0, le=1)
    refusal_accuracy: float = Field(ge=0, le=1)
    tool_selection_accuracy: float = Field(ge=0, le=1)
    groundedness_rate: float = Field(ge=0, le=1)
    mean_latency_ms: float = Field(ge=0)
    total_tool_calls: int = Field(ge=0)
    fallback_rate: float = Field(ge=0, le=1)
    external_provider_cost_usd: None
    external_provider_token_estimate: None
    evaluation_policy: Literal["deterministic labeled checks; no model-graded scoring"] = (
        "deterministic labeled checks; no model-graded scoring"
    )
    cases: tuple[AiEvaluationCaseResponse, ...]


class AuditEventResponse(ContractModel):
    id: UUID
    action: str
    aggregate_type: str
    aggregate_id: UUID | None
    actor_id: str
    occurred_at: datetime
    correlation_id: UUID
    details: dict[str, Any]
