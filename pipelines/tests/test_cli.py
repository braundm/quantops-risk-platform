"""CLI behavior tests for offline generation and manifest verification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quantops_pipelines.cli import main

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPOSITORY_ROOT / "data" / "synthetic" / "generator_config.json"


def test_cli_generates_verifies_and_reports_tampering(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "dataset"
    generate_code = main(
        [
            "generate",
            "--config",
            str(CONFIG_PATH),
            "--output",
            str(output),
        ]
    )
    generated = json.loads(capsys.readouterr().out)
    assert generate_code == 0
    assert generated["price_bar_count"] == 2_088

    verify_code = main(["verify", "--dataset", str(output)])
    verified = json.loads(capsys.readouterr().out)
    assert verify_code == 0
    assert verified["status"] == "valid"

    manifest_path = output / "canonical" / "instruments.json"
    manifest_path.write_bytes(manifest_path.read_bytes() + b"tampered")
    invalid_code = main(["verify", "--dataset", str(output)])
    captured = capsys.readouterr()
    invalid = json.loads(captured.err)
    assert invalid_code == 1
    assert invalid["status"] == "invalid"


def test_cli_verify_reports_missing_manifest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["verify", "--dataset", str(tmp_path)])
    captured = capsys.readouterr()
    response = json.loads(captured.err)
    assert code == 1
    assert response["errors"] == ["manifest.json is missing"]
