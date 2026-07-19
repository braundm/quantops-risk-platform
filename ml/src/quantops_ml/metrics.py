"""Honest classification and calibration metrics without external dependencies."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from quantops_ml.types import EVALUATED_REGIMES, Prediction, RiskRegime


@dataclass(frozen=True, slots=True)
class ClassificationMetrics:
    sample_count: int
    accuracy: float
    macro_f1: float
    adjusted_rand_index: float
    stress_false_negative_rate: float | None
    expected_calibration_error: float
    mean_confidence: float
    confusion_matrix: dict[str, dict[str, int]]

    def to_mapping(self) -> dict[str, object]:
        return {
            "sample_count": self.sample_count,
            "accuracy": self.accuracy,
            "macro_f1": self.macro_f1,
            "adjusted_rand_index": self.adjusted_rand_index,
            "stress_false_negative_rate": self.stress_false_negative_rate,
            "expected_calibration_error": self.expected_calibration_error,
            "mean_confidence": self.mean_confidence,
            "confusion_matrix": self.confusion_matrix,
            "macro_average_labels": [label.value for label in EVALUATED_REGIMES],
        }


def classification_metrics(
    truth: tuple[RiskRegime, ...],
    predictions: tuple[Prediction, ...],
    calibration_bins: int = 10,
) -> ClassificationMetrics:
    if not truth or len(truth) != len(predictions):
        raise ValueError("truth and predictions must have equal non-zero length")
    if calibration_bins < 2:
        raise ValueError("calibration_bins must be at least two")
    predicted = tuple(item.label for item in predictions)
    matrix = {
        true_label.value: {predicted_label.value: 0 for predicted_label in EVALUATED_REGIMES}
        for true_label in EVALUATED_REGIMES
    }
    for expected, actual in zip(truth, predicted, strict=True):
        if expected in EVALUATED_REGIMES and actual in EVALUATED_REGIMES:
            matrix[expected.value][actual.value] += 1
    correct = sum(expected == actual for expected, actual in zip(truth, predicted, strict=True))
    f1_values: list[float] = []
    for label in EVALUATED_REGIMES:
        true_positive = sum(
            expected == label and actual == label
            for expected, actual in zip(truth, predicted, strict=True)
        )
        false_positive = sum(
            expected != label and actual == label
            for expected, actual in zip(truth, predicted, strict=True)
        )
        false_negative = sum(
            expected == label and actual != label
            for expected, actual in zip(truth, predicted, strict=True)
        )
        denominator = (2 * true_positive) + false_positive + false_negative
        f1_values.append(0.0 if denominator == 0 else (2 * true_positive) / denominator)
    stress_count = sum(label is RiskRegime.STRESS for label in truth)
    stress_false_negatives = sum(
        expected is RiskRegime.STRESS and actual is not RiskRegime.STRESS
        for expected, actual in zip(truth, predicted, strict=True)
    )
    stress_fnr = None if stress_count == 0 else stress_false_negatives / stress_count
    return ClassificationMetrics(
        sample_count=len(truth),
        accuracy=correct / len(truth),
        macro_f1=statistics.fmean(f1_values),
        adjusted_rand_index=adjusted_rand_index(truth, predicted),
        stress_false_negative_rate=stress_fnr,
        expected_calibration_error=_expected_calibration_error(
            truth,
            predictions,
            calibration_bins,
        ),
        mean_confidence=statistics.fmean(item.confidence for item in predictions),
        confusion_matrix=matrix,
    )


def adjusted_rand_index(
    truth: tuple[RiskRegime, ...],
    predicted: tuple[RiskRegime, ...],
) -> float:
    if len(truth) != len(predicted) or not truth:
        raise ValueError("ARI inputs must have equal non-zero length")
    true_labels = sorted(set(truth), key=lambda label: label.value)
    predicted_labels = sorted(set(predicted), key=lambda label: label.value)
    contingency = {
        (true_label, predicted_label): sum(
            expected == true_label and actual == predicted_label
            for expected, actual in zip(truth, predicted, strict=True)
        )
        for true_label in true_labels
        for predicted_label in predicted_labels
    }
    sum_combined = sum(_combination_two(value) for value in contingency.values())
    true_sums = [
        sum(contingency[(label, predicted_label)] for predicted_label in predicted_labels)
        for label in true_labels
    ]
    predicted_sums = [
        sum(contingency[(true_label, label)] for true_label in true_labels)
        for label in predicted_labels
    ]
    total_pairs = _combination_two(len(truth))
    if total_pairs == 0:
        return 1.0
    true_pairs = sum(_combination_two(value) for value in true_sums)
    predicted_pairs = sum(_combination_two(value) for value in predicted_sums)
    expected_index = (true_pairs * predicted_pairs) / total_pairs
    maximum_index = 0.5 * (true_pairs + predicted_pairs)
    denominator = maximum_index - expected_index
    if math.isclose(denominator, 0.0, abs_tol=1e-15):
        return 1.0 if _same_partition(truth, predicted) else 0.0
    return (sum_combined - expected_index) / denominator


def _expected_calibration_error(
    truth: tuple[RiskRegime, ...],
    predictions: tuple[Prediction, ...],
    bins: int,
) -> float:
    grouped: list[list[tuple[bool, float]]] = [[] for _ in range(bins)]
    for expected, prediction in zip(truth, predictions, strict=True):
        confidence = min(max(prediction.confidence, 0.0), 1.0)
        index = min(int(confidence * bins), bins - 1)
        grouped[index].append((expected == prediction.label, confidence))
    total = len(truth)
    error = 0.0
    for entries in grouped:
        if not entries:
            continue
        accuracy = sum(correct for correct, _ in entries) / len(entries)
        confidence = statistics.fmean(value for _, value in entries)
        error += (len(entries) / total) * abs(accuracy - confidence)
    return error


def _combination_two(value: int) -> int:
    return (value * (value - 1)) // 2


def _same_partition(
    truth: tuple[RiskRegime, ...],
    predicted: tuple[RiskRegime, ...],
) -> bool:
    return all(
        (truth[left] == truth[right]) == (predicted[left] == predicted[right])
        for left in range(len(truth))
        for right in range(left + 1, len(truth))
    )
