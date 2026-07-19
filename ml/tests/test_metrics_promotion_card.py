"""Metric semantics, promotion gates, and model-card tests."""

from __future__ import annotations

import pytest

from quantops_ml.evaluation import EvaluationBundle
from quantops_ml.metrics import adjusted_rand_index, classification_metrics
from quantops_ml.model_card import model_card_complete, render_model_card
from quantops_ml.promotion import PromotionPolicy, evaluate_promotion
from quantops_ml.types import EVALUATED_REGIMES, FEATURE_SCHEMA, Prediction, RiskRegime

from .helpers import metrics


def test_perfect_metrics_are_one_and_include_all_declared_labels() -> None:
    truth = EVALUATED_REGIMES
    predictions = tuple(Prediction(label, 1.0, "perfect") for label in truth)
    result = classification_metrics(truth, predictions)
    assert result.accuracy == 1.0
    assert result.macro_f1 == 1.0
    assert result.adjusted_rand_index == 1.0
    assert result.stress_false_negative_rate == 0.0
    assert result.expected_calibration_error == 0.0
    assert result.to_mapping()["macro_average_labels"] == [
        label.value for label in EVALUATED_REGIMES
    ]


def test_metrics_are_honest_when_stress_is_absent_and_confidence_is_bounded() -> None:
    truth = (RiskRegime.NORMAL, RiskRegime.NORMAL)
    predictions = (
        Prediction(RiskRegime.NORMAL, 2.0, "clamped only for calibration"),
        Prediction(RiskRegime.STRESS, -1.0, "clamped only for calibration"),
    )
    result = classification_metrics(truth, predictions, calibration_bins=2)
    assert result.stress_false_negative_rate is None
    assert result.accuracy == 0.5
    assert result.macro_f1 < result.accuracy
    assert 0.0 <= result.expected_calibration_error <= 1.0
    assert result.mean_confidence == 0.5


@pytest.mark.parametrize(
    ("truth", "predictions", "message"),
    [
        ((), (), "equal non-zero"),
        ((RiskRegime.NORMAL,), (), "equal non-zero"),
    ],
)
def test_metric_input_validation(
    truth: tuple[RiskRegime, ...],
    predictions: tuple[Prediction, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        classification_metrics(truth, predictions)
    with pytest.raises(ValueError, match="equal non-zero"):
        adjusted_rand_index(truth, tuple(item.label for item in predictions))


def test_metric_configuration_and_degenerate_ari() -> None:
    truth = (RiskRegime.NORMAL, RiskRegime.NORMAL)
    predictions = tuple(Prediction(label, 0.5, "unit") for label in truth)
    with pytest.raises(ValueError, match="at least two"):
        classification_metrics(truth, predictions, calibration_bins=1)
    assert adjusted_rand_index(truth, truth) == 1.0
    assert (
        adjusted_rand_index(
            truth,
            (RiskRegime.STRESS, RiskRegime.STRESS),
        )
        == 1.0
    )


def test_promotion_passes_only_when_every_automated_gate_passes() -> None:
    approved = evaluate_promotion(
        model_feature_schema_version=FEATURE_SCHEMA.version,
        baseline_test=metrics(macro_f1=0.70, calibration_error=0.20),
        candidate_test=metrics(macro_f1=0.71, calibration_error=0.20),
        leakage_check_passed=True,
        deterministic_inference_passed=True,
        missing_data_label=RiskRegime.INSUFFICIENT_DATA,
        model_card_complete=True,
    )
    assert approved.status == "approved_by_automated_demo_policy"
    assert all(gate.passed for gate in approved.gates)
    assert approved.to_mapping()["human_approval_claimed"] is False
    rejected = evaluate_promotion(
        model_feature_schema_version="wrong-schema",
        baseline_test=metrics(macro_f1=0.70, calibration_error=0.20),
        candidate_test=metrics(macro_f1=0.40, calibration_error=0.50),
        leakage_check_passed=False,
        deterministic_inference_passed=False,
        missing_data_label=RiskRegime.NORMAL,
        model_card_complete=False,
        policy=PromotionPolicy(),
    )
    assert rejected.status == "rejected_by_automated_demo_policy"
    assert not all(gate.passed for gate in rejected.gates)
    assert rejected.fallback == "rule-baseline-v1 remains the active deterministic classifier"


def test_model_card_is_complete_and_prohibits_forecasting_claims(
    evaluation: EvaluationBundle,
) -> None:
    draft = render_model_card(evaluation, "a" * 64, None)
    assert model_card_complete(draft)
    assert "pending automated policy evaluation" in draft
    lower = " ".join(draft.lower().split())
    assert "does not predict prices or returns" in lower
    assert "does not" in lower and "optimize profit" in lower
    assert "investment advice" in lower
    assert "not a calibrated probability" in lower
    assert not model_card_complete("# incomplete")
