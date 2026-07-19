"""Strict loader for the content-addressed deterministic synthetic dataset."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

REQUIRED_SYMBOLS = ("QTECH", "QGOLD", "QWTI", "QCASH")


@dataclass(frozen=True, slots=True)
class MarketBar:
    symbol: str
    observed_on: date
    close: float
    volume: int
    regime: str
    is_synthetic: bool


@dataclass(frozen=True, slots=True)
class DailyMarketFrame:
    observed_on: date
    bars: Mapping[str, MarketBar]


@dataclass(frozen=True, slots=True)
class MarketDataset:
    frames: tuple[DailyMarketFrame, ...]
    dataset_hash: str
    source_sha256: str
    is_synthetic: bool


def load_synthetic_dataset(csv_path: Path, manifest_path: Path) -> MarketDataset:
    """Load canonical bars only after verifying their manifest SHA-256."""

    manifest_raw: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = _mapping(manifest_raw, "manifest")
    if manifest.get("all_records_synthetic") is not True:
        raise ValueError("dataset manifest must explicitly mark all records synthetic")
    dataset_hash = _required_string(manifest, "dataset_hash")
    expected_hash = _artifact_hash(manifest, "canonical/price_bars.csv")
    content = csv_path.read_bytes()
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError(
            f"price CSV SHA-256 mismatch: expected {expected_hash}, received {actual_hash}"
        )

    grouped: dict[date, dict[str, MarketBar]] = defaultdict(dict)
    text = content.decode("utf-8")
    for row_number, row in enumerate(csv.DictReader(text.splitlines()), start=2):
        symbol = _required_row(row, "symbol", row_number)
        if symbol not in REQUIRED_SYMBOLS:
            raise ValueError(f"row {row_number}: unexpected symbol {symbol}")
        timestamp = _required_row(row, "timestamp", row_number)
        observed_on = date.fromisoformat(timestamp[:10])
        if symbol in grouped[observed_on]:
            raise ValueError(f"row {row_number}: duplicate {symbol} bar for {observed_on}")
        close = float(_required_row(row, "close", row_number))
        volume = int(_required_row(row, "volume", row_number))
        if close <= 0 or volume < 0:
            raise ValueError(f"row {row_number}: close must be positive and volume nonnegative")
        synthetic_text = _required_row(row, "is_synthetic", row_number).lower()
        if synthetic_text not in {"true", "1"}:
            raise ValueError(f"row {row_number}: record is not marked synthetic")
        grouped[observed_on][symbol] = MarketBar(
            symbol=symbol,
            observed_on=observed_on,
            close=close,
            volume=volume,
            regime=_required_row(row, "regime", row_number),
            is_synthetic=True,
        )

    frames: list[DailyMarketFrame] = []
    for observed_on in sorted(grouped):
        bars = grouped[observed_on]
        missing = sorted(set(REQUIRED_SYMBOLS) - set(bars))
        if missing:
            raise ValueError(f"{observed_on}: canonical data is missing symbols {missing}")
        regimes = {bar.regime for bar in bars.values()}
        if len(regimes) != 1:
            raise ValueError(f"{observed_on}: symbols disagree on the synthetic regime")
        frames.append(DailyMarketFrame(observed_on=observed_on, bars=dict(bars)))
    if len(frames) < 252 * 2:
        raise ValueError("synthetic dataset must contain at least two years of business days")
    return MarketDataset(
        frames=tuple(frames),
        dataset_hash=dataset_hash,
        source_sha256=actual_hash,
        is_synthetic=True,
    )


def _artifact_hash(manifest: Mapping[str, object], path: str) -> str:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("manifest artifacts must be a list")
    for item in artifacts:
        artifact = _mapping(item, "artifact")
        if artifact.get("path") == path:
            return _required_string(artifact, "sha256")
    raise ValueError(f"manifest does not contain {path}")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _required_string(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_row(row: Mapping[str, str | None], key: str, row_number: int) -> str:
    value = row.get(key)
    if value is None or value == "":
        raise ValueError(f"row {row_number}: missing {key}")
    return value
