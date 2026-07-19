"""Executor state, idempotency, cancellation, and observability tests."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from quantops_scheduler.config import AiEvaluationConfig, DatasetVerifyConfig
from quantops_scheduler.errors import SchedulerUnavailableError
from quantops_scheduler.executor import JobExecutor
from quantops_scheduler.models import (
    CommandResult,
    JobDefinition,
    JobName,
    RunStatus,
    SchedulerMetrics,
)
from quantops_scheduler.registry import JobRegistry, default_registry
from quantops_scheduler.runtime import InMemoryRunStore

LOGICAL_TIME = datetime(2026, 7, 19, 12, tzinfo=UTC)


@dataclass(slots=True)
class FrozenClock:
    value: datetime = LOGICAL_TIME

    def now(self) -> datetime:
        return self.value


@dataclass(slots=True)
class ResultRunner:
    result: CommandResult
    calls: list[tuple[str, ...]] = field(default_factory=list)

    async def run(self, command: tuple[str, ...]) -> CommandResult:
        self.calls.append(command)
        return self.result


class BlockingRunner:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False

    async def run(self, command: tuple[str, ...]) -> CommandResult:
        del command
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("blocking runner unexpectedly resumed")


class UnavailableRunner:
    async def run(self, command: tuple[str, ...]) -> CommandResult:
        del command
        raise SchedulerUnavailableError


class ExplodingRunner:
    async def run(self, command: tuple[str, ...]) -> CommandResult:
        del command
        raise RuntimeError("a sensitive internal detail")


def _executor(
    runner: ResultRunner | BlockingRunner | UnavailableRunner | ExplodingRunner,
    *,
    registry: JobRegistry | None = None,
) -> tuple[JobExecutor, InMemoryRunStore, SchedulerMetrics]:
    store = InMemoryRunStore()
    metrics = SchedulerMetrics()
    return (
        JobExecutor(
            registry or default_registry(),
            store,
            runner,
            FrozenClock(),
            metrics=metrics,
        ),
        store,
        metrics,
    )


def test_dry_run_records_plan_without_invoking_command(tmp_path: Path) -> None:
    runner = ResultRunner(CommandResult(0, '{"status":"valid"}', ""))
    executor, _, metrics = _executor(runner)

    receipt = asyncio.run(
        executor.execute(
            JobName.VERIFY_DEMO_DATASET,
            DatasetVerifyConfig(tmp_path),
            scheduled_for=LOGICAL_TIME,
            dry_run=True,
        )
    )

    assert receipt.record.status is RunStatus.DRY_RUN
    assert receipt.record.attempt_count == 0
    assert not receipt.replayed
    assert runner.calls == []
    assert metrics.snapshot().dry_runs == 1


def test_success_is_counted_and_duplicate_is_not_reexecuted(tmp_path: Path) -> None:
    runner = ResultRunner(CommandResult(0, '{"status":"valid","dataset":"demo"}', ""))
    executor, _, metrics = _executor(runner)
    config = DatasetVerifyConfig(tmp_path)

    first = asyncio.run(
        executor.execute(
            JobName.VERIFY_DEMO_DATASET,
            config,
            scheduled_for=LOGICAL_TIME,
        )
    )
    replay = asyncio.run(
        executor.execute(
            JobName.VERIFY_DEMO_DATASET,
            config,
            scheduled_for=LOGICAL_TIME,
        )
    )

    assert first.record.status is RunStatus.SUCCEEDED
    assert first.record.counts.succeeded == 1
    assert replay.replayed
    assert replay.record.run_id == first.record.run_id
    assert replay.record.replay_count == 1
    assert len(runner.calls) == 1
    assert metrics.snapshot().succeeded == 1
    assert metrics.snapshot().duplicates == 1


def test_new_logical_time_gets_a_new_attempt(tmp_path: Path) -> None:
    runner = ResultRunner(CommandResult(0, '{"status":"valid"}', ""))
    executor, _, _ = _executor(runner)
    config = DatasetVerifyConfig(tmp_path)

    first = asyncio.run(
        executor.execute(
            JobName.VERIFY_DEMO_DATASET,
            config,
            scheduled_for=LOGICAL_TIME,
        )
    )
    second = asyncio.run(
        executor.execute(
            JobName.VERIFY_DEMO_DATASET,
            config,
            scheduled_for=datetime(2026, 7, 20, 12, tzinfo=UTC),
        )
    )

    assert first.record.run_id != second.record.run_id
    assert len(runner.calls) == 2


def test_nonzero_exit_preserves_safe_counts_but_never_stderr(tmp_path: Path) -> None:
    summary = {"case_count": 3, "passed": 2, "failed": 1, "report_path": None}
    runner = ResultRunner(CommandResult(1, json.dumps(summary), "secret-token-value"))
    executor, _, metrics = _executor(runner)

    receipt = asyncio.run(
        executor.execute(
            JobName.EVALUATE_AI_WORKFLOW,
            AiEvaluationConfig(tmp_path / "cases.jsonl"),
            scheduled_for=LOGICAL_TIME,
        )
    )

    assert receipt.record.status is RunStatus.FAILED
    assert receipt.record.failure_code == "job_exit_nonzero"
    assert receipt.record.counts.failed == 1
    assert "secret" not in repr(receipt.record)
    assert metrics.snapshot().failed == 1


def test_invalid_success_output_becomes_safe_failure(tmp_path: Path) -> None:
    runner = ResultRunner(CommandResult(0, "not-json", ""))
    executor, _, _ = _executor(runner)

    receipt = asyncio.run(
        executor.execute(
            JobName.VERIFY_DEMO_DATASET,
            DatasetVerifyConfig(tmp_path),
            scheduled_for=LOGICAL_TIME,
        )
    )

    assert receipt.record.status is RunStatus.FAILED
    assert receipt.record.failure_code == "invalid_job_output"


def test_timeout_cancels_runner_and_records_timeout(tmp_path: Path) -> None:
    runner = BlockingRunner()
    registry = JobRegistry(
        (
            JobDefinition(
                JobName.VERIFY_DEMO_DATASET,
                "Short timeout for deterministic testing.",
                DatasetVerifyConfig,
                0.01,
                None,
            ),
        )
    )
    executor, _, metrics = _executor(runner, registry=registry)

    receipt = asyncio.run(
        executor.execute(
            JobName.VERIFY_DEMO_DATASET,
            DatasetVerifyConfig(tmp_path),
            scheduled_for=LOGICAL_TIME,
        )
    )

    assert receipt.record.status is RunStatus.TIMED_OUT
    assert receipt.record.failure_code == "job_timed_out"
    assert runner.cancelled
    assert metrics.snapshot().timed_out == 1


def test_explicit_cancellation_is_terminal(tmp_path: Path) -> None:
    async def scenario() -> tuple[RunStatus, bool, int]:
        runner = BlockingRunner()
        executor, _, metrics = _executor(runner)
        event = asyncio.Event()
        event.set()
        receipt = await executor.execute(
            JobName.VERIFY_DEMO_DATASET,
            DatasetVerifyConfig(tmp_path),
            scheduled_for=LOGICAL_TIME,
            cancel_event=event,
        )
        return receipt.record.status, runner.cancelled, metrics.snapshot().cancelled

    status, runner_cancelled, metric = asyncio.run(scenario())

    assert status is RunStatus.CANCELLED
    assert runner_cancelled
    assert metric == 1


def test_task_cancellation_updates_ledger_then_propagates(tmp_path: Path) -> None:
    async def scenario() -> tuple[RunStatus | None, bool]:
        runner = BlockingRunner()
        executor, store, _ = _executor(runner)
        config = DatasetVerifyConfig(tmp_path)
        task = asyncio.create_task(
            executor.execute(
                JobName.VERIFY_DEMO_DATASET,
                config,
                scheduled_for=LOGICAL_TIME,
            )
        )
        await runner.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        plan = default_registry().plan(
            JobName.VERIFY_DEMO_DATASET,
            config,
            scheduled_for=LOGICAL_TIME,
        )
        record = store.get(plan.run_id)
        return None if record is None else record.status, runner.cancelled

    status, runner_cancelled = asyncio.run(scenario())

    assert status is RunStatus.CANCELLED
    assert runner_cancelled


def test_unavailable_and_unexpected_failures_are_sanitized(tmp_path: Path) -> None:
    unavailable, _, unavailable_metrics = _executor(UnavailableRunner())
    unavailable_receipt = asyncio.run(
        unavailable.execute(
            JobName.VERIFY_DEMO_DATASET,
            DatasetVerifyConfig(tmp_path),
            scheduled_for=LOGICAL_TIME,
        )
    )
    exploding, _, failed_metrics = _executor(ExplodingRunner())
    failed_receipt = asyncio.run(
        exploding.execute(
            JobName.VERIFY_DEMO_DATASET,
            DatasetVerifyConfig(tmp_path),
            scheduled_for=LOGICAL_TIME,
        )
    )

    assert unavailable_receipt.record.status is RunStatus.SCHEDULER_UNAVAILABLE
    assert unavailable_receipt.record.failure_code == "scheduler_unavailable"
    assert unavailable_metrics.snapshot().unavailable == 1
    assert failed_receipt.record.status is RunStatus.FAILED
    assert failed_receipt.record.failure_code == "job_execution_failed"
    assert "sensitive" not in repr(failed_receipt.record)
    assert failed_metrics.snapshot().failed == 1
