"""Pure mappings from domain/application values to public API contracts."""

from __future__ import annotations

from typing import Literal, cast

from quantops_domain import AuditEvent, Instrument, Portfolio, Position
from quantops_risk import (
    AssetClassShock,
    CorrelationOverride,
    FXShock,
    InstrumentPriceShock,
    ScenarioDefinition,
    VolatilityMultiplier,
)

from quantops_api.api.schemas import (
    AiEvaluationCaseResponse,
    AiEvaluationResponse,
    AiEvidenceReferenceResponse,
    AiSafeTraceResponse,
    AiValidationResponse,
    AuditEventResponse,
    DataQualityIssueResponse,
    InstrumentResponse,
    PipelineRunResponse,
    PortfolioResponse,
    PositionResponse,
    PriceBarResponse,
    RiskBriefResponse,
    RiskSnapshotResponse,
    ScenarioPositionResultResponse,
    ScenarioResponse,
    ScenarioRunResponse,
    ScenarioShockResponse,
)
from quantops_api.application.ai_service import (
    AiEvaluationApplicationRecord,
    RiskBriefApplicationRecord,
)
from quantops_api.application.demo_service import (
    DataQualityIssueRecord,
    PipelineRunRecord,
    PriceBarRecord,
    RiskSnapshotRecord,
    ScenarioRunRecord,
)


def instrument_response(value: Instrument) -> InstrumentResponse:
    return InstrumentResponse(
        id=value.id,
        source=value.source,
        symbol=value.symbol.value,
        name=value.name,
        asset_class=value.asset_class.value,
        quote_currency=value.quote_currency.code,
        price_scale=value.price_scale,
        timezone=value.timezone,
        calendar=value.calendar,
        is_demo=value.is_demo,
        created_at=value.created_at,
        updated_at=value.updated_at,
        metadata=dict(value.metadata),
    )


def price_response(value: PriceBarRecord) -> PriceBarResponse:
    return PriceBarResponse(
        instrument_id=value.instrument_id,
        observed_at=value.observed_at,
        interval="1d",
        open=str(value.open),
        high=str(value.high),
        low=str(value.low),
        close=str(value.close),
        volume=str(value.volume),
        currency=value.currency,
        source=value.source,
        quality_status=value.quality_status,
        is_synthetic=value.is_synthetic,
    )


def portfolio_response(value: Portfolio) -> PortfolioResponse:
    return PortfolioResponse(
        id=value.id,
        name=value.name,
        base_currency=value.base_currency.code,
        description=value.description,
        is_demo=value.is_demo,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def position_response(value: Position) -> PositionResponse:
    return PositionResponse(
        id=value.id,
        portfolio_id=value.portfolio_id,
        instrument_id=value.instrument_id,
        quantity=str(value.quantity),
        average_cost=str(value.average_cost),
        currency=value.currency.code,
        as_of=value.as_of,
        tags=dict(value.tags),
    )


def risk_response(value: RiskSnapshotRecord) -> RiskSnapshotResponse:
    return RiskSnapshotResponse(
        id=value.id,
        portfolio_id=value.portfolio_id,
        portfolio_version=value.portfolio_version,
        as_of=value.as_of,
        created_at=value.created_at,
        methodology_version=value.methodology_version,
        window_start=value.window_start,
        window_end=value.window_end,
        confidence_level=value.confidence_level,
        base_currency=value.base_currency,
        portfolio_value=str(value.portfolio_value),
        daily_pnl=str(value.daily_pnl),
        volatility_annualized=value.volatility_annualized,
        var_historical=value.var_historical,
        var_parametric=value.var_parametric,
        expected_shortfall=value.expected_shortfall,
        max_drawdown=value.max_drawdown,
        data_completeness=value.data_completeness,
        quality_status=value.quality_status,
        observation_count=value.observation_count,
        concentration_hhi=value.concentration_hhi,
        largest_absolute_weight=value.largest_absolute_weight,
        evidence_id=value.evidence_id,
        assumptions=value.assumptions,
    )


def _shock_response(value: object) -> ScenarioShockResponse:
    if isinstance(value, InstrumentPriceShock):
        return ScenarioShockResponse(
            kind="instrument_price", target=value.instrument_id, value=str(value.percentage)
        )
    if isinstance(value, AssetClassShock):
        return ScenarioShockResponse(
            kind="asset_class", target=value.asset_class, value=str(value.percentage)
        )
    if isinstance(value, VolatilityMultiplier):
        return ScenarioShockResponse(
            kind="volatility_multiplier", target="portfolio", value=str(value.multiplier)
        )
    if isinstance(value, FXShock):
        return ScenarioShockResponse(kind="fx", target=value.currency, value=str(value.percentage))
    correlation = cast(CorrelationOverride, value)
    left, right = correlation.canonical_pair
    return ScenarioShockResponse(
        kind="correlation_override",
        target=f"{left}:{right}",
        value=str(correlation.correlation),
    )


def scenario_response(value: ScenarioDefinition) -> ScenarioResponse:
    return ScenarioResponse(
        id=value.key,
        title=value.title,
        version=value.version,
        shocks=tuple(_shock_response(item) for item in value.shocks),
        assumptions=value.assumptions,
        hypothetical=value.hypothetical,
    )


def scenario_run_response(value: ScenarioRunRecord) -> ScenarioRunResponse:
    result = value.result
    return ScenarioRunResponse(
        id=value.id,
        portfolio_id=value.portfolio_id,
        portfolio_version=value.portfolio_version,
        run_at=value.run_at,
        scenario_id=result.scenario_key,
        scenario_version=result.scenario_version,
        methodology_version=result.methodology_version,
        base_currency=result.base_currency,
        base_value=str(result.base_value),
        stressed_value=str(result.stressed_value),
        pnl=str(result.pnl),
        positions=tuple(
            ScenarioPositionResultResponse(
                instrument_id=item.instrument_id,
                base_market_value=str(item.base_market_value),
                stressed_market_value=str(item.stressed_market_value),
                pnl=str(item.pnl),
                applied_price_multiplier=str(item.applied_price_multiplier),
                applied_fx_multiplier=str(item.applied_fx_multiplier),
            )
            for item in result.positions
        ),
        volatility_multiplier=str(result.volatility_multiplier),
        assumptions=result.assumptions,
        hypothetical=result.hypothetical,
    )


def pipeline_response(value: PipelineRunRecord) -> PipelineRunResponse:
    return PipelineRunResponse(**{field: getattr(value, field) for field in value.__slots__})


def quality_issue_response(value: DataQualityIssueRecord) -> DataQualityIssueResponse:
    return DataQualityIssueResponse(**{field: getattr(value, field) for field in value.__slots__})


def audit_response(value: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=value.id,
        action=value.action.value,
        aggregate_type=value.aggregate_type,
        aggregate_id=value.aggregate_id,
        actor_id=value.actor_id,
        occurred_at=value.occurred_at,
        correlation_id=value.correlation_id,
        details=dict(value.details),
    )


def risk_brief_response(value: RiskBriefApplicationRecord) -> RiskBriefResponse:
    report = value.result.validation
    if report is None:
        validation = AiValidationResponse(
            valid=True,
            citation_valid=True,
            numerical_valid=True,
            citation_precision=1.0,
            required_citation_coverage=1.0,
            checked_numeric_claims=0,
            issue_codes=value.result.trace.validation_issue_codes,
        )
    else:
        validation = AiValidationResponse(
            valid=report.valid,
            citation_valid=report.citation.valid,
            numerical_valid=report.numerical.valid,
            citation_precision=report.citation.precision,
            required_citation_coverage=report.citation.required_coverage,
            checked_numeric_claims=report.numerical.checked_claims,
            issue_codes=report.issue_codes,
        )
    trace = value.result.trace
    return RiskBriefResponse(
        id=value.id,
        portfolio_id=value.portfolio_id,
        snapshot_ids=value.snapshot_ids,
        source_evidence_ids=value.source_evidence_ids,
        created_at=value.created_at,
        correlation_id=value.correlation_id,
        provider=cast(Literal["deterministic-risk-brief-v1"], value.provider),
        brief=value.result.brief,
        evidence=tuple(
            AiEvidenceReferenceResponse(
                evidence_id=item.evidence_id,
                kind=item.kind.value,
                source_timestamp=item.source_timestamp,
                title=item.title,
                metric_name=item.metric_name,
                canonical_value=(
                    None if item.canonical_value is None else str(item.canonical_value)
                ),
                canonical_unit=(None if item.canonical_unit is None else item.canonical_unit.value),
                document_id=item.document_id,
                section=item.section,
                source_url=item.source_url,
                publication_date=item.publication_date,
                synthetic=item.synthetic,
            )
            for item in value.evidence
        ),
        validation=validation,
        trace=AiSafeTraceResponse(
            trace_version=trace.trace_version,
            request_fingerprint=trace.request_fingerprint,
            states=trace.states,
            tool_names=trace.tool_names,
            tool_call_count=trace.tool_call_count,
            evidence_ids=trace.evidence_ids,
            provider_attempts=trace.provider_attempts,
            validation_issue_codes=trace.validation_issue_codes,
            repair_attempted=trace.repair_attempted,
            fallback_used=trace.fallback_used,
            elapsed_ms=trace.elapsed_ms,
        ),
    )


def ai_evaluation_response(value: AiEvaluationApplicationRecord) -> AiEvaluationResponse:
    report = value.report
    return AiEvaluationResponse(
        id=value.id,
        created_at=value.created_at,
        correlation_id=value.correlation_id,
        report_version=report.report_version,
        suite_version=report.suite_version,
        case_count=report.case_count,
        passed=report.passed,
        failed=report.failed,
        category_count=report.category_count,
        schema_valid_rate=report.schema_valid_rate,
        citation_valid_rate=report.citation_valid_rate,
        numerical_consistency_rate=report.numerical_consistency_rate,
        refusal_accuracy=report.refusal_accuracy,
        tool_selection_accuracy=report.tool_selection_accuracy,
        groundedness_rate=report.groundedness_rate,
        mean_latency_ms=report.mean_latency_ms,
        total_tool_calls=report.total_tool_calls,
        fallback_rate=report.fallback_rate,
        external_provider_cost_usd=report.external_provider_cost_usd,
        external_provider_token_estimate=report.external_provider_token_estimate,
        cases=tuple(
            AiEvaluationCaseResponse(
                case_id=item.case_id,
                category=item.category,
                passed=item.passed,
                schema_valid=item.schema_valid,
                citation_valid=item.citation_valid,
                citation_precision=item.citation_precision,
                required_citation_coverage=item.required_citation_coverage,
                numerical_consistency=item.numerical_consistency,
                refusal_accurate=item.refusal_accurate,
                tool_selection_correct=item.tool_selection_correct,
                groundedness=item.groundedness,
                latency_ms=item.latency_ms,
                tool_call_count=item.tool_call_count,
                fallback_used=item.fallback_used,
                issue_codes=item.issue_codes,
            )
            for item in report.cases
        ),
    )
