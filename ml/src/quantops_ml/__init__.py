"""Leakage-safe deterministic synthetic risk-regime lifecycle."""

from quantops_ml.baseline import BASELINE_VERSION, BaselineThresholds, RuleBaseline
from quantops_ml.candidate import (
    CANDIDATE_VERSION,
    CandidateConfig,
    KMeansCandidate,
    Standardizer,
    fit_candidate,
)
from quantops_ml.data import MarketDataset, load_synthetic_dataset
from quantops_ml.drift import (
    DriftReport,
    DriftThresholds,
    jensen_shannon_divergence,
    monitor_drift,
    population_stability_index,
    synthetic_drift_rows,
)
from quantops_ml.evaluation import (
    DEFAULT_SEEDS,
    ChronologicalSplit,
    EvaluationBundle,
    SplitConfig,
    chronological_split,
    evaluate_fixed_seeds,
)
from quantops_ml.features import FeatureConfig, assert_point_in_time, build_point_in_time_features
from quantops_ml.lifecycle import LifecycleConfig, LifecycleResult, run_lifecycle
from quantops_ml.metrics import ClassificationMetrics, adjusted_rand_index, classification_metrics
from quantops_ml.promotion import PromotionDecision, PromotionPolicy, evaluate_promotion
from quantops_ml.types import FEATURE_SCHEMA, FeatureRow, Prediction, RiskRegime

__all__ = [
    "BASELINE_VERSION",
    "CANDIDATE_VERSION",
    "DEFAULT_SEEDS",
    "FEATURE_SCHEMA",
    "BaselineThresholds",
    "CandidateConfig",
    "ChronologicalSplit",
    "ClassificationMetrics",
    "DriftReport",
    "DriftThresholds",
    "EvaluationBundle",
    "FeatureConfig",
    "FeatureRow",
    "KMeansCandidate",
    "LifecycleConfig",
    "LifecycleResult",
    "MarketDataset",
    "Prediction",
    "PromotionDecision",
    "PromotionPolicy",
    "RiskRegime",
    "RuleBaseline",
    "SplitConfig",
    "Standardizer",
    "adjusted_rand_index",
    "assert_point_in_time",
    "build_point_in_time_features",
    "chronological_split",
    "classification_metrics",
    "evaluate_fixed_seeds",
    "evaluate_promotion",
    "fit_candidate",
    "jensen_shannon_divergence",
    "load_synthetic_dataset",
    "monitor_drift",
    "population_stability_index",
    "run_lifecycle",
    "synthetic_drift_rows",
]

__version__ = "0.1.0"
