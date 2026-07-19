"""Artifact determinism, lifecycle fallback, CLI, and optional tracking tests."""

from __future__ import annotations

import importlib
import importlib.util
import json
import math
import runpy
from enum import StrEnum
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from quantops_ml.artifacts import canonical_json_bytes, write_lifecycle_artifacts
from quantops_ml.cli import main
from quantops_ml.lifecycle import run_lifecycle
from quantops_ml.tracking import track_with_optional_mlflow

from .conftest import DATASET_MANIFEST, PRICE_CSV


class SampleEnum(StrEnum):
    VALUE = "value"


def test_canonical_json_and_content_aware_writes_are_deterministic(tmp_path: Path) -> None:
    value = {"z": 1.1234567890128, "a": [SampleEnum.VALUE, True, None]}
    encoded = canonical_json_bytes(value)
    assert encoded == canonical_json_bytes({"a": ["value", True, None], "z": 1.123456789013})
    assert encoded.endswith(b"\n")
    first = write_lifecycle_artifacts(tmp_path, {"report.json": value}, {"card.md": "card\n"})
    second = write_lifecycle_artifacts(tmp_path, {"report.json": value}, {"card.md": "card\n"})
    assert first.artifact_hash == second.artifact_hash
    assert first.files_written == 3
    assert second.files_written == 0
    assert second.files_unchanged == 3
    manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))
    assert manifest["deterministic"] is True
    assert manifest["wall_clock_metadata_persisted"] is False
    assert manifest["artifact_hash"] == first.artifact_hash


def test_artifact_serialization_rejects_ambiguous_or_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json_bytes({"bad": math.inf})
    with pytest.raises(TypeError, match="string keys"):
        canonical_json_bytes({1: "bad"})
    with pytest.raises(TypeError, match="unsupported"):
        canonical_json_bytes({"bad": {1, 2}})


def test_end_to_end_lifecycle_is_repeatable_and_falls_back_honestly(tmp_path: Path) -> None:
    output = tmp_path / "artifacts"
    first = run_lifecycle(PRICE_CSV, DATASET_MANIFEST, output)
    snapshot = {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}
    second = run_lifecycle(PRICE_CSV, DATASET_MANIFEST, output)
    repeated = {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}
    assert first.feature_rows == 462
    assert first.selected_seed in {7, 19, 41, 73, 101}
    assert first.promotion_status == "rejected_by_automated_demo_policy"
    assert first.tracking_status == "disabled"
    assert first.artifacts.files_written == 10
    assert second.artifacts.files_written == 0
    assert second.artifacts.files_unchanged == 10
    assert second.artifacts.artifact_hash == first.artifacts.artifact_hash
    assert repeated == snapshot

    promotion = json.loads((output / "promotion.json").read_text(encoding="utf-8"))
    failed_gates = {gate["name"] for gate in promotion["gates"] if not gate["passed"]}
    assert failed_gates == {"baseline_relative_macro_f1", "calibration_error"}
    assert promotion["fallback"].startswith("rule-baseline-v1")
    report = json.loads((output / "evaluation_report.json").read_text(encoding="utf-8"))
    assert report["dataset"]["is_synthetic"] is True
    assert len(report["evaluation"]["candidate_runs"]) == 5
    assert report["evaluation"]["inference_cost"]["observed_latency_ms"] is None
    assert report["code_revision"] == "not_recorded_git_cli_unavailable"


def test_cli_records_explicit_code_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    revision = "764b545a1b2c3d4e5f678901234567890abcdef0"

    assert (
        main(
            [
                "run",
                "--prices",
                str(PRICE_CSV),
                "--manifest",
                str(DATASET_MANIFEST),
                "--output",
                str(tmp_path / "artifacts"),
                "--code-revision",
                revision,
            ]
        )
        == 0
    )

    capsys.readouterr()
    report = json.loads((tmp_path / "artifacts" / "evaluation_report.json").read_text())
    assert report["code_revision"] == revision


def test_cli_rejects_non_sha_code_revision() -> None:
    with pytest.raises(SystemExit, match="2"):
        main(["run", "--code-revision", "not-a-revision-or-secret"])


def test_cli_emits_machine_readable_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "cli-artifacts"
    exit_code = main(
        [
            "run",
            "--prices",
            str(PRICE_CSV),
            "--manifest",
            str(DATASET_MANIFEST),
            "--output",
            str(output),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["feature_rows"] == 462
    assert payload["promotion_status"] == "rejected_by_automated_demo_policy"
    assert (output / "model_card.md").is_file()


def test_module_entry_point_delegates_to_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    import quantops_ml.cli as cli

    monkeypatch.setattr(cli, "main", lambda: 0)
    with pytest.raises(SystemExit) as raised:
        runpy.run_module("quantops_ml", run_name="__main__")
    assert raised.value.code == 0


def test_optional_tracking_is_inert_or_unavailable_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parameters: dict[str, object] = {}
    metrics: dict[str, float] = {}
    disabled = track_with_optional_mlflow(
        enabled=False,
        tracking_uri=None,
        experiment_name="unit",
        parameters=parameters,
        metrics=metrics,
        artifact_dir=tmp_path,
    )
    assert disabled.status == "disabled"
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: None)
    unavailable = track_with_optional_mlflow(
        enabled=True,
        tracking_uri="file:///never-used",
        experiment_name="unit",
        parameters=parameters,
        metrics=metrics,
        artifact_dir=tmp_path,
    )
    assert unavailable.status == "unavailable"


def test_optional_tracking_requires_uri_and_degrades_safely(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: SimpleNamespace())
    not_configured = track_with_optional_mlflow(
        enabled=True,
        tracking_uri=None,
        experiment_name="unit",
        parameters={},
        metrics={},
        artifact_dir=tmp_path,
    )
    assert not_configured.status == "not_configured"

    def fail_import(_name: str) -> Any:
        raise RuntimeError("offline")

    monkeypatch.setattr(importlib, "import_module", fail_import)
    degraded = track_with_optional_mlflow(
        enabled=True,
        tracking_uri="file:///configured",
        experiment_name="unit",
        parameters={},
        metrics={},
        artifact_dir=tmp_path,
    )
    assert degraded.status == "degraded"
    assert "RuntimeError" in degraded.detail
