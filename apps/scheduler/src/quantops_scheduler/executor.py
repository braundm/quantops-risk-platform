"""Framework-neutral scheduler executor with deterministic replay semantics."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from quantops_scheduler.config import JobConfig
from quantops_scheduler.errors import (
    ExplicitCancellation,
    InvalidJobOutputError,
    OutputLimitError,
    SchedulerUnavailableError,
)
from quantops_scheduler.models import (
    CommandResult,
    JobName,
    RunCounts,
    RunReceipt,
    RunRecord,
    RunStatus,
    SchedulerMetrics,
)
from quantops_scheduler.output import parse_job_output
from quantops_scheduler.ports import Clock, CommandRunner, RunStore
from quantops_scheduler.registry import JobRegistry


class JobExecutor:
    def __init__(
        self,
        registry: JobRegistry,
        store: RunStore,
        runner: CommandRunner,
        clock: Clock,
        *,
        metrics: SchedulerMetrics | None = None,
    ) -> None:
        self._registry = registry
        self._store = store
        self._runner = runner
        self._clock = clock
        self.metrics = metrics or SchedulerMetrics()

    async def execute(
        self,
        name: JobName,
        config: JobConfig,
        *,
        scheduled_for: datetime,
        dry_run: bool = False,
        cancel_event: asyncio.Event | None = None,
        python_executable: Path | None = None,
    ) -> RunReceipt:
        self.metrics.requested += 1
        plan = self._registry.plan(
            name,
            config,
            scheduled_for=scheduled_for,
            dry_run=dry_run,
            python_executable=python_executable,
        )
        record, reserved = self._store.reserve(plan, at=self._clock.now())
        if not reserved:
            self.metrics.duplicates += 1
            return RunReceipt(record=record, replayed=True, command=plan.command)

        if dry_run:
            final = self._store.finish(
                replace(record, status=RunStatus.DRY_RUN, updated_at=self._clock.now())
            )
            self.metrics.dry_runs += 1
            return RunReceipt(record=final, replayed=False, command=plan.command)

        running = self._store.mark_running(plan.run_id, at=self._clock.now())
        self.metrics.started += 1
        try:
            async with asyncio.timeout(plan.definition.timeout_seconds):
                result = await self._run_command(plan.command, cancel_event)
        except TimeoutError:
            final = self._terminal(running, RunStatus.TIMED_OUT, "job_timed_out")
            self.metrics.timed_out += 1
        except ExplicitCancellation:
            final = self._terminal(running, RunStatus.CANCELLED, "cancelled")
            self.metrics.cancelled += 1
        except SchedulerUnavailableError:
            final = self._terminal(
                running,
                RunStatus.SCHEDULER_UNAVAILABLE,
                SchedulerUnavailableError.code,
            )
            self.metrics.unavailable += 1
        except OutputLimitError:
            final = self._terminal(running, RunStatus.FAILED, OutputLimitError.code)
            self.metrics.failed += 1
        except asyncio.CancelledError:
            self._terminal(running, RunStatus.CANCELLED, "cancelled")
            self.metrics.cancelled += 1
            raise
        except Exception:
            final = self._terminal(running, RunStatus.FAILED, "job_execution_failed")
            self.metrics.failed += 1
        else:
            final = self._from_result(running, result)
        return RunReceipt(record=final, replayed=False, command=plan.command)

    async def _run_command(
        self,
        command: tuple[str, ...],
        cancel_event: asyncio.Event | None,
    ) -> CommandResult:
        if cancel_event is None:
            return await self._runner.run(command)
        command_task = asyncio.create_task(self._runner.run(command))
        cancellation_task = asyncio.create_task(cancel_event.wait())
        try:
            await asyncio.wait(
                {command_task, cancellation_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if command_task.done():
                return await command_task
            command_task.cancel()
            with suppress(asyncio.CancelledError):
                await command_task
            raise ExplicitCancellation
        except asyncio.CancelledError:
            command_task.cancel()
            with suppress(asyncio.CancelledError):
                await command_task
            raise
        finally:
            cancellation_task.cancel()
            with suppress(asyncio.CancelledError):
                await cancellation_task

    def _from_result(self, running: RunRecord, result: CommandResult) -> RunRecord:
        if result.return_code != 0:
            counts = RunCounts()
            output_sha256: str | None = None
            with suppress(InvalidJobOutputError):
                parsed = parse_job_output(running.job_name, result.stdout)
                counts = parsed.counts
                output_sha256 = parsed.sha256
            self.metrics.failed += 1
            return self._terminal(
                running,
                RunStatus.FAILED,
                "job_exit_nonzero",
                counts=counts,
                output_sha256=output_sha256,
            )
        try:
            parsed = parse_job_output(running.job_name, result.stdout)
        except InvalidJobOutputError:
            self.metrics.failed += 1
            return self._terminal(running, RunStatus.FAILED, InvalidJobOutputError.code)
        self.metrics.succeeded += 1
        return self._terminal(
            running,
            RunStatus.SUCCEEDED,
            None,
            counts=parsed.counts,
            output_sha256=parsed.sha256,
        )

    def _terminal(
        self,
        running: RunRecord,
        status: RunStatus,
        failure_code: str | None,
        *,
        counts: RunCounts | None = None,
        output_sha256: str | None = None,
    ) -> RunRecord:
        return self._store.finish(
            replace(
                running,
                status=status,
                updated_at=self._clock.now(),
                counts=counts or RunCounts(),
                output_sha256=output_sha256,
                failure_code=failure_code,
            )
        )
