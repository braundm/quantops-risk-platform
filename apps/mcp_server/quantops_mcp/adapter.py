"""Typed mappings over the existing QuantOps application-service read methods."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel
from quantops_api.application.demo_service import (
    DEMO_PORTFOLIO_ID,
    DemoQuantOpsService,
    RiskSnapshotRecord,
)
from quantops_risk.scenarios import (
    AssetClassShock,
    CorrelationOverride,
    FXShock,
    InstrumentPriceShock,
    ScenarioDefinition,
    ScenarioShock,
    VolatilityMultiplier,
)

from .models import (
    EvidenceManifestView,
    LatestRiskOutput,
    RiskSnapshotView,
    ScenarioCatalogOutput,
    ScenarioShockView,
    ScenarioView,
    SnapshotEvidenceOutput,
)

DEFAULT_MAX_RESPONSE_BYTES = 32 * 1024
DEFAULT_TIMEOUT_SECONDS = 1.0
MAX_SCENARIOS = 20


class ReadService(Protocol):
    """Only application-service methods the MCP boundary is allowed to call."""

    def latest_risk(self, portfolio_id: UUID) -> RiskSnapshotRecord: ...

    def get_snapshot(self, snapshot_id: UUID) -> RiskSnapshotRecord: ...

    def get_evidence(self, snapshot_id: UUID) -> dict[str, Any]: ...

    def list_scenarios(self) -> tuple[ScenarioDefinition, ...]: ...


def default_read_service() -> ReadService:
    """Create the existing deterministic application service without duplicating persistence."""
    return DemoQuantOpsService()


def validate_security_limits(*, timeout_seconds: float, max_response_bytes: int) -> None:
    """Prevent callers from weakening the local server's fixed upper bounds."""
    if not 0 < timeout_seconds <= DEFAULT_TIMEOUT_SECONDS:
        raise ValueError("timeout_seconds must be positive and no greater than 1 second")
    if not 0 < max_response_bytes <= DEFAULT_MAX_RESPONSE_BYTES:
        raise ValueError("max_response_bytes must be positive and no greater than 32768")


async def run_read_with_timeout[**P, T](
    operation: Callable[P, T],
    timeout_seconds: float,
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    """Run a synchronous application read behind a deterministic timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(operation, *args, **kwargs),
            timeout=timeout_seconds,
        )
    except TimeoutError as error:
        raise RuntimeError("approved application read exceeded the MCP timeout") from error


def enforce_response_limit[M: BaseModel](model: M, *, max_response_bytes: int) -> M:
    """Reject structured results exceeding the deterministic serialized byte limit."""
    encoded = model.model_dump_json(exclude_none=False).encode("utf-8")
    if len(encoded) > max_response_bytes:
        raise RuntimeError("structured MCP response exceeds the configured byte limit")
    return model


def require_demo_portfolio(portfolio_id: UUID) -> None:
    """Enforce the single approved local demo scope."""
    if portfolio_id != DEMO_PORTFOLIO_ID:
        raise ValueError("portfolio is outside the approved demo scope")


def require_demo_snapshot(snapshot: RiskSnapshotRecord) -> None:
    """Prevent a valid snapshot UUID from crossing the approved portfolio scope."""
    require_demo_portfolio(snapshot.portfolio_id)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("application timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def map_risk(snapshot: RiskSnapshotRecord) -> LatestRiskOutput:
    """Map an application record without recalculating any authoritative value."""
    require_demo_snapshot(snapshot)
    if snapshot.base_currency != "USD":
        raise ValueError("application snapshot is outside the approved currency scope")
    view = RiskSnapshotView(
        snapshot_id=str(snapshot.id),
        portfolio_id=str(snapshot.portfolio_id),
        portfolio_version=snapshot.portfolio_version,
        as_of=_iso_utc(snapshot.as_of),
        methodology_version=snapshot.methodology_version,
        confidence_level=snapshot.confidence_level,
        observation_count=snapshot.observation_count,
        base_currency="USD",
        portfolio_value=str(snapshot.portfolio_value),
        daily_pnl=str(snapshot.daily_pnl),
        volatility_annualized=snapshot.volatility_annualized,
        var_historical=snapshot.var_historical,
        var_parametric=snapshot.var_parametric,
        expected_shortfall=snapshot.expected_shortfall,
        max_drawdown=snapshot.max_drawdown,
        data_completeness=snapshot.data_completeness,
        quality_status=snapshot.quality_status,
        concentration_hhi=snapshot.concentration_hhi,
        largest_absolute_weight=snapshot.largest_absolute_weight,
        evidence_id=snapshot.evidence_id,
        assumptions=snapshot.assumptions,
    )
    return LatestRiskOutput(snapshot=view, evidence_id=snapshot.evidence_id)


def map_evidence(
    snapshot: RiskSnapshotRecord,
    evidence: dict[str, Any],
) -> SnapshotEvidenceOutput:
    """Validate the application evidence manifest before exposing it."""
    require_demo_snapshot(snapshot)
    manifest = EvidenceManifestView.model_validate(evidence)
    if manifest.evidence_id != snapshot.evidence_id:
        raise RuntimeError("application evidence identity does not match the snapshot")
    return SnapshotEvidenceOutput(
        snapshot_id=str(snapshot.id),
        portfolio_id=str(snapshot.portfolio_id),
        evidence_id=manifest.evidence_id,
        evidence=manifest,
    )


def _map_shock(shock: ScenarioShock) -> ScenarioShockView:
    if isinstance(shock, InstrumentPriceShock):
        return ScenarioShockView(
            kind="instrument_price", target=shock.instrument_id, value=str(shock.percentage)
        )
    if isinstance(shock, AssetClassShock):
        return ScenarioShockView(
            kind="asset_class", target=shock.asset_class, value=str(shock.percentage)
        )
    if isinstance(shock, FXShock):
        return ScenarioShockView(kind="fx", target=shock.currency, value=str(shock.percentage))
    if isinstance(shock, VolatilityMultiplier):
        return ScenarioShockView(
            kind="volatility_multiplier", target="portfolio", value=str(shock.multiplier)
        )
    if isinstance(shock, CorrelationOverride):
        return ScenarioShockView(
            kind="correlation_override",
            target=":".join(shock.canonical_pair),
            value=str(shock.correlation),
        )
    raise TypeError("unsupported application scenario shock")


def map_scenarios(scenarios: tuple[ScenarioDefinition, ...]) -> ScenarioCatalogOutput:
    """Map a deterministic, capped system-scenario catalog."""
    if len(scenarios) > MAX_SCENARIOS:
        raise RuntimeError("application scenario catalog exceeds the MCP item limit")
    if any(not item.hypothetical for item in scenarios):
        raise ValueError("application scenario catalog contains a non-hypothetical entry")
    values = tuple(
        ScenarioView(
            scenario_id=item.key,
            title=item.title,
            version=item.version,
            shocks=tuple(_map_shock(shock) for shock in item.shocks),
            assumptions=item.assumptions,
            hypothetical=True,
        )
        for item in sorted(scenarios, key=lambda candidate: candidate.key)
    )
    return ScenarioCatalogOutput(scenarios=values, count=len(values))
