"""Chronological evaluation across fixed seeds with an honest selection policy."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from quantops_ml.baseline import RuleBaseline
from quantops_ml.candidate import (
    DEFAULT_CANDIDATE_CONFIG,
    CandidateConfig,
    KMeansCandidate,
    fit_candidate,
)
from quantops_ml.metrics import ClassificationMetrics, classification_metrics
from quantops_ml.types import FeatureRow, Prediction

DEFAULT_SEEDS = (7, 19, 41, 73, 101)


@dataclass(frozen=True, slots=True)
class SplitConfig:
    train_fraction: float = 0.45
    validation_fraction: float = 0.25

    def __post_init__(self) -> None:
        if not 0.2 <= self.train_fraction <= 0.8:
            raise ValueError("train_fraction must be between 0.2 and 0.8")
        if not 0.1 <= self.validation_fraction <= 0.5:
            raise ValueError("validation_fraction must be between 0.1 and 0.5")
        if self.train_fraction + self.validation_fraction >= 0.9:
            raise ValueError("at least ten percent of rows must remain for the test partition")

    @property
    def test_fraction(self) -> float:
        return 1.0 - self.train_fraction - self.validation_fraction

    def to_mapping(self) -> dict[str, float]:
        return {
            "train_fraction": self.train_fraction,
            "validation_fraction": self.validation_fraction,
            "test_fraction": self.test_fraction,
        }


DEFAULT_SPLIT_CONFIG = SplitConfig()


@dataclass(frozen=True, slots=True)
class ChronologicalSplit:
    train: tuple[FeatureRow, ...]
    validation: tuple[FeatureRow, ...]
    test: tuple[FeatureRow, ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "train": _window(self.train),
            "validation": _window(self.validation),
            "test": _window(self.test),
            "shuffle": False,
        }


@dataclass(frozen=True, slots=True)
class CandidateRun:
    seed: int
    model: KMeansCandidate
    validation_metrics: ClassificationMetrics
    test_metrics: ClassificationMetrics
    descriptive_all_rows_metrics: ClassificationMetrics

    def to_mapping(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "validation_metrics": self.validation_metrics.to_mapping(),
            "test_metrics": self.test_metrics.to_mapping(),
            "descriptive_all_rows_metrics": self.descriptive_all_rows_metrics.to_mapping(),
            "model_summary": {
                "iterations": self.model.iterations,
                "cluster_labels": [label.value for label in self.model.cluster_labels],
            },
        }


@dataclass(frozen=True, slots=True)
class EvaluationBundle:
    split: ChronologicalSplit
    baseline_validation: ClassificationMetrics
    baseline_test: ClassificationMetrics
    baseline_descriptive_all_rows: ClassificationMetrics
    candidate_runs: tuple[CandidateRun, ...]
    selected_run: CandidateRun
    aggregate: dict[str, object]
    selection_policy: str

    def to_mapping(self) -> dict[str, object]:
        return {
            "split": self.split.to_mapping(),
            "baseline": {
                "validation": self.baseline_validation.to_mapping(),
                "test": self.baseline_test.to_mapping(),
                "descriptive_all_rows": self.baseline_descriptive_all_rows.to_mapping(),
            },
            "candidate_runs": [run.to_mapping() for run in self.candidate_runs],
            "aggregate": self.aggregate,
            "selected_seed": self.selected_run.seed,
            "selection_policy": self.selection_policy,
            "inference_cost": {
                "distance_evaluations_per_row": self.selected_run.model.config.clusters,
                "observed_latency_ms": None,
                "note": "Host-dependent latency is not persisted as a reproducibility claim.",
            },
        }


def chronological_split(
    rows: tuple[FeatureRow, ...],
    config: SplitConfig = DEFAULT_SPLIT_CONFIG,
) -> ChronologicalSplit:
    if len(rows) < 40:
        raise ValueError("at least 40 feature rows are required for chronological evaluation")
    train_end = int(len(rows) * config.train_fraction)
    validation_end = train_end + int(len(rows) * config.validation_fraction)
    split = ChronologicalSplit(
        train=rows[:train_end],
        validation=rows[train_end:validation_end],
        test=rows[validation_end:],
    )
    if not split.train or not split.validation or not split.test:
        raise ValueError("all chronological partitions must be non-empty")
    if not (
        split.train[-1].as_of < split.validation[0].as_of
        and split.validation[-1].as_of < split.test[0].as_of
    ):
        raise ValueError("chronological partitions overlap or are out of order")
    return split


def evaluate_fixed_seeds(
    rows: tuple[FeatureRow, ...],
    baseline: RuleBaseline,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    split_config: SplitConfig = DEFAULT_SPLIT_CONFIG,
    candidate_config: CandidateConfig = DEFAULT_CANDIDATE_CONFIG,
) -> EvaluationBundle:
    """Evaluate every declared seed and select the median validation result, not the best."""

    if len(seeds) < 3 or len(set(seeds)) != len(seeds):
        raise ValueError("at least three unique fixed seeds are required")
    split = chronological_split(rows, split_config)
    baseline_validation = _metrics_for(
        split.validation,
        tuple(baseline.classify(row) for row in split.validation),
    )
    baseline_test = _metrics_for(split.test, tuple(baseline.classify(row) for row in split.test))
    baseline_all = _metrics_for(rows, tuple(baseline.classify(row) for row in rows))
    runs: list[CandidateRun] = []
    for seed in seeds:
        model = fit_candidate(split.train, seed, baseline, candidate_config)
        runs.append(
            CandidateRun(
                seed=seed,
                model=model,
                validation_metrics=_metrics_for(
                    split.validation,
                    model.predict_many(split.validation),
                ),
                test_metrics=_metrics_for(split.test, model.predict_many(split.test)),
                descriptive_all_rows_metrics=_metrics_for(rows, model.predict_many(rows)),
            )
        )
    ordered = sorted(runs, key=lambda run: (run.validation_metrics.macro_f1, run.seed))
    selected = ordered[len(ordered) // 2]
    aggregate = _aggregate_runs(tuple(runs))
    return EvaluationBundle(
        split=split,
        baseline_validation=baseline_validation,
        baseline_test=baseline_test,
        baseline_descriptive_all_rows=baseline_all,
        candidate_runs=tuple(runs),
        selected_run=selected,
        aggregate=aggregate,
        selection_policy=(
            "Select the median validation macro-F1 run across every declared fixed seed; "
            "ties use the lower seed. Test metrics never select the model."
        ),
    )


def _metrics_for(
    rows: tuple[FeatureRow, ...],
    predictions: tuple[Prediction, ...],
) -> ClassificationMetrics:
    return classification_metrics(tuple(row.known_regime for row in rows), predictions)


def _aggregate_runs(runs: tuple[CandidateRun, ...]) -> dict[str, object]:
    validation_f1 = [run.validation_metrics.macro_f1 for run in runs]
    test_f1 = [run.test_metrics.macro_f1 for run in runs]
    validation_ari = [run.validation_metrics.adjusted_rand_index for run in runs]
    validation_calibration = [run.validation_metrics.expected_calibration_error for run in runs]
    return {
        "seed_count": len(runs),
        "seeds": [run.seed for run in runs],
        "validation_macro_f1_mean": statistics.fmean(validation_f1),
        "validation_macro_f1_stddev": statistics.pstdev(validation_f1),
        "test_macro_f1_mean": statistics.fmean(test_f1),
        "test_macro_f1_stddev": statistics.pstdev(test_f1),
        "validation_adjusted_rand_mean": statistics.fmean(validation_ari),
        "validation_expected_calibration_error_mean": statistics.fmean(validation_calibration),
        "reporting_policy": "all configured seeds are included; none are omitted",
    }


def _window(rows: tuple[FeatureRow, ...]) -> dict[str, object]:
    return {
        "rows": len(rows),
        "start": rows[0].as_of.isoformat(),
        "end": rows[-1].as_of.isoformat(),
        "known_regime_counts": {
            regime: sum(row.known_regime.value == regime for row in rows)
            for regime in sorted({row.known_regime.value for row in rows})
        },
    }
