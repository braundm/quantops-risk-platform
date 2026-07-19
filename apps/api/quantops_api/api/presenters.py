"""Pure mappings from domain/application values to public API contracts."""

from __future__ import annotations

from typing import cast

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
    AuditEventResponse,
    DataQualityIssueResponse,
    InstrumentResponse,
    PipelineRunResponse,
    PortfolioResponse,
    PositionResponse,
    PriceBarResponse,
    RiskSnapshotResponse,
    ScenarioPositionResultResponse,
    ScenarioResponse,
    ScenarioRunResponse,
    ScenarioShockResponse,
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
