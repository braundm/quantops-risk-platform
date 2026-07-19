"""Versioned transparent rule baseline for synthetic risk regimes."""

from __future__ import annotations

import math
from dataclasses import dataclass

from quantops_ml.types import FeatureRow, Prediction, RiskRegime

BASELINE_VERSION = "rule-baseline-v1"


@dataclass(frozen=True, slots=True)
class BaselineThresholds:
    stress_volatility: float = 0.34
    stress_drawdown: float = 0.14
    stress_drawdown_velocity: float = 0.045
    correlation_level: float = 0.58
    correlation_minimum_volatility: float = 0.12
    elevated_volatility: float = 0.14
    elevated_drawdown: float = 0.05
    elevated_volume_zscore: float = 1.40
    maximum_missing_ratio: float = 0.20

    def to_mapping(self) -> dict[str, float]:
        return {
            "stress_volatility": self.stress_volatility,
            "stress_drawdown": self.stress_drawdown,
            "stress_drawdown_velocity": self.stress_drawdown_velocity,
            "correlation_level": self.correlation_level,
            "correlation_minimum_volatility": self.correlation_minimum_volatility,
            "elevated_volatility": self.elevated_volatility,
            "elevated_drawdown": self.elevated_drawdown,
            "elevated_volume_zscore": self.elevated_volume_zscore,
            "maximum_missing_ratio": self.maximum_missing_ratio,
        }


DEFAULT_BASELINE_THRESHOLDS = BaselineThresholds()


class RuleBaseline:
    """Explainable classification based on observable risk-state thresholds."""

    version = BASELINE_VERSION

    def __init__(self, thresholds: BaselineThresholds = DEFAULT_BASELINE_THRESHOLDS) -> None:
        self.thresholds = thresholds

    def classify(self, row: FeatureRow | None) -> Prediction:
        if row is None or not all(math.isfinite(value) for value in row.values):
            return Prediction(
                RiskRegime.INSUFFICIENT_DATA,
                1.0,
                "missing or non-finite feature vector",
            )
        volatility = row.value("portfolio_volatility_20d")
        correlation = row.value("mean_pairwise_correlation_20d")
        drawdown = row.value("portfolio_drawdown_60d")
        drawdown_velocity = row.value("drawdown_velocity_5d")
        volume_zscore = row.value("mean_volume_zscore_20d")
        missing_ratio = row.value("missing_observation_ratio_20d")
        if missing_ratio > self.thresholds.maximum_missing_ratio:
            return Prediction(
                RiskRegime.INSUFFICIENT_DATA,
                0.99,
                "missing-observation ratio exceeds the versioned quality threshold",
            )
        if (
            volatility >= self.thresholds.stress_volatility
            or drawdown >= self.thresholds.stress_drawdown
            or drawdown_velocity >= self.thresholds.stress_drawdown_velocity
        ):
            return Prediction(
                RiskRegime.STRESS,
                0.90,
                "stress volatility, drawdown, or drawdown-velocity threshold crossed",
            )
        if (
            correlation >= self.thresholds.correlation_level
            and volatility >= self.thresholds.correlation_minimum_volatility
        ):
            return Prediction(
                RiskRegime.CORRELATION_BREAKDOWN,
                0.86,
                "high shared correlation with non-trivial portfolio volatility",
            )
        if (
            volatility >= self.thresholds.elevated_volatility
            or drawdown >= self.thresholds.elevated_drawdown
            or volume_zscore >= self.thresholds.elevated_volume_zscore
        ):
            return Prediction(
                RiskRegime.ELEVATED_VOLATILITY,
                0.78,
                "elevated volatility, drawdown, or volume anomaly threshold crossed",
            )
        return Prediction(
            RiskRegime.NORMAL,
            0.74,
            "no elevated, stress, correlation, or quality threshold crossed",
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "version": self.version,
            "thresholds": self.thresholds.to_mapping(),
            "classification_order": [
                "insufficient_data",
                "stress",
                "correlation_breakdown",
                "elevated_volatility",
                "normal",
            ],
            "intended_use": "risk-regime classification only",
        }
