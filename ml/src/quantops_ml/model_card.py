"""Deterministic model-card rendering and completeness validation."""

from __future__ import annotations

from quantops_ml.evaluation import EvaluationBundle
from quantops_ml.promotion import PromotionDecision
from quantops_ml.types import FEATURE_SCHEMA

REQUIRED_HEADINGS = (
    "## Intended use",
    "## Prohibited use",
    "## Training data",
    "## Feature schema and leakage controls",
    "## Evaluation and calibration",
    "## Seed selection policy",
    "## Promotion status",
    "## Drift behavior",
    "## Reproducibility",
    "## Limitations",
)


def render_model_card(
    evaluation: EvaluationBundle,
    dataset_hash: str,
    promotion: PromotionDecision | None,
) -> str:
    selected = evaluation.selected_run
    promotion_status = (
        "pending automated policy evaluation" if promotion is None else promotion.status
    )
    text = f"""# QuantOps risk-regime candidate model card

## Intended use

Classify end-of-day **risk regimes** in the fictional QuantOps demonstration dataset. The model
supports risk monitoring, model-lifecycle engineering, and data-quality demonstrations.

## Prohibited use

This model does not predict prices or returns, optimize profit, recommend buying or selling,
execute orders, or represent real-market performance. It must not be used for personalized
investment advice.

## Training data

The only training source is the deterministic synthetic dataset with manifest hash
`{dataset_hash}`. Selected training window: `{selected.model.training_start}` through
`{selected.model.training_end}`. All rows are explicitly synthetic.

## Feature schema and leakage controls

Schema `{FEATURE_SCHEMA.version}` uses rolling volatility, portfolio volatility, pairwise
correlation, drawdown, drawdown velocity, cross-sectional dispersion, volume anomaly, and missing
observation ratio. Every row records `max_input_date <= as_of`; standardization is fitted only on
the chronological training partition. Primary evaluation never shuffles time.

## Evaluation and calibration

Selected validation macro F1: `{selected.validation_metrics.macro_f1:.6f}`. Selected test macro F1:
`{selected.test_metrics.macro_f1:.6f}`. Test expected calibration error:
`{selected.test_metrics.expected_calibration_error:.6f}`. Macro F1 always averages the four
declared evaluable regimes, including absent predictions. A missing stress class produces a null
stress false-negative rate rather than a fabricated value.

## Seed selection policy

{evaluation.selection_policy} Every configured seed is reported; the best seed is not cherry-picked.
Cluster semantics use the documented rule-baseline classification of raw-space centroids, not an
unsupported economic interpretation of anonymous cluster numbers.

## Promotion status

`{promotion_status}`. Promotion is automated by demo policy only; no committee or named person is
claimed to have approved the model. When any gate fails, `rule-baseline-v1` remains active.

## Drift behavior

Feature drift uses Population Stability Index, quality drift uses the missing-ratio change, and
regime-proportion drift uses Jensen-Shannon divergence. Thresholds are operational signals, not
tests of statistical significance, causality, price direction, or profitability.

## Reproducibility

The candidate uses pure-Python deterministic K-Means, selected seed `{selected.seed}`, fixed
configuration, canonical JSON artifacts, and no network dependency. Host-dependent latency and
wall-clock timestamps are not persisted as reproducibility claims.

## Limitations

The regimes and documents are fictional. Chronological partitions contain different designed
regimes, so some holdout metrics have limited class coverage. K-Means assumes compact Euclidean
clusters after standardization; its confidence score is a distance heuristic, not a calibrated
probability. Synthetic performance must not be generalized to real markets.
"""
    return text


def model_card_complete(card: str) -> bool:
    return all(heading in card for heading in REQUIRED_HEADINGS) and all(
        phrase in card.lower()
        for phrase in ("synthetic", "does not predict prices", "investment advice", "limitations")
    )
