"""Automated demo promotion gates with no fictitious human approval."""

from __future__ import annotations

from dataclasses import dataclass

from quantops_ml.metrics import ClassificationMetrics
from quantops_ml.types import FEATURE_SCHEMA, RiskRegime


@dataclass(frozen=True, slots=True)
class PromotionPolicy:
    minimum_baseline_relative_macro_f1: float = -0.02
    maximum_expected_calibration_error: float = 0.30

    def to_mapping(self) -> dict[str, float]:
        return {
            "minimum_baseline_relative_macro_f1": self.minimum_baseline_relative_macro_f1,
            "maximum_expected_calibration_error": self.maximum_expected_calibration_error,
        }


DEFAULT_PROMOTION_POLICY = PromotionPolicy()


@dataclass(frozen=True, slots=True)
class GateResult:
    name: str
    passed: bool
    observed: object
    expected: object

    def to_mapping(self) -> dict[str, object]:
        return {
            "name": self.name,
            "passed": self.passed,
            "observed": self.observed,
            "expected": self.expected,
        }


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    status: str
    automated_by_policy: bool
    gates: tuple[GateResult, ...]
    policy: PromotionPolicy
    fallback: str

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status,
            "automated_by_policy": self.automated_by_policy,
            "human_approval_claimed": False,
            "gates": [gate.to_mapping() for gate in self.gates],
            "policy": self.policy.to_mapping(),
            "fallback": self.fallback,
        }


def evaluate_promotion(
    *,
    model_feature_schema_version: str,
    baseline_test: ClassificationMetrics,
    candidate_test: ClassificationMetrics,
    leakage_check_passed: bool,
    deterministic_inference_passed: bool,
    missing_data_label: RiskRegime,
    model_card_complete: bool,
    policy: PromotionPolicy = DEFAULT_PROMOTION_POLICY,
) -> PromotionDecision:
    relative_f1 = candidate_test.macro_f1 - baseline_test.macro_f1
    gates = (
        GateResult(
            "feature_schema_compatibility",
            model_feature_schema_version == FEATURE_SCHEMA.version,
            model_feature_schema_version,
            FEATURE_SCHEMA.version,
        ),
        GateResult(
            "baseline_relative_macro_f1",
            relative_f1 >= policy.minimum_baseline_relative_macro_f1,
            relative_f1,
            f">= {policy.minimum_baseline_relative_macro_f1}",
        ),
        GateResult(
            "calibration_error",
            candidate_test.expected_calibration_error <= policy.maximum_expected_calibration_error,
            candidate_test.expected_calibration_error,
            f"<= {policy.maximum_expected_calibration_error}",
        ),
        GateResult("point_in_time_leakage_check", leakage_check_passed, leakage_check_passed, True),
        GateResult(
            "deterministic_inference",
            deterministic_inference_passed,
            deterministic_inference_passed,
            True,
        ),
        GateResult(
            "missing_data_behavior",
            missing_data_label is RiskRegime.INSUFFICIENT_DATA,
            missing_data_label.value,
            RiskRegime.INSUFFICIENT_DATA.value,
        ),
        GateResult("model_card_completeness", model_card_complete, model_card_complete, True),
    )
    passed = all(gate.passed for gate in gates)
    return PromotionDecision(
        status=(
            "approved_by_automated_demo_policy" if passed else "rejected_by_automated_demo_policy"
        ),
        automated_by_policy=True,
        gates=gates,
        policy=policy,
        fallback="rule-baseline-v1 remains the active deterministic classifier",
    )
