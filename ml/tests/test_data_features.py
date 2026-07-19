"""Dataset provenance and point-in-time feature tests."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from quantops_ml.data import DailyMarketFrame, MarketDataset, load_synthetic_dataset
from quantops_ml.features import FeatureConfig, assert_point_in_time, build_point_in_time_features
from quantops_ml.types import FEATURE_SCHEMA, FeatureRow, RiskRegime

from .conftest import DATASET_MANIFEST, PRICE_CSV


def test_canonical_dataset_provenance_and_shape(dataset: MarketDataset) -> None:
    assert dataset.is_synthetic is True
    assert len(dataset.frames) == 522
    assert len(dataset.dataset_hash) == 64
    assert len(dataset.source_sha256) == 64
    assert all(len(frame.bars) == 4 for frame in dataset.frames)
    assert dataset.frames[0].observed_on < dataset.frames[-1].observed_on


def test_point_in_time_feature_contract(feature_rows: tuple[FeatureRow, ...]) -> None:
    assert len(feature_rows) == 462
    assert_point_in_time(feature_rows)
    assert all(row.is_synthetic for row in feature_rows)
    assert all(row.max_input_date == row.as_of for row in feature_rows)
    assert all(len(row.values) == len(FEATURE_SCHEMA.names) for row in feature_rows)
    assert all(math.isfinite(value) for row in feature_rows for value in row.values)
    assert {row.source_regime for row in feature_rows} == {
        "normal",
        "risk_on",
        "volatility_shock",
        "correlation_breakdown",
        "partial_recovery",
    }
    mapped = feature_rows[0].to_mapping()
    assert mapped["max_input_date"] == mapped["as_of"]
    mapped_features = mapped["features"]
    assert isinstance(mapped_features, dict)
    assert set(mapped_features) == set(FEATURE_SCHEMA.names)


def test_future_observations_cannot_change_earlier_features(dataset: MarketDataset) -> None:
    original = build_point_in_time_features(dataset)
    cutoff_index = 260
    cutoff = dataset.frames[cutoff_index].observed_on
    changed_frames = list(dataset.frames)
    for index in range(cutoff_index + 1, len(changed_frames)):
        frame = changed_frames[index]
        bars = dict(frame.bars)
        bars["QTECH"] = replace(
            bars["QTECH"],
            close=bars["QTECH"].close * 3.0,
            volume=bars["QTECH"].volume + 1_000_000,
        )
        changed_frames[index] = DailyMarketFrame(frame.observed_on, bars)
    perturbed = build_point_in_time_features(
        MarketDataset(
            frames=tuple(changed_frames),
            dataset_hash=dataset.dataset_hash,
            source_sha256=dataset.source_sha256,
            is_synthetic=True,
        )
    )
    original_before_cutoff = tuple(row for row in original if row.as_of <= cutoff)
    perturbed_before_cutoff = tuple(row for row in perturbed if row.as_of <= cutoff)
    assert perturbed_before_cutoff == original_before_cutoff


def test_loader_rejects_tampered_price_content(tmp_path: Path) -> None:
    tampered = tmp_path / "prices.csv"
    content = PRICE_CSV.read_bytes()
    tampered.write_bytes(content.replace(b"QTECH", b"XTECH", 1))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_synthetic_dataset(tampered, DATASET_MANIFEST)


def test_loader_requires_explicit_synthetic_manifest(tmp_path: Path) -> None:
    manifest = json.loads(DATASET_MANIFEST.read_text(encoding="utf-8"))
    manifest["all_records_synthetic"] = False
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="explicitly mark all records synthetic"):
        load_synthetic_dataset(PRICE_CSV, manifest_path)


def test_feature_config_and_row_validation() -> None:
    with pytest.raises(ValueError, match="greater than one"):
        FeatureConfig(volatility_window=1)
    with pytest.raises(ValueError, match="align"):
        FeatureConfig(portfolio_weights=(0.3, 0.3, 0.4))
    with pytest.raises(ValueError, match="sum to one"):
        FeatureConfig(portfolio_weights=(0.3, 0.3, 0.3, 0.3))
    with pytest.raises(ValueError, match="vector length"):
        FeatureRow(
            date.today(),
            date.today(),
            (0.0,),
            RiskRegime.NORMAL,
            "unit",
            True,
        )
    with pytest.raises(ValueError, match="future input"):
        FeatureRow(
            date(2026, 1, 1),
            date(2026, 1, 2),
            (0.0,) * len(FEATURE_SCHEMA.names),
            RiskRegime.NORMAL,
            "unit",
            True,
        )


def test_point_in_time_assertion_rejects_empty_and_non_chronological(
    feature_rows: tuple[FeatureRow, ...],
) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        assert_point_in_time(())
    with pytest.raises(ValueError, match="strictly chronological"):
        assert_point_in_time((feature_rows[1], feature_rows[0]))
    with pytest.raises(KeyError, match="not_a_feature"):
        feature_rows[0].value("not_a_feature")
