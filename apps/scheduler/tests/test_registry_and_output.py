"""Typed registry, hashing, command, and public-output contract tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from quantops_scheduler.config import (
    AiEvaluationConfig,
    DatasetGenerateConfig,
    DatasetVerifyConfig,
    JobConfig,
    MlLifecycleConfig,
    config_hash,
)
from quantops_scheduler.errors import InvalidJobOutputError
from quantops_scheduler.models import JobName
from quantops_scheduler.output import parse_job_output
from quantops_scheduler.registry import (
    config_from_mapping,
    default_job_configs,
    default_registry,
)

LOGICAL_TIME = datetime(2026, 7, 19, 12, tzinfo=UTC)


def test_default_registry_has_four_bounded_offline_jobs() -> None:
    registry = default_registry()

    assert {item.name for item in registry.definitions} == set(JobName)
    assert registry.definition(JobName.GENERATE_DEMO_DATASET).schedule is None
    assert registry.definition(JobName.VERIFY_DEMO_DATASET).schedule == "0 3 * * *"
    assert registry.definition(JobName.RUN_ML_LIFECYCLE).schedule == "0 4 * * 1"
    assert registry.definition(JobName.EVALUATE_AI_WORKFLOW).schedule == "0 5 * * 1"


def test_plan_identity_is_stable_and_dry_run_is_separate(tmp_path: Path) -> None:
    registry = default_registry()
    config = DatasetVerifyConfig(tmp_path / "dataset")

    first = registry.plan(
        JobName.VERIFY_DEMO_DATASET,
        config,
        scheduled_for=LOGICAL_TIME,
    )
    second = registry.plan(
        JobName.VERIFY_DEMO_DATASET,
        config,
        scheduled_for=LOGICAL_TIME,
    )
    dry_run = registry.plan(
        JobName.VERIFY_DEMO_DATASET,
        config,
        scheduled_for=LOGICAL_TIME,
        dry_run=True,
    )

    assert first.run_id == second.run_id
    assert first.config_hash == second.config_hash == config_hash(config)
    assert len(first.config_hash) == 64
    assert dry_run.run_id != first.run_id


def test_plan_rejects_wrong_config_type_and_naive_time(tmp_path: Path) -> None:
    registry = default_registry()

    with pytest.raises(TypeError, match="requires DatasetVerifyConfig"):
        registry.plan(
            JobName.VERIFY_DEMO_DATASET,
            AiEvaluationConfig(tmp_path / "cases.jsonl"),
            scheduled_for=LOGICAL_TIME,
        )
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        registry.plan(
            JobName.VERIFY_DEMO_DATASET,
            DatasetVerifyConfig(tmp_path),
            scheduled_for=LOGICAL_TIME.replace(tzinfo=None),
        )


def test_config_mapping_round_trips_for_every_job(tmp_path: Path) -> None:
    values: tuple[tuple[JobName, JobConfig], ...] = (
        (
            JobName.GENERATE_DEMO_DATASET,
            DatasetGenerateConfig(tmp_path / "config.json", tmp_path / "dataset"),
        ),
        (JobName.VERIFY_DEMO_DATASET, DatasetVerifyConfig(tmp_path / "dataset")),
        (
            JobName.RUN_ML_LIFECYCLE,
            MlLifecycleConfig(
                tmp_path / "prices.csv",
                tmp_path / "manifest.json",
                tmp_path / "models",
                "abcdef1",
            ),
        ),
        (
            JobName.EVALUATE_AI_WORKFLOW,
            AiEvaluationConfig(tmp_path / "cases.jsonl", tmp_path / "report.json"),
        ),
    )

    for name, config in values:
        assert config_from_mapping(name, config.to_mapping()).to_mapping() == config.to_mapping()


def test_config_mapping_rejects_extra_fields_and_mlflow(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fields"):
        config_from_mapping(
            JobName.VERIFY_DEMO_DATASET,
            {"dataset_dir": str(tmp_path), "unexpected": True},
        )
    with pytest.raises(ValueError, match="MLflow"):
        config_from_mapping(
            JobName.RUN_ML_LIFECYCLE,
            {
                "prices_path": str(tmp_path / "prices.csv"),
                "manifest_path": str(tmp_path / "manifest.json"),
                "output_dir": str(tmp_path / "models"),
                "code_revision": None,
                "mlflow_enabled": True,
            },
        )


def test_ml_revision_is_validated_and_command_never_enables_mlflow(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="lowercase"):
        MlLifecycleConfig(
            tmp_path / "prices.csv",
            tmp_path / "manifest.json",
            tmp_path / "models",
            "NOT-A-SHA",
        )
    config = MlLifecycleConfig(
        tmp_path / "prices.csv",
        tmp_path / "manifest.json",
        tmp_path / "models",
        "abcdef1",
    )

    command = config.command(Path("python"))

    assert command[1:4] == ("-m", "quantops_ml", "run")
    assert "--code-revision" in command
    assert not any("mlflow" in argument.lower() for argument in command)


def test_default_configs_stay_inside_workspace(workspace_root: Path) -> None:
    configs = default_job_configs(workspace_root)

    assert set(configs) == set(JobName)
    root_text = workspace_root.resolve().as_posix()
    for config in configs.values():
        for value in config.to_mapping().values():
            if isinstance(value, str) and ("/" in value or "\\" in value):
                assert value.startswith(root_text)


@pytest.mark.parametrize(
    ("name", "stdout", "expected"),
    (
        (
            JobName.GENERATE_DEMO_DATASET,
            '{"price_bar_count":12,"quality_accepted_count":10,'
            '"quality_quarantined_count":2,"files_written":3}',
            (12, 10, 2, 3),
        ),
        (JobName.VERIFY_DEMO_DATASET, '{"status":"valid","dataset":"demo"}', (1, 1, 0, 0)),
        (
            JobName.RUN_ML_LIFECYCLE,
            '{"feature_rows":8,"artifacts":{"files_written":4}}',
            (8, 1, 0, 4),
        ),
        (
            JobName.EVALUATE_AI_WORKFLOW,
            '{"case_count":7,"passed":6,"failed":1,"report_path":"report.json"}',
            (7, 6, 1, 1),
        ),
    ),
)
def test_parse_public_cli_summaries(
    name: JobName,
    stdout: str,
    expected: tuple[int, int, int, int],
) -> None:
    parsed = parse_job_output(name, f"diagnostic line\n{stdout}\n")

    assert (
        parsed.counts.processed,
        parsed.counts.succeeded,
        parsed.counts.failed,
        parsed.counts.artifacts_written,
    ) == expected
    assert len(parsed.sha256) == 64


@pytest.mark.parametrize(
    "stdout",
    (
        "",
        "not-json",
        "[]",
        '{"case_count":2,"passed":2,"failed":1,"report_path":null}',
        '{"case_count":true,"passed":1,"failed":0,"report_path":null}',
    ),
)
def test_invalid_ai_summaries_are_rejected(stdout: str) -> None:
    with pytest.raises(InvalidJobOutputError):
        parse_job_output(JobName.EVALUATE_AI_WORKFLOW, stdout)
