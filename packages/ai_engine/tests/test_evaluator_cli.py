"""Versioned 44-case suite, deterministic report, and CLI tests."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

from quantops_ai.cli import main
from quantops_ai.evaluator import (
    EvaluationCategory,
    default_cases_path,
    load_evaluation_cases,
    run_evaluation,
)


def test_versioned_suite_has_44_cases_and_all_20_categories() -> None:
    cases = load_evaluation_cases(default_cases_path())
    assert len(cases) == 44
    assert {case.category for case in cases} == set(EvaluationCategory)
    assert len({case.case_id for case in cases}) == 44


def test_full_deterministic_evaluation_passes_every_case() -> None:
    report = run_evaluation(load_evaluation_cases(default_cases_path()))
    assert report.case_count == report.passed == 44
    assert report.failed == 0
    assert report.category_count == 20
    assert report.schema_valid_rate == 1.0
    assert report.citation_valid_rate == 1.0
    assert report.numerical_consistency_rate == 1.0
    assert report.refusal_accuracy == 1.0
    assert report.tool_selection_accuracy == 1.0
    assert report.groundedness_rate == 1.0
    assert report.fallback_rate > 0
    mapping = report.to_mapping()
    assert mapping["evaluation_policy"] == "deterministic labeled checks; no model-graded scoring"
    assert mapping["external_provider_cost_usd"] is None
    assert mapping["external_provider_token_estimate"] is None
    assert len(mapping["cases"]) == 44  # type: ignore[arg-type]


def test_evaluation_loader_rejects_invalid_duplicate_and_incomplete_suites(
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        load_evaluation_cases(invalid)

    first_line = default_cases_path().read_text(encoding="utf-8").splitlines()[0]
    duplicate = tmp_path / "duplicate.jsonl"
    duplicate.write_text(f"{first_line}\n{first_line}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_evaluation_cases(duplicate, require_complete_suite=False)

    small = tmp_path / "small.jsonl"
    small.write_text(first_line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="at least 40"):
        load_evaluation_cases(small)
    assert len(load_evaluation_cases(small, require_complete_suite=False)) == 1

    forty_same_category = tmp_path / "missing.jsonl"
    base = json.loads(first_line)
    lines = []
    for index in range(40):
        case = dict(base)
        case["case_id"] = f"AI-EVAL-{index + 100:03d}"
        lines.append(json.dumps(case))
    forty_same_category.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(ValueError, match="missing categories"):
        load_evaluation_cases(forty_same_category)


def test_evaluation_requires_cases() -> None:
    with pytest.raises(ValueError, match="at least one"):
        run_evaluation(())


def test_cli_writes_machine_readable_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "evaluation-report.json"
    exit_code = main(["evaluate", "--output", str(output)])
    summary = json.loads(capsys.readouterr().out)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert summary == {
        "case_count": 44,
        "failed": 0,
        "passed": 44,
        "report_path": str(output),
    }
    assert report["case_count"] == 44
    assert report["failed"] == 0


def test_module_entry_point_delegates_to_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    import quantops_ai.cli as cli

    monkeypatch.setattr(cli, "main", lambda: 0)
    with pytest.raises(SystemExit) as raised:
        runpy.run_module("quantops_ai", run_name="__main__")
    assert raised.value.code == 0
