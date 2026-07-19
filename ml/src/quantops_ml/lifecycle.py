"""End-to-end deterministic synthetic risk-regime lifecycle orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from quantops_ml.artifacts import (
    ArtifactWriteResult,
    canonical_json_bytes,
    write_lifecycle_artifacts,
)
from quantops_ml.baseline import RuleBaseline
from quantops_ml.candidate import CandidateConfig, fit_candidate
from quantops_ml.data import load_synthetic_dataset
from quantops_ml.drift import DriftThresholds, monitor_drift, synthetic_drift_rows
from quantops_ml.evaluation import (
    DEFAULT_SEEDS,
    EvaluationBundle,
    SplitConfig,
    evaluate_fixed_seeds,
)
from quantops_ml.features import FeatureConfig, assert_point_in_time, build_point_in_time_features
from quantops_ml.model_card import model_card_complete, render_model_card
from quantops_ml.promotion import PromotionDecision, PromotionPolicy, evaluate_promotion
from quantops_ml.tracking import TrackingStatus, track_with_optional_mlflow
from quantops_ml.types import FEATURE_SCHEMA


@dataclass(frozen=True, slots=True)
class LifecycleConfig:
    seeds: tuple[int, ...] = DEFAULT_SEEDS
    feature: FeatureConfig = field(default_factory=FeatureConfig)
    split: SplitConfig = field(default_factory=SplitConfig)
    candidate: CandidateConfig = field(default_factory=CandidateConfig)
    promotion: PromotionPolicy = field(default_factory=PromotionPolicy)
    drift: DriftThresholds = field(default_factory=DriftThresholds)

    def to_mapping(self) -> dict[str, object]:
        return {
            "seeds": list(self.seeds),
            "feature": self.feature.to_mapping(),
            "split": self.split.to_mapping(),
            "candidate": self.candidate.to_mapping(),
            "promotion": self.promotion.to_mapping(),
            "drift": self.drift.to_mapping(),
        }


DEFAULT_LIFECYCLE_CONFIG = LifecycleConfig()


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    feature_rows: int
    selected_seed: int
    promotion_status: str
    drift_status: str
    tracking_status: str
    artifacts: ArtifactWriteResult

    def to_mapping(self) -> dict[str, object]:
        return {
            "feature_rows": self.feature_rows,
            "selected_seed": self.selected_seed,
            "promotion_status": self.promotion_status,
            "drift_status": self.drift_status,
            "tracking_status": self.tracking_status,
            "artifacts": self.artifacts.to_mapping(),
        }


def run_lifecycle(
    prices_path: Path,
    dataset_manifest_path: Path,
    output_dir: Path,
    *,
    config: LifecycleConfig = DEFAULT_LIFECYCLE_CONFIG,
    enable_mlflow: bool = False,
    mlflow_tracking_uri: str | None = None,
    code_revision: str = "not_recorded_git_cli_unavailable",
) -> LifecycleResult:
    dataset = load_synthetic_dataset(prices_path, dataset_manifest_path)
    features = build_point_in_time_features(dataset, config.feature)
    assert_point_in_time(features)
    baseline = RuleBaseline()
    evaluation = evaluate_fixed_seeds(
        features,
        baseline,
        config.seeds,
        config.split,
        config.candidate,
    )
    selected = evaluation.selected_run
    repeated_model = fit_candidate(
        evaluation.split.train,
        selected.seed,
        baseline,
        config.candidate,
    )
    deterministic = canonical_json_bytes(repeated_model.to_mapping()) == canonical_json_bytes(
        selected.model.to_mapping()
    ) and repeated_model.predict_many(evaluation.split.test) == selected.model.predict_many(
        evaluation.split.test
    )
    draft_card = render_model_card(evaluation, dataset.dataset_hash, None)
    promotion = evaluate_promotion(
        model_feature_schema_version=FEATURE_SCHEMA.version,
        baseline_test=evaluation.baseline_test,
        candidate_test=selected.test_metrics,
        leakage_check_passed=all(row.max_input_date <= row.as_of for row in features),
        deterministic_inference_passed=deterministic,
        missing_data_label=selected.model.predict(None).label,
        model_card_complete=model_card_complete(draft_card),
        policy=config.promotion,
    )
    card = render_model_card(evaluation, dataset.dataset_hash, promotion)
    observed_drift = monitor_drift(
        evaluation.split.train,
        evaluation.split.test,
        selected.model,
        thresholds=config.drift,
    )
    drift_demo = monitor_drift(
        evaluation.split.train,
        synthetic_drift_rows(evaluation.split.test),
        selected.model,
        thresholds=config.drift,
        synthetic_perturbation=True,
    )
    tracking = _tracking_status_without_side_effect(enable_mlflow)
    experiment_report = _experiment_report(
        dataset.dataset_hash,
        dataset.source_sha256,
        len(features),
        config,
        baseline,
        evaluation,
        promotion,
        tracking,
        code_revision,
    )
    json_artifacts: dict[str, object] = {
        "config.json": config.to_mapping(),
        "feature_schema.json": FEATURE_SCHEMA.to_mapping(),
        "evaluation_report.json": experiment_report,
        "model_artifact.json": selected.model.to_mapping()
        | {
            "dataset_hash": dataset.dataset_hash,
            "code_revision": code_revision,
            "serialization_version": "quantops-ml-artifact-v1",
        },
        "promotion.json": promotion.to_mapping(),
        "drift_observed.json": observed_drift.to_mapping(),
        "drift_demo.json": drift_demo.to_mapping(),
        "tracking_status.json": tracking.to_mapping(),
    }
    artifact_result = write_lifecycle_artifacts(
        output_dir,
        json_artifacts,
        {"model_card.md": card},
    )
    if enable_mlflow:
        tracking = track_with_optional_mlflow(
            enabled=True,
            tracking_uri=mlflow_tracking_uri,
            experiment_name="quantops-synthetic-risk-regimes",
            parameters={
                "selected_seed": selected.seed,
                "feature_schema_version": FEATURE_SCHEMA.version,
                "dataset_hash": dataset.dataset_hash,
            },
            metrics={
                "validation_macro_f1": selected.validation_metrics.macro_f1,
                "test_macro_f1": selected.test_metrics.macro_f1,
                "test_calibration_error": selected.test_metrics.expected_calibration_error,
            },
            artifact_dir=output_dir,
        )
        json_artifacts["tracking_status.json"] = tracking.to_mapping()
        experiment_report["tracking"] = tracking.to_mapping()
        json_artifacts["evaluation_report.json"] = experiment_report
        artifact_result = write_lifecycle_artifacts(
            output_dir,
            json_artifacts,
            {"model_card.md": card},
        )
    return LifecycleResult(
        feature_rows=len(features),
        selected_seed=selected.seed,
        promotion_status=promotion.status,
        drift_status=observed_drift.status,
        tracking_status=tracking.status,
        artifacts=artifact_result,
    )


def _tracking_status_without_side_effect(enabled: bool) -> TrackingStatus:
    if enabled:
        return TrackingStatus(
            provider="mlflow",
            status="pending_explicit_adapter_call",
            enabled=True,
            detail="Artifacts are written locally before the optional MLflow adapter runs.",
        )
    return track_with_optional_mlflow(
        enabled=False,
        tracking_uri=None,
        experiment_name="quantops-synthetic-risk-regimes",
        parameters={},
        metrics={},
        artifact_dir=Path(),
    )


def _experiment_report(
    dataset_hash: str,
    source_sha256: str,
    feature_rows: int,
    config: LifecycleConfig,
    baseline: RuleBaseline,
    evaluation: EvaluationBundle,
    promotion: PromotionDecision,
    tracking: TrackingStatus,
    code_revision: str,
) -> dict[str, object]:
    partitions = (
        evaluation.split.train,
        evaluation.split.validation,
        evaluation.split.test,
    )
    source_regime_coverage = sorted(
        {row.source_regime for partition in partitions for row in partition}
    )
    return {
        "experiment_schema_version": "1.0.0",
        "experiment_name": "quantops-synthetic-risk-regime-comparison",
        "dataset": {
            "dataset_hash": dataset_hash,
            "source_price_csv_sha256": source_sha256,
            "is_synthetic": True,
            "source_regime_coverage": source_regime_coverage,
        },
        "feature_schema": FEATURE_SCHEMA.to_mapping(),
        "feature_rows": feature_rows,
        "configuration": config.to_mapping(),
        "baseline": baseline.to_mapping(),
        "evaluation": evaluation.to_mapping(),
        "promotion": promotion.to_mapping(),
        "tracking": tracking.to_mapping(),
        "code_revision": code_revision,
        "limitations": [
            "Synthetic designed regimes are not evidence of real-market generalization.",
            "The classifier estimates risk state, not price direction or investment return.",
            "Chronological partitions have intentionally uneven regime class coverage.",
            "K-Means confidence is distance-based and not a probabilistic forecast.",
            "Host-dependent latency is not persisted as a benchmark claim.",
        ],
    }
