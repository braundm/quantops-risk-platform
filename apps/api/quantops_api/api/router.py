"""Versioned REST routes for the deterministic QuantOps application slice."""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from quantops_risk import METHODOLOGY_VERSION

from quantops_api import __version__
from quantops_api.api.dependencies import (
    Limit,
    Offset,
    etag,
    get_ai_service,
    get_request_correlation_id,
    get_service,
    require_demo_token,
    require_expensive_capacity,
    require_idempotency_key,
    require_if_match,
)
from quantops_api.api.presenters import (
    ai_evaluation_response,
    audit_response,
    instrument_response,
    pipeline_response,
    portfolio_response,
    position_response,
    price_response,
    quality_issue_response,
    risk_brief_response,
    risk_response,
    scenario_response,
    scenario_run_response,
)
from quantops_api.api.schemas import (
    AiEvaluationRequest,
    AiEvaluationResponse,
    AuditEventResponse,
    DataQualityIssueResponse,
    DataQualitySummaryResponse,
    HealthResponse,
    InstrumentResponse,
    ModelCatalogResponse,
    Page,
    PipelineRunResponse,
    PortfolioCreate,
    PortfolioPatch,
    PortfolioResponse,
    PositionReplacement,
    PositionReplacementResponse,
    PositionResponse,
    PriceBarResponse,
    ProblemDetails,
    ReadinessResponse,
    RiskBriefCreateRequest,
    RiskBriefResponse,
    RiskRecomputeRequest,
    RiskSnapshotResponse,
    ScenarioCreate,
    ScenarioResponse,
    ScenarioRunResponse,
    VersionResponse,
)
from quantops_api.application.ai_service import DeterministicAiApplicationService
from quantops_api.application.demo_service import (
    CustomShockCommand,
    DemoQuantOpsService,
)
from quantops_api.application.errors import (
    NotFoundError,
    RequestFormatError,
)
from quantops_api.settings import Settings

Service = Annotated[DemoQuantOpsService, Depends(get_service)]
AiService = Annotated[DeterministicAiApplicationService, Depends(get_ai_service)]
CorrelationId = Annotated[UUID, Depends(get_request_correlation_id)]
ExpectedVersion = Annotated[int, Depends(require_if_match)]
IdempotencyKey = Annotated[str, Depends(require_idempotency_key)]

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ProblemDetails, "description": "Invalid request"},
    401: {"model": ProblemDetails, "description": "Demo token missing or invalid"},
    404: {"model": ProblemDetails, "description": "Resource not found"},
    409: {"model": ProblemDetails, "description": "Conflict or stale aggregate version"},
    422: {"model": ProblemDetails, "description": "Request or domain validation failed"},
    428: {"model": ProblemDetails, "description": "Required precondition missing"},
    429: {"model": ProblemDetails, "description": "Expensive-operation limit reached"},
    503: {"model": ProblemDetails, "description": "Optional capability unavailable"},
}

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


def _page[ItemT](items: tuple[ItemT, ...], limit: int, offset: int) -> Page[ItemT]:
    total = len(items)
    selected = items[offset : offset + limit]
    next_offset = offset + len(selected) if offset + len(selected) < total else None
    return Page(
        items=selected,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
    )


def _mark_idempotency(response: Response, replayed: bool) -> None:
    response.status_code = status.HTTP_200_OK if replayed else status.HTTP_201_CREATED
    response.headers["Idempotent-Replay"] = "true" if replayed else "false"


@router.get("/health", response_model=HealthResponse, tags=["operations"])
async def health() -> HealthResponse:
    """Report process liveness without probing optional infrastructure."""

    return HealthResponse(version=__version__)


@router.get("/ready", response_model=ReadinessResponse, tags=["operations"])
async def ready(request: Request) -> ReadinessResponse:
    """Explain which honest runtime mode is ready without exposing credentials."""

    settings: Settings = request.app.state.settings
    if settings.demo_mode:
        return ReadinessResponse(
            status="ready",
            version=__version__,
            mode="deterministic-demo",
            checks={"application_service": "ready", "database": "not_configured"},
        )
    return ReadinessResponse(
        status="degraded",
        version=__version__,
        mode="infrastructure-required",
        checks={"application_service": "ready", "database": "not_configured"},
    )


@router.get("/version", response_model=VersionResponse, tags=["operations"])
async def version() -> VersionResponse:
    return VersionResponse(version=__version__, methodology_version=METHODOLOGY_VERSION)


@router.get("/instruments", response_model=Page[InstrumentResponse], tags=["market data"])
async def list_instruments(
    service: Service,
    limit: Limit = 50,
    offset: Offset = 0,
    symbol: Annotated[str | None, Query(min_length=1, max_length=32)] = None,
    asset_class: Annotated[str | None, Query(min_length=1, max_length=40)] = None,
) -> Page[InstrumentResponse]:
    items = service.list_instruments()
    if symbol is not None:
        items = tuple(item for item in items if item.symbol.value == symbol.strip().upper())
    if asset_class is not None:
        items = tuple(
            item for item in items if item.asset_class.value == asset_class.strip().lower()
        )
    return _page(tuple(instrument_response(item) for item in items), limit, offset)


@router.get(
    "/instruments/{instrument_id}",
    response_model=InstrumentResponse,
    tags=["market data"],
)
async def get_instrument(instrument_id: UUID, service: Service) -> InstrumentResponse:
    return instrument_response(service.get_instrument(instrument_id))


@router.get(
    "/instruments/{instrument_id}/prices",
    response_model=Page[PriceBarResponse],
    tags=["market data"],
)
async def list_prices(
    instrument_id: UUID,
    service: Service,
    limit: Limit = 100,
    offset: Offset = 0,
    start: date | None = None,
    end: date | None = None,
    interval: Literal["1d"] = "1d",
) -> Page[PriceBarResponse]:
    del interval
    if start is not None and end is not None:
        if start > end:
            raise RequestFormatError("start must be on or before end")
        if (end - start).days > 366:
            raise RequestFormatError("price date windows are limited to 366 days")
    items = service.list_prices(instrument_id, start=start, end=end)
    return _page(tuple(price_response(item) for item in items), limit, offset)


@router.get("/portfolios", response_model=Page[PortfolioResponse], tags=["portfolios"])
async def list_portfolios(
    service: Service, limit: Limit = 50, offset: Offset = 0
) -> Page[PortfolioResponse]:
    return _page(
        tuple(portfolio_response(item) for item in service.list_portfolios()), limit, offset
    )


@router.post(
    "/portfolios",
    response_model=PortfolioResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["portfolios"],
    dependencies=[Depends(require_demo_token)],
)
async def create_portfolio(
    payload: PortfolioCreate,
    response: Response,
    service: Service,
    correlation_id: CorrelationId,
) -> PortfolioResponse:
    value = service.create_portfolio(
        name=payload.name,
        base_currency=payload.base_currency,
        description=payload.description,
        correlation_id=correlation_id,
    )
    response.headers["ETag"] = etag(value.version)
    return portfolio_response(value)


@router.get("/portfolios/{portfolio_id}", response_model=PortfolioResponse, tags=["portfolios"])
async def get_portfolio(
    portfolio_id: UUID, response: Response, service: Service
) -> PortfolioResponse:
    value = service.get_portfolio(portfolio_id)
    response.headers["ETag"] = etag(value.version)
    return portfolio_response(value)


@router.patch(
    "/portfolios/{portfolio_id}",
    response_model=PortfolioResponse,
    tags=["portfolios"],
    dependencies=[Depends(require_demo_token)],
)
async def patch_portfolio(
    portfolio_id: UUID,
    payload: PortfolioPatch,
    response: Response,
    service: Service,
    correlation_id: CorrelationId,
    expected_version: ExpectedVersion,
) -> PortfolioResponse:
    if not payload.model_fields_set:
        raise RequestFormatError("at least one portfolio field must be supplied")
    value = service.patch_portfolio(
        portfolio_id,
        expected_version=expected_version,
        name=payload.name,
        description=payload.description,
        description_is_set="description" in payload.model_fields_set,
        correlation_id=correlation_id,
    )
    response.headers["ETag"] = etag(value.version)
    return portfolio_response(value)


@router.get(
    "/portfolios/{portfolio_id}/positions",
    response_model=Page[PositionResponse],
    tags=["portfolios"],
)
async def list_positions(
    portfolio_id: UUID,
    service: Service,
    limit: Limit = 100,
    offset: Offset = 0,
) -> Page[PositionResponse]:
    return _page(
        tuple(position_response(item) for item in service.list_positions(portfolio_id)),
        limit,
        offset,
    )


@router.put(
    "/portfolios/{portfolio_id}/positions",
    response_model=PositionReplacementResponse,
    tags=["portfolios"],
    dependencies=[Depends(require_demo_token)],
)
async def replace_positions(
    portfolio_id: UUID,
    payload: PositionReplacement,
    response: Response,
    service: Service,
    correlation_id: CorrelationId,
    expected_version: ExpectedVersion,
) -> PositionReplacementResponse:
    portfolio, positions = service.replace_positions(
        portfolio_id,
        expected_version=expected_version,
        items=tuple(
            (
                item.instrument_id,
                item.quantity,
                item.average_cost,
                item.currency,
                item.tags,
            )
            for item in payload.items
        ),
        correlation_id=correlation_id,
    )
    response.headers["ETag"] = etag(portfolio.version)
    return PositionReplacementResponse(
        portfolio=portfolio_response(portfolio),
        positions=tuple(position_response(item) for item in positions),
    )


@router.get(
    "/portfolios/{portfolio_id}/risk/latest",
    response_model=RiskSnapshotResponse,
    tags=["risk"],
)
async def latest_risk(portfolio_id: UUID, service: Service) -> RiskSnapshotResponse:
    return risk_response(service.latest_risk(portfolio_id))


@router.get(
    "/portfolios/{portfolio_id}/risk/history",
    response_model=Page[RiskSnapshotResponse],
    tags=["risk"],
)
async def risk_history(
    portfolio_id: UUID,
    service: Service,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[RiskSnapshotResponse]:
    values = tuple(risk_response(item) for item in reversed(service.risk_history(portfolio_id)))
    return _page(values, limit, offset)


@router.post(
    "/portfolios/{portfolio_id}/risk/recompute",
    response_model=RiskSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["risk"],
    dependencies=[Depends(require_demo_token), Depends(require_expensive_capacity)],
)
async def recompute_risk(
    portfolio_id: UUID,
    payload: RiskRecomputeRequest,
    response: Response,
    service: Service,
    correlation_id: CorrelationId,
    idempotency_key: IdempotencyKey,
) -> RiskSnapshotResponse:
    result = service.recompute_risk(
        portfolio_id,
        confidence_level=payload.confidence_level,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
    _mark_idempotency(response, result.replayed)
    return risk_response(result.value)


@router.get("/risk/snapshots/{snapshot_id}", response_model=RiskSnapshotResponse, tags=["risk"])
async def get_snapshot(snapshot_id: UUID, service: Service) -> RiskSnapshotResponse:
    return risk_response(service.get_snapshot(snapshot_id))


@router.get("/risk/snapshots/{snapshot_id}/evidence", tags=["risk"])
async def get_evidence(snapshot_id: UUID, service: Service) -> dict[str, Any]:
    return service.get_evidence(snapshot_id)


@router.get("/scenarios", response_model=Page[ScenarioResponse], tags=["scenarios"])
async def list_scenarios(
    service: Service, limit: Limit = 50, offset: Offset = 0
) -> Page[ScenarioResponse]:
    return _page(tuple(scenario_response(item) for item in service.list_scenarios()), limit, offset)


@router.post(
    "/scenarios",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["scenarios"],
    dependencies=[Depends(require_demo_token), Depends(require_expensive_capacity)],
)
async def create_scenario(
    payload: ScenarioCreate,
    response: Response,
    service: Service,
    correlation_id: CorrelationId,
    idempotency_key: IdempotencyKey,
) -> ScenarioResponse:
    result = service.create_scenario(
        title=payload.title,
        version=payload.version,
        shocks=tuple(
            CustomShockCommand(item.kind, item.target, item.value) for item in payload.shocks
        ),
        assumptions=payload.assumptions,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
    _mark_idempotency(response, result.replayed)
    return scenario_response(result.value)


@router.post(
    "/portfolios/{portfolio_id}/scenarios/{scenario_id}/run",
    response_model=ScenarioRunResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["scenarios"],
    dependencies=[Depends(require_demo_token), Depends(require_expensive_capacity)],
)
async def run_scenario(
    portfolio_id: UUID,
    scenario_id: str,
    response: Response,
    service: Service,
    correlation_id: CorrelationId,
    idempotency_key: IdempotencyKey,
) -> ScenarioRunResponse:
    result = service.run_scenario(
        portfolio_id,
        scenario_id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
    _mark_idempotency(response, result.replayed)
    return scenario_run_response(result.value)


@router.get(
    "/scenario-runs/{scenario_run_id}",
    response_model=ScenarioRunResponse,
    tags=["scenarios"],
)
async def get_scenario_run(scenario_run_id: str, service: Service) -> ScenarioRunResponse:
    return scenario_run_response(service.get_scenario_run(scenario_run_id))


@router.get("/pipelines/runs", response_model=Page[PipelineRunResponse], tags=["data quality"])
async def list_pipeline_runs(
    service: Service, limit: Limit = 50, offset: Offset = 0
) -> Page[PipelineRunResponse]:
    return _page(
        tuple(pipeline_response(item) for item in service.list_pipeline_runs()), limit, offset
    )


@router.get("/pipelines/runs/{run_id}", response_model=PipelineRunResponse, tags=["data quality"])
async def get_pipeline_run(run_id: UUID, service: Service) -> PipelineRunResponse:
    return pipeline_response(service.get_pipeline_run(run_id))


@router.get(
    "/data-quality/issues", response_model=Page[DataQualityIssueResponse], tags=["data quality"]
)
async def list_quality_issues(
    service: Service,
    limit: Limit = 50,
    offset: Offset = 0,
    unresolved_only: bool = False,
) -> Page[DataQualityIssueResponse]:
    values = service.list_quality_issues()
    if unresolved_only:
        values = tuple(item for item in values if item.resolved_at is None)
    return _page(tuple(quality_issue_response(item) for item in values), limit, offset)


@router.get(
    "/data-quality/summary", response_model=DataQualitySummaryResponse, tags=["data quality"]
)
async def quality_summary(service: Service) -> DataQualitySummaryResponse:
    issues = service.list_quality_issues()
    unresolved = tuple(item for item in issues if item.resolved_at is None)
    return DataQualitySummaryResponse(
        status="healthy" if not unresolved else "attention_required",
        total_issues=len(issues),
        unresolved_issues=len(unresolved),
        warning_issues=sum(item.severity == "warning" for item in issues),
        intentional_fixture_issues=sum(item.intentional_fixture for item in issues),
        latest_pipeline_status=service.list_pipeline_runs()[-1].status,
    )


@router.get("/models", response_model=ModelCatalogResponse, tags=["models"])
async def list_models() -> ModelCatalogResponse:
    return ModelCatalogResponse(
        detail="no ML model is configured; the API does not fabricate model results"
    )


@router.get("/models/{model_id}", tags=["models"])
@router.get("/models/{model_id}/evaluations", tags=["models"])
@router.get("/models/{model_id}/drift", tags=["models"])
async def get_unconfigured_model(model_id: str) -> None:
    raise NotFoundError(f"model {model_id} is not configured")


@router.post(
    "/portfolios/{portfolio_id}/risk-briefs",
    response_model=RiskBriefResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["grounded AI"],
    dependencies=[
        Depends(require_demo_token),
        Depends(require_expensive_capacity),
    ],
)
async def create_risk_brief(
    portfolio_id: UUID,
    payload: RiskBriefCreateRequest,
    response: Response,
    service: AiService,
    correlation_id: CorrelationId,
    idempotency_key: IdempotencyKey,
) -> RiskBriefResponse:
    result = service.create_risk_brief(
        portfolio_id,
        question=payload.question,
        snapshot_ids=payload.snapshot_ids,
        document_query=payload.document_query,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
    _mark_idempotency(response, result.replayed)
    return risk_brief_response(result.value)


@router.get(
    "/risk-briefs/{brief_id}",
    response_model=RiskBriefResponse,
    tags=["grounded AI"],
)
async def get_risk_brief(brief_id: UUID, service: AiService) -> RiskBriefResponse:
    return risk_brief_response(service.get_risk_brief(brief_id))


@router.post(
    "/ai/evaluations/run",
    response_model=AiEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["grounded AI"],
    dependencies=[
        Depends(require_demo_token),
        Depends(require_expensive_capacity),
    ],
)
async def run_ai_evaluation(
    payload: AiEvaluationRequest,
    response: Response,
    service: AiService,
    correlation_id: CorrelationId,
    idempotency_key: IdempotencyKey,
) -> AiEvaluationResponse:
    result = service.run_evaluation(
        suite_version=payload.suite_version,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
    _mark_idempotency(response, result.replayed)
    return ai_evaluation_response(result.value)


@router.get("/audit-events", response_model=Page[AuditEventResponse], tags=["audit"])
async def list_audit_events(
    service: Service,
    limit: Limit = 50,
    offset: Offset = 0,
    aggregate_type: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
) -> Page[AuditEventResponse]:
    values = service.list_audit_events()
    if aggregate_type is not None:
        values = tuple(item for item in values if item.aggregate_type == aggregate_type.casefold())
    values = tuple(reversed(values))
    return _page(tuple(audit_response(item) for item in values), limit, offset)


@router.get("/reports/portfolios/{portfolio_id}.json", tags=["reports"])
async def portfolio_json_report(portfolio_id: UUID, service: Service) -> JSONResponse:
    return JSONResponse(
        service.portfolio_report(portfolio_id),
        headers={"Content-Disposition": f'attachment; filename="portfolio-{portfolio_id}.json"'},
    )


@router.get("/reports/portfolios/{portfolio_id}.csv", tags=["reports"])
async def portfolio_csv_report(portfolio_id: UUID, service: Service) -> Response:
    report = service.portfolio_report(portfolio_id)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=("instrument_id", "symbol", "quantity", "market_value", "currency"),
    )
    writer.writeheader()
    writer.writerows(report["positions"])
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="portfolio-{portfolio_id}.csv"'},
    )
