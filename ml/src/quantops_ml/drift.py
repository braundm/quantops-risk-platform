"""Operational PSI and regime-proportion drift monitoring for demo windows."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from quantops_ml.candidate import KMeansCandidate
from quantops_ml.types import EVALUATED_REGIMES, FEATURE_SCHEMA, FeatureRow


@dataclass(frozen=True, slots=True)
class DriftThresholds:
    feature_psi: float = 0.25
    missing_ratio_change: float = 0.05
    regime_js_divergence: float = 0.10

    def to_mapping(self) -> dict[str, float]:
        return {
            "feature_psi": self.feature_psi,
            "missing_ratio_change": self.missing_ratio_change,
            "regime_js_divergence": self.regime_js_divergence,
        }


DEFAULT_DRIFT_THRESHOLDS = DriftThresholds()


@dataclass(frozen=True, slots=True)
class DriftReport:
    status: str
    reference_window: dict[str, object]
    current_window: dict[str, object]
    feature_psi: dict[str, float]
    missing_ratio_change: float
    regime_js_divergence: float
    thresholds: DriftThresholds
    synthetic_perturbation: bool

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reference_window": self.reference_window,
            "current_window": self.current_window,
            "feature_psi": self.feature_psi,
            "missing_ratio_change": self.missing_ratio_change,
            "regime_js_divergence": self.regime_js_divergence,
            "thresholds": self.thresholds.to_mapping(),
            "synthetic_perturbation": self.synthetic_perturbation,
            "interpretation": (
                "PSI and Jensen-Shannon thresholds indicate operational change, not statistical "
                "significance, causality, or market direction."
            ),
            "statistical_significance_test": None,
        }


def monitor_drift(
    reference: tuple[FeatureRow, ...],
    current: tuple[FeatureRow, ...],
    model: KMeansCandidate,
    *,
    thresholds: DriftThresholds = DEFAULT_DRIFT_THRESHOLDS,
    synthetic_perturbation: bool = False,
) -> DriftReport:
    if len(reference) < 20 or len(current) < 20:
        raise ValueError("drift windows each require at least 20 rows")
    feature_psi = {
        name: population_stability_index(
            [row.values[index] for row in reference],
            [row.values[index] for row in current],
        )
        for index, name in enumerate(FEATURE_SCHEMA.names)
    }
    missing_index = FEATURE_SCHEMA.names.index("missing_observation_ratio_20d")
    missing_change = abs(
        statistics.fmean(row.values[missing_index] for row in current)
        - statistics.fmean(row.values[missing_index] for row in reference)
    )
    reference_proportions = _regime_proportions(model, reference)
    current_proportions = _regime_proportions(model, current)
    regime_js = jensen_shannon_divergence(reference_proportions, current_proportions)
    drifted = (
        any(value >= thresholds.feature_psi for value in feature_psi.values())
        or missing_change >= thresholds.missing_ratio_change
        or regime_js >= thresholds.regime_js_divergence
    )
    return DriftReport(
        status="operational_drift_detected" if drifted else "within_operational_thresholds",
        reference_window=_window(reference),
        current_window=_window(current),
        feature_psi=feature_psi,
        missing_ratio_change=missing_change,
        regime_js_divergence=regime_js,
        thresholds=thresholds,
        synthetic_perturbation=synthetic_perturbation,
    )


def synthetic_drift_rows(rows: tuple[FeatureRow, ...]) -> tuple[FeatureRow, ...]:
    """Create an explicit non-market perturbation used only to demonstrate monitoring."""

    result: list[FeatureRow] = []
    for row in rows:
        values = list(row.values)
        for index in (0, 1, 2, 3):
            values[index] *= 1.8
        values[4] = max(values[4], 0.82)
        values[5] = min(0.95, values[5] + 0.10)
        values[6] += 0.03
        values[7] *= 1.5
        values[8] += 1.2
        values[9] = 0.12
        result.append(
            FeatureRow(
                as_of=row.as_of,
                max_input_date=row.max_input_date,
                values=tuple(values),
                known_regime=row.known_regime,
                source_regime=row.source_regime,
                is_synthetic=True,
            )
        )
    return tuple(result)


def population_stability_index(
    reference: list[float],
    current: list[float],
    bins: int = 10,
) -> float:
    if len(reference) < 2 or len(current) < 2 or bins < 2:
        raise ValueError("PSI requires two non-trivial samples and at least two bins")
    sorted_reference = sorted(reference)
    edges = sorted({_quantile(sorted_reference, index / bins) for index in range(1, bins)})
    reference_counts = _bin_counts(reference, edges)
    current_counts = _bin_counts(current, edges)
    epsilon = 1e-6
    result = 0.0
    for reference_count, current_count in zip(reference_counts, current_counts, strict=True):
        reference_ratio = max(reference_count / len(reference), epsilon)
        current_ratio = max(current_count / len(current), epsilon)
        result += (current_ratio - reference_ratio) * math.log(current_ratio / reference_ratio)
    return result


def jensen_shannon_divergence(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Jensen-Shannon inputs must have equal non-zero length")
    if not math.isclose(sum(left), 1.0, abs_tol=1e-9) or not math.isclose(
        sum(right), 1.0, abs_tol=1e-9
    ):
        raise ValueError("Jensen-Shannon inputs must each sum to one")
    midpoint = [
        (left_value + right_value) / 2.0
        for left_value, right_value in zip(left, right, strict=True)
    ]
    return 0.5 * _kl_divergence(left, midpoint) + 0.5 * _kl_divergence(right, midpoint)


def _regime_proportions(model: KMeansCandidate, rows: tuple[FeatureRow, ...]) -> list[float]:
    predictions = model.predict_many(rows)
    return [
        sum(prediction.label is regime for prediction in predictions) / len(predictions)
        for regime in EVALUATED_REGIMES
    ]


def _kl_divergence(left: list[float], right: list[float]) -> float:
    return sum(
        0.0 if left_value == 0 else left_value * math.log(left_value / right_value, 2)
        for left_value, right_value in zip(left, right, strict=True)
    )


def _bin_counts(values: list[float], edges: list[float]) -> list[int]:
    counts = [0] * (len(edges) + 1)
    for value in values:
        index = 0
        while index < len(edges) and value > edges[index]:
            index += 1
        counts[index] += 1
    return counts


def _quantile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return (sorted_values[lower] * (1.0 - weight)) + (sorted_values[upper] * weight)


def _window(rows: tuple[FeatureRow, ...]) -> dict[str, object]:
    return {
        "rows": len(rows),
        "start": rows[0].as_of.isoformat(),
        "end": rows[-1].as_of.isoformat(),
    }
