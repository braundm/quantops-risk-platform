"""Shared deterministic dataset and evaluation fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantops_ml.baseline import RuleBaseline
from quantops_ml.data import MarketDataset, load_synthetic_dataset
from quantops_ml.evaluation import EvaluationBundle, evaluate_fixed_seeds
from quantops_ml.features import build_point_in_time_features
from quantops_ml.types import FeatureRow

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRICE_CSV = REPOSITORY_ROOT / "data/synthetic/canonical/price_bars.csv"
DATASET_MANIFEST = REPOSITORY_ROOT / "data/synthetic/manifest.json"


@pytest.fixture(scope="session")
def dataset() -> MarketDataset:
    return load_synthetic_dataset(PRICE_CSV, DATASET_MANIFEST)


@pytest.fixture(scope="session")
def feature_rows(dataset: MarketDataset) -> tuple[FeatureRow, ...]:
    return build_point_in_time_features(dataset)


@pytest.fixture(scope="session")
def evaluation(feature_rows: tuple[FeatureRow, ...]) -> EvaluationBundle:
    return evaluate_fixed_seeds(feature_rows, RuleBaseline())
