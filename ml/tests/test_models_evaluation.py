"""Transparent baseline, deterministic candidate, and honest split tests."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from quantops_ml.baseline import BASELINE_VERSION, BaselineThresholds, RuleBaseline
from quantops_ml.candidate import CandidateConfig, Standardizer, fit_candidate
from quantops_ml.evaluation import (
    DEFAULT_SEEDS,
    EvaluationBundle,
    SplitConfig,
    chronological_split,
    evaluate_fixed_seeds,
)
from quantops_ml.types import FEATURE_SCHEMA, FeatureRow, RiskRegime

from .helpers import feature_row


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (feature_row(), RiskRegime.NORMAL),
        (
            feature_row(portfolio_volatility_20d=0.18),
            RiskRegime.ELEVATED_VOLATILITY,
        ),
        (feature_row(portfolio_drawdown_60d=0.20), RiskRegime.STRESS),
        (
            feature_row(
                portfolio_volatility_20d=0.20,
                mean_pairwise_correlation_20d=0.70,
            ),
            RiskRegime.CORRELATION_BREAKDOWN,
        ),
        (
            feature_row(missing_observation_ratio_20d=0.50),
            RiskRegime.INSUFFICIENT_DATA,
        ),
    ],
)
def test_rule_baseline_classifies_documented_risk_states(
    row: FeatureRow,
    expected: RiskRegime,
) -> None:
    prediction = RuleBaseline().classify(row)
    assert prediction.label is expected
    assert prediction.reason
    assert 0.0 <= prediction.confidence <= 1.0


def test_rule_baseline_handles_missing_and_nonfinite_rows() -> None:
    baseline = RuleBaseline()
    assert baseline.classify(None).label is RiskRegime.INSUFFICIENT_DATA
    invalid = replace(feature_row(), values=(math.nan,) * len(FEATURE_SCHEMA.names))
    assert baseline.classify(invalid).label is RiskRegime.INSUFFICIENT_DATA
    mapping = baseline.to_mapping()
    assert mapping["version"] == BASELINE_VERSION
    assert mapping["intended_use"] == "risk-regime classification only"
    assert BaselineThresholds().to_mapping()["stress_volatility"] == 0.34


def test_candidate_is_reproducible_and_scaler_is_train_only(
    feature_rows: tuple[FeatureRow, ...],
) -> None:
    split = chronological_split(feature_rows)
    baseline = RuleBaseline()
    first = fit_candidate(split.train, 19, baseline)
    second = fit_candidate(split.train, 19, baseline)
    assert first == second
    assert first.predict_many(split.test) == second.predict_many(split.test)
    assert first.standardizer == Standardizer.fit(split.train)
    assert first.standardizer != Standardizer.fit(feature_rows)
    assert first.training_end == split.train[-1].as_of.isoformat()
    assert first.to_mapping()["feature_schema_version"] == FEATURE_SCHEMA.version
    assert first.predict(None).label is RiskRegime.INSUFFICIENT_DATA
    invalid = replace(feature_rows[0], values=(math.inf,) * len(FEATURE_SCHEMA.names))
    assert first.predict(invalid).label is RiskRegime.INSUFFICIENT_DATA


def test_standardizer_round_trip_and_validation(feature_rows: tuple[FeatureRow, ...]) -> None:
    standardizer = Standardizer.fit(feature_rows[:80])
    transformed = standardizer.transform(feature_rows[40].values)
    restored = standardizer.inverse(transformed)
    assert restored == pytest.approx(feature_rows[40].values)
    assert standardizer.to_mapping()["fit_scope"] == "training_partition_only"
    with pytest.raises(ValueError, match="without rows"):
        Standardizer.fit(())
    with pytest.raises(ValueError, match="does not match"):
        standardizer.transform((1.0,))


def test_candidate_configuration_validation(feature_rows: tuple[FeatureRow, ...]) -> None:
    with pytest.raises(ValueError, match="at least two"):
        CandidateConfig(clusters=1)
    with pytest.raises(ValueError, match="positive"):
        CandidateConfig(max_iterations=0)
    with pytest.raises(ValueError, match="at least"):
        fit_candidate(feature_rows[:2], 7, RuleBaseline(), CandidateConfig(clusters=4))


def test_evaluation_reports_every_seed_and_selects_validation_median(
    evaluation: EvaluationBundle,
) -> None:
    assert tuple(run.seed for run in evaluation.candidate_runs) == DEFAULT_SEEDS
    ordered = sorted(
        evaluation.candidate_runs,
        key=lambda run: (run.validation_metrics.macro_f1, run.seed),
    )
    assert evaluation.selected_run == ordered[len(ordered) // 2]
    assert evaluation.aggregate["seed_count"] == len(DEFAULT_SEEDS)
    assert evaluation.aggregate["seeds"] == list(DEFAULT_SEEDS)
    assert "Test metrics never select" in evaluation.selection_policy
    report = evaluation.to_mapping()
    assert report["split"]["shuffle"] is False  # type: ignore[index]
    assert report["inference_cost"]["observed_latency_ms"] is None  # type: ignore[index]


def test_chronological_split_has_strict_non_overlapping_boundaries(
    feature_rows: tuple[FeatureRow, ...],
) -> None:
    split = chronological_split(feature_rows)
    assert split.train[-1].as_of < split.validation[0].as_of
    assert split.validation[-1].as_of < split.test[0].as_of
    assert len(split.train) + len(split.validation) + len(split.test) == len(feature_rows)
    assert split.to_mapping()["shuffle"] is False
    with pytest.raises(ValueError, match="at least 40"):
        chronological_split(feature_rows[:39])
    disorder = list(feature_rows)
    disorder[206], disorder[207] = disorder[207], disorder[206]
    with pytest.raises(ValueError, match="overlap or are out of order"):
        chronological_split(tuple(disorder))


def test_split_and_seed_policy_validation(feature_rows: tuple[FeatureRow, ...]) -> None:
    with pytest.raises(ValueError, match="train_fraction"):
        SplitConfig(train_fraction=0.1)
    with pytest.raises(ValueError, match="validation_fraction"):
        SplitConfig(validation_fraction=0.05)
    with pytest.raises(ValueError, match="ten percent"):
        SplitConfig(train_fraction=0.71, validation_fraction=0.2)
    with pytest.raises(ValueError, match="three unique"):
        evaluate_fixed_seeds(feature_rows, RuleBaseline(), (7, 7, 19))
