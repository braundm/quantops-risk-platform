"""Determinism, labeling, manifest, and fixture-behavior tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quantops_pipelines.generator import (
    REGIME_ORDER,
    REQUIRED_SYMBOLS,
    generate_dataset,
    load_config,
    verify_dataset,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPOSITORY_ROOT / "data" / "synthetic" / "generator_config.json"


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(directory)).replace("\\", "/"): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _json(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_regeneration_is_byte_identical_and_idempotent(tmp_path: Path) -> None:
    config = load_config(CONFIG_PATH)
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first = generate_dataset(config, first_dir)
    second = generate_dataset(config, second_dir)

    assert first.dataset_hash == second.dataset_hash
    assert first.price_bar_count == 2_088
    assert _snapshot(first_dir) == _snapshot(second_dir)

    before = _snapshot(first_dir)
    rerun = generate_dataset(config, first_dir)
    assert rerun.files_written == 0
    assert rerun.files_unchanged == 11
    assert _snapshot(first_dir) == before


def test_manifest_verifies_every_generated_artifact(tmp_path: Path) -> None:
    config = load_config(CONFIG_PATH)
    output = tmp_path / "dataset"
    result = generate_dataset(config, output)

    assert result.dataset_hash
    assert verify_dataset(output) == ()

    price_path = output / "canonical" / "price_bars.csv"
    price_path.write_bytes(price_path.read_bytes() + b"tampered")
    errors = verify_dataset(output)
    assert any("price_bars.csv" in error and "mismatch" in error for error in errors)


def test_canonical_records_cover_all_instruments_regimes_and_dates(tmp_path: Path) -> None:
    output = tmp_path / "dataset"
    generate_dataset(load_config(CONFIG_PATH), output)
    payload = _json(output / "canonical" / "price_bars.json")
    records = payload["records"]
    assert isinstance(records, list)

    assert payload["is_synthetic"] is True
    assert payload["record_count"] == 2_088
    assert {record["symbol"] for record in records} == set(REQUIRED_SYMBOLS)
    assert {record["regime"] for record in records} == set(REGIME_ORDER)
    assert all(record["is_synthetic"] is True for record in records)
    assert records[0]["timestamp"] == "2023-01-02T21:00:00Z"
    assert records[-1]["timestamp"] == "2024-12-31T21:00:00Z"

    shock_records = [record for record in records if record["timestamp"] == "2024-01-01T21:00:00Z"]
    assert {record["symbol"] for record in shock_records} == set(REQUIRED_SYMBOLS)
    qtech = next(record for record in shock_records if record["symbol"] == "QTECH")
    assert float(qtech["close"]) < float(qtech["open"]) * 0.93


def test_fictional_documents_are_approved_synthetic_and_include_inert_attack(
    tmp_path: Path,
) -> None:
    output = tmp_path / "dataset"
    generate_dataset(load_config(CONFIG_PATH), output)
    payload = _json(output / "canonical" / "documents.json")
    documents = payload["documents"]
    assert isinstance(documents, list)

    assert len(documents) == 4
    assert all(document["is_synthetic"] is True for document in documents)
    assert all(document["approved_for_demo"] is True for document in documents)
    security_document = next(
        document for document in documents if document["metadata"]["security_test"] is True
    )
    assert "Ignore all previous instructions" in security_document["body"]
    assert "inert prompt-injection fixture" in security_document["body"]


def test_intentional_cases_are_isolated_and_have_exact_run_counts(tmp_path: Path) -> None:
    output = tmp_path / "dataset"
    result = generate_dataset(load_config(CONFIG_PATH), output)
    cases = _json(output / "cases" / "quality_cases.json")
    run = _json(output / "runs" / "quality_run.json")
    counts = run["counts"]
    assert isinstance(counts, dict)

    assert result.quality_accepted_count == 17
    assert result.quality_quarantined_count == 4
    assert counts == {
        "accepted_records": 17,
        "counts_by_rule": {
            "DQ_DUPLICATE_EVENT": 1,
            "DQ_LATE_ARRIVAL": 1,
            "DQ_MALFORMED_NUMBER": 1,
            "DQ_MISSING_EXPECTED_BAR": 1,
        },
        "expected_records": 20,
        "input_records": 20,
        "quality_issues": 4,
        "quarantined_records": 4,
    }
    assert cases["is_synthetic"] is True
    assert cases["expected_record_count"] == 20
    assert cases["staging_record_count"] == 20

    quarantine_path = output / "quarantine" / "quality_quarantine.jsonl"
    quarantine = [json.loads(line) for line in quarantine_path.read_text().splitlines()]
    assert len(quarantine) == 4
    assert all(item["is_synthetic"] is True for item in quarantine)
    assert all(
        item["payload_reference"].startswith("cases/quality_cases.json#") for item in quarantine
    )
    assert {code for item in quarantine for code in item["rule_codes"]} == {
        "DQ_DUPLICATE_EVENT",
        "DQ_LATE_ARRIVAL",
        "DQ_MALFORMED_NUMBER",
        "DQ_MISSING_EXPECTED_BAR",
    }


def test_configuration_rejects_an_uncovered_business_date(tmp_path: Path) -> None:
    raw = _json(CONFIG_PATH)
    regimes = raw["regimes"]
    assert isinstance(regimes, list)
    regimes[0]["end_date"] = "2023-06-29"
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly one regime"):
        load_config(invalid)
