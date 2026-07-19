"""Integration tests proving wrappers invoke the existing public CLIs."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from quantops_scheduler.config import (
    AiEvaluationConfig,
    DatasetGenerateConfig,
    DatasetVerifyConfig,
    MlLifecycleConfig,
)
from quantops_scheduler.executor import JobExecutor
from quantops_scheduler.models import JobName, RunStatus
from quantops_scheduler.registry import default_registry
from quantops_scheduler.runtime import InMemoryRunStore, SystemClock
from quantops_scheduler.subprocess_runner import SubprocessCommandRunner


def _real_executor() -> JobExecutor:
    return JobExecutor(
        default_registry(),
        InMemoryRunStore(),
        SubprocessCommandRunner(max_output_bytes=2_097_152),
        SystemClock(),
    )


def test_generate_then_verify_through_public_pipeline_cli(
    workspace_root: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "synthetic"
    executor = _real_executor()
    generated = asyncio.run(
        executor.execute(
            JobName.GENERATE_DEMO_DATASET,
            DatasetGenerateConfig(
                workspace_root / "data" / "synthetic" / "generator_config.json",
                output,
            ),
            scheduled_for=datetime(2032, 1, 1, tzinfo=UTC),
        )
    )
    verified = asyncio.run(
        executor.execute(
            JobName.VERIFY_DEMO_DATASET,
            DatasetVerifyConfig(output),
            scheduled_for=datetime(2032, 1, 2, tzinfo=UTC),
        )
    )

    assert generated.record.status is RunStatus.SUCCEEDED
    assert generated.record.counts.processed == 2_088
    assert generated.record.counts.artifacts_written > 0
    assert verified.record.status is RunStatus.SUCCEEDED
    assert verified.record.counts.succeeded == 1
    assert (output / "manifest.json").is_file()


def test_ai_evaluation_runs_through_public_cli(workspace_root: Path, tmp_path: Path) -> None:
    executor = _real_executor()
    report = tmp_path / "ai-evaluation.json"

    receipt = asyncio.run(
        executor.execute(
            JobName.EVALUATE_AI_WORKFLOW,
            AiEvaluationConfig(
                workspace_root / "packages" / "ai_engine" / "evals" / "v1" / "cases.jsonl",
                report,
            ),
            scheduled_for=datetime(2032, 1, 3, tzinfo=UTC),
        )
    )

    assert receipt.record.status is RunStatus.SUCCEEDED
    assert receipt.record.counts.processed > 0
    assert receipt.record.counts.failed == 0
    assert report.is_file()


def test_ml_lifecycle_runs_through_public_cli(workspace_root: Path, tmp_path: Path) -> None:
    dataset = workspace_root / "data" / "synthetic"
    executor = _real_executor()
    output = tmp_path / "ml"

    receipt = asyncio.run(
        executor.execute(
            JobName.RUN_ML_LIFECYCLE,
            MlLifecycleConfig(
                dataset / "canonical" / "price_bars.csv",
                dataset / "manifest.json",
                output,
            ),
            scheduled_for=datetime(2032, 1, 4, tzinfo=UTC),
        )
    )

    assert receipt.record.status is RunStatus.SUCCEEDED
    assert receipt.record.counts.processed > 0
    assert receipt.record.counts.artifacts_written > 0
    assert output.is_dir()
