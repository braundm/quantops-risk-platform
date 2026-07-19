"""Operational drift behavior without significance or market claims."""

from __future__ import annotations

import pytest

from quantops_ml.drift import (
    jensen_shannon_divergence,
    monitor_drift,
    population_stability_index,
    synthetic_drift_rows,
)
from quantops_ml.evaluation import EvaluationBundle
from quantops_ml.types import FeatureRow


def test_population_stability_index_is_zero_for_identical_samples() -> None:
    sample = [float(index) for index in range(100)]
    assert population_stability_index(sample, sample) == pytest.approx(0.0)
    shifted = [value + 100.0 for value in sample]
    assert population_stability_index(sample, shifted) > 0.25


def test_jensen_shannon_divergence_bounds_and_symmetry() -> None:
    left = [1.0, 0.0, 0.0, 0.0]
    right = [0.0, 1.0, 0.0, 0.0]
    assert jensen_shannon_divergence(left, left) == 0.0
    assert jensen_shannon_divergence(left, right) == pytest.approx(1.0)
    assert jensen_shannon_divergence(left, right) == jensen_shannon_divergence(right, left)


@pytest.mark.parametrize(
    ("left", "right", "message"),
    [
        ([1.0], [], "equal non-zero"),
        ([0.4, 0.4], [0.5, 0.5], "sum to one"),
    ],
)
def test_jensen_shannon_validation(
    left: list[float],
    right: list[float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        jensen_shannon_divergence(left, right)


def test_psi_validation() -> None:
    with pytest.raises(ValueError, match="non-trivial"):
        population_stability_index([1.0], [1.0])
    with pytest.raises(ValueError, match="at least two bins"):
        population_stability_index([1.0, 2.0], [1.0, 2.0], bins=1)


def test_monitor_identical_window_is_stable_and_demo_is_detected(
    evaluation: EvaluationBundle,
) -> None:
    reference = evaluation.split.train[-80:]
    observed = monitor_drift(reference, reference, evaluation.selected_run.model)
    assert observed.status == "within_operational_thresholds"
    assert all(value == pytest.approx(0.0) for value in observed.feature_psi.values())
    assert observed.regime_js_divergence == 0.0
    assert observed.synthetic_perturbation is False

    shifted_rows = synthetic_drift_rows(evaluation.split.test)
    shifted = monitor_drift(
        reference,
        shifted_rows,
        evaluation.selected_run.model,
        synthetic_perturbation=True,
    )
    assert shifted.status == "operational_drift_detected"
    assert shifted.synthetic_perturbation is True
    mapping = shifted.to_mapping()
    assert mapping["statistical_significance_test"] is None
    interpretation = str(mapping["interpretation"])
    assert "not statistical significance" in interpretation
    assert "not" in interpretation and "market direction" in interpretation


def test_monitor_requires_meaningful_windows(
    evaluation: EvaluationBundle,
    feature_rows: tuple[FeatureRow, ...],
) -> None:
    with pytest.raises(ValueError, match="at least 20"):
        monitor_drift(
            feature_rows[:19],
            feature_rows[-20:],
            evaluation.selected_run.model,
        )
