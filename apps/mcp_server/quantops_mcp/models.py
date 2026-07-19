"""Strict structured-output schemas for the bounded MCP surface."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictOutput(BaseModel):
    """Base schema that rejects undeclared and non-finite output."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class RiskSnapshotView(StrictOutput):
    """Stable application-service risk snapshot projection."""

    snapshot_id: str
    portfolio_id: str
    portfolio_version: int = Field(ge=1)
    as_of: str
    methodology_version: str
    confidence_level: float = Field(gt=0, lt=1)
    observation_count: int = Field(ge=0)
    base_currency: Literal["USD"]
    portfolio_value: str
    daily_pnl: str
    volatility_annualized: float | None
    var_historical: float | None
    var_parametric: float | None
    expected_shortfall: float | None
    max_drawdown: float | None
    data_completeness: float = Field(ge=0, le=1)
    quality_status: str
    concentration_hhi: float | None
    largest_absolute_weight: float | None
    evidence_id: str = Field(min_length=1, max_length=160)
    assumptions: tuple[str, ...]


class LatestRiskOutput(StrictOutput):
    """Tool envelope for an in-scope latest risk snapshot."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    scope: Literal["demo"] = "demo"
    is_synthetic: Literal[True] = True
    not_investment_advice: Literal[True] = True
    snapshot: RiskSnapshotView
    evidence_id: str = Field(min_length=1, max_length=160)
    methodology_resource: Literal["quantops://methodology/risk/1.0.0"] = (
        "quantops://methodology/risk/1.0.0"
    )


class EvidenceItemView(StrictOutput):
    """One hashed evidence input from the risk-engine manifest."""

    as_of: str
    key: str = Field(min_length=1, max_length=240)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_kind: str = Field(min_length=1, max_length=100)


class EvidenceManifestView(StrictOutput):
    """Validated evidence manifest returned by the application service."""

    calculation_parameters: tuple[tuple[str, str], ...]
    evidence_id: str = Field(min_length=1, max_length=160)
    items: tuple[EvidenceItemView, ...]
    methodology_version: str


class SnapshotEvidenceOutput(StrictOutput):
    """Tool envelope for an approved snapshot evidence manifest."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    scope: Literal["demo"] = "demo"
    is_synthetic: Literal[True] = True
    not_investment_advice: Literal[True] = True
    snapshot_id: str
    portfolio_id: str
    evidence_id: str = Field(min_length=1, max_length=160)
    evidence: EvidenceManifestView


class ScenarioShockView(StrictOutput):
    """Canonical, serializable system-scenario shock."""

    kind: Literal[
        "instrument_price",
        "asset_class",
        "fx",
        "volatility_multiplier",
        "correlation_override",
    ]
    target: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=80)


class ScenarioView(StrictOutput):
    """Versioned hypothetical scenario definition."""

    scenario_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=200)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    shocks: tuple[ScenarioShockView, ...]
    assumptions: tuple[str, ...]
    hypothetical: Literal[True]


class ScenarioCatalogOutput(StrictOutput):
    """Bounded scenario-catalog tool response."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    scope: Literal["demo"] = "demo"
    is_synthetic: Literal[True] = True
    not_investment_advice: Literal[True] = True
    scenarios: tuple[ScenarioView, ...]
    count: int = Field(ge=0, le=20)
