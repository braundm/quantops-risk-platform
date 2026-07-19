"""Small process-local runtime adapters for scheduler execution."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID

from quantops_scheduler.models import JobPlan, RunRecord, RunStatus


class SystemClock:
    """UTC wall clock used at scheduler boundaries."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class InMemoryRunStore:
    """Thread-safe process-local run ledger with deterministic replay handling."""

    def __init__(self) -> None:
        self._records: dict[UUID, RunRecord] = {}
        self._lock = RLock()

    def reserve(self, plan: JobPlan, *, at: datetime) -> tuple[RunRecord, bool]:
        with self._lock:
            current = self._records.get(plan.run_id)
            if current is not None:
                if (
                    current.job_name is not plan.definition.name
                    or current.config_hash != plan.config_hash
                    or current.scheduled_for != plan.scheduled_for
                    or current.dry_run != plan.dry_run
                ):
                    raise ValueError("run identity collision")
                replayed = replace(
                    current,
                    replay_count=current.replay_count + 1,
                    updated_at=max(current.updated_at, at),
                )
                self._records[plan.run_id] = replayed
                return replayed, False
            record = RunRecord(
                run_id=plan.run_id,
                job_name=plan.definition.name,
                config_hash=plan.config_hash,
                scheduled_for=plan.scheduled_for,
                dry_run=plan.dry_run,
                status=RunStatus.PLANNED,
                created_at=at,
                updated_at=at,
            )
            self._records[plan.run_id] = record
            return record, True

    def mark_running(self, run_id: UUID, *, at: datetime) -> RunRecord:
        with self._lock:
            current = self._required(run_id)
            if current.status is not RunStatus.PLANNED:
                raise ValueError("only planned runs can start")
            running = replace(
                current,
                status=RunStatus.RUNNING,
                attempt_count=current.attempt_count + 1,
                updated_at=max(current.updated_at, at),
            )
            self._records[run_id] = running
            return running

    def finish(self, record: RunRecord) -> RunRecord:
        final_statuses = {
            RunStatus.DRY_RUN,
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.TIMED_OUT,
            RunStatus.CANCELLED,
            RunStatus.SCHEDULER_UNAVAILABLE,
        }
        if record.status not in final_statuses:
            raise ValueError("finish requires a terminal run status")
        with self._lock:
            current = self._required(record.run_id)
            allowed = (
                current.status is RunStatus.PLANNED and record.status is RunStatus.DRY_RUN
            ) or current.status is RunStatus.RUNNING
            if not allowed:
                raise ValueError("invalid run status transition")
            if (
                current.job_name is not record.job_name
                or current.config_hash != record.config_hash
                or current.scheduled_for != record.scheduled_for
                or current.dry_run != record.dry_run
                or current.created_at != record.created_at
                or current.attempt_count != record.attempt_count
                or current.replay_count != record.replay_count
            ):
                raise ValueError("immutable run identity fields changed")
            self._records[record.run_id] = record
            return record

    def get(self, run_id: UUID) -> RunRecord | None:
        with self._lock:
            return self._records.get(run_id)

    def _required(self, run_id: UUID) -> RunRecord:
        try:
            return self._records[run_id]
        except KeyError as error:
            raise KeyError(f"unknown run: {run_id}") from error
