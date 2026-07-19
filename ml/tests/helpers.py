"""Small typed constructors used by focused unit tests."""

from __future__ import annotations

from datetime import date

from quantops_ml.metrics import ClassificationMetrics
from quantops_ml.types import FEATURE_SCHEMA, FeatureRow, RiskRegime


def feature_row(**overrides: float) -> FeatureRow:
    values = {name: 0.0 for name in FEATURE_SCHEMA.names}
    values["mean_pairwise_correlation_20d"] = 0.10
    values.update(overrides)
    return FeatureRow(
        as_of=date(2026, 1, 2),
        max_input_date=date(2026, 1, 2),
        values=tuple(values[name] for name in FEATURE_SCHEMA.names),
        known_regime=RiskRegime.NORMAL,
        source_regime="unit_test",
        is_synthetic=True,
    )


def metrics(*, macro_f1: float, calibration_error: float) -> ClassificationMetrics:
    matrix = {
        regime.value: {
            predicted.value: 0 for predicted in RiskRegime if predicted.value != "insufficient_data"
        }
        for regime in RiskRegime
        if regime.value != "insufficient_data"
    }
    return ClassificationMetrics(
        sample_count=10,
        accuracy=macro_f1,
        macro_f1=macro_f1,
        adjusted_rand_index=macro_f1,
        stress_false_negative_rate=0.0,
        expected_calibration_error=calibration_error,
        mean_confidence=0.75,
        confusion_matrix=matrix,
    )
