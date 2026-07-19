"""Shared immutable types for leakage-safe risk-regime classification."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class RiskRegime(StrEnum):
    NORMAL = "normal"
    ELEVATED_VOLATILITY = "elevated_volatility"
    STRESS = "stress"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    INSUFFICIENT_DATA = "insufficient_data"


EVALUATED_REGIMES: tuple[RiskRegime, ...] = (
    RiskRegime.NORMAL,
    RiskRegime.ELEVATED_VOLATILITY,
    RiskRegime.STRESS,
    RiskRegime.CORRELATION_BREAKDOWN,
)


KNOWN_SYNTHETIC_REGIME_MAP: Mapping[str, RiskRegime] = {
    "normal": RiskRegime.NORMAL,
    "risk_on": RiskRegime.NORMAL,
    "volatility_shock": RiskRegime.STRESS,
    "correlation_breakdown": RiskRegime.CORRELATION_BREAKDOWN,
    "partial_recovery": RiskRegime.ELEVATED_VOLATILITY,
}


@dataclass(frozen=True, slots=True)
class FeatureSchema:
    version: str
    names: tuple[str, ...]
    description: str

    def to_mapping(self) -> dict[str, object]:
        return {
            "version": self.version,
            "names": list(self.names),
            "description": self.description,
        }


FEATURE_SCHEMA = FeatureSchema(
    version="risk-regime-features-v1",
    names=(
        "qtech_volatility_20d",
        "qgold_volatility_20d",
        "qwti_volatility_20d",
        "portfolio_volatility_20d",
        "mean_pairwise_correlation_20d",
        "portfolio_drawdown_60d",
        "drawdown_velocity_5d",
        "cross_sectional_dispersion_1d",
        "mean_volume_zscore_20d",
        "missing_observation_ratio_20d",
    ),
    description=(
        "End-of-day risk features computed only from observations available on or before as_of."
    ),
)


@dataclass(frozen=True, slots=True)
class FeatureRow:
    as_of: date
    max_input_date: date
    values: tuple[float, ...]
    known_regime: RiskRegime
    source_regime: str
    is_synthetic: bool

    def __post_init__(self) -> None:
        if len(self.values) != len(FEATURE_SCHEMA.names):
            raise ValueError("feature vector length does not match the feature schema")
        if self.max_input_date > self.as_of:
            raise ValueError("feature row contains future input")

    def value(self, name: str) -> float:
        try:
            index = FEATURE_SCHEMA.names.index(name)
        except ValueError as error:
            raise KeyError(name) from error
        return self.values[index]

    def to_mapping(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "max_input_date": self.max_input_date.isoformat(),
            "features": dict(zip(FEATURE_SCHEMA.names, self.values, strict=True)),
            "known_regime": self.known_regime.value,
            "source_regime": self.source_regime,
            "is_synthetic": self.is_synthetic,
        }


@dataclass(frozen=True, slots=True)
class Prediction:
    label: RiskRegime
    confidence: float
    reason: str
    cluster_id: int | None = None

    def to_mapping(self) -> dict[str, object]:
        return {
            "label": self.label.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "cluster_id": self.cluster_id,
        }
