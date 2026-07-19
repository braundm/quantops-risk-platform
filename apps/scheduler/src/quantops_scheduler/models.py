"""Immutable job plans, run records, counts, and availability contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from quantops_scheduler.config import JobConfig

_HASH = re.compile(r"^[a-f0-9]{64}$")
_FAILURE_CODE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def _utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be timezone-aware UTC")
    return value.astimezone(UTC)


class JobName(StrEnum):
    GENERATE_DEMO_DATASET = "generate_demo_dataset"
    VERIFY_DEMO_DATASET = "verify_demo_dataset"
    RUN_ML_LIFECYCLE = "run_ml_lifecycle"
    EVALUATE_AI_WORKFLOW = "evaluate_ai_workflow"


class RunStatus(StrEnum):
    PLANNED = "planned"
    DRY_RUN = "dry_run"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    SCHEDULER_UNAVAILABLE = "scheduler_unavailable"


@dataclass(frozen=True, slots=True)
class RunCounts:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    artifacts_written: int = 0

    def __post_init__(self) -> None:
        if min(self.processed, self.succeeded, self.failed, self.artifacts_written) < 0:
            raise ValueError("run counts must be non-negative")


@dataclass(frozen=True, slots=True)
class JobDefinition:
    name: JobName
    description: str
    config_type: type[JobConfig]
    timeout_seconds: float
    schedule: str | None

    def __post_init__(self) -> None:
        if not self.description.strip() or len(self.description) > 240:
            raise ValueError("job description must be non-empty and bounded")
        if not 0.001 <= self.timeout_seconds <= 86_400:
            raise ValueError("job timeout must be between 0.001 and 86400 seconds")
        if self.schedule is not None and not self.schedule.strip():
            raise ValueError("schedule must be non-empty when configured")


@dataclass(frozen=True, slots=True)
class JobPlan:
    run_id: UUID
    definition: JobDefinition
    config: JobConfig
    config_hash: str
    scheduled_for: datetime
    dry_run: bool
    command: tuple[str, ...]

    def __post_init__(self) -> None:
        if _HASH.fullmatch(self.config_hash) is None:
            raise ValueError("config_hash must be SHA-256 hex")
        object.__setattr__(self, "scheduled_for", _utc(self.scheduled_for, "scheduled_for"))
        if not self.command or any(not item for item in self.command):
            raise ValueError("job command must contain non-empty arguments")


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: UUID
    job_name: JobName
    config_hash: str
    scheduled_for: datetime
    dry_run: bool
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    attempt_count: int = 0
    replay_count: int = 0
    counts: RunCounts = field(default_factory=RunCounts)
    output_sha256: str | None = None
    failure_code: str | None = None

    def __post_init__(self) -> None:
        if _HASH.fullmatch(self.config_hash) is None:
            raise ValueError("config_hash must be SHA-256 hex")
        object.__setattr__(self, "scheduled_for", _utc(self.scheduled_for, "scheduled_for"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _utc(self.updated_at, "updated_at"))
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if self.attempt_count < 0 or self.replay_count < 0:
            raise ValueError("run attempt and replay counts must be non-negative")
        if self.output_sha256 is not None and _HASH.fullmatch(self.output_sha256) is None:
            raise ValueError("output_sha256 must be SHA-256 hex")
        if self.failure_code is not None and _FAILURE_CODE.fullmatch(self.failure_code) is None:
            raise ValueError("failure_code must be a safe identifier")


@dataclass(frozen=True, slots=True)
class RunReceipt:
    record: RunRecord
    replayed: bool
    command: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CommandResult:
    return_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class ParsedJobOutput:
    counts: RunCounts
    summary: dict[str, Any]
    sha256: str


@dataclass(frozen=True, slots=True)
class SchedulerAvailability:
    available: bool
    code: str
    detail: str

    def __post_init__(self) -> None:
        if self.code not in {"available", "scheduler_unavailable"}:
            raise ValueError("invalid scheduler availability code")
        if not self.detail or len(self.detail) > 240:
            raise ValueError("availability detail must be non-empty and bounded")


@dataclass(frozen=True, slots=True)
class SchedulerMetricsSnapshot:
    requested: int
    started: int
    succeeded: int
    failed: int
    timed_out: int
    cancelled: int
    dry_runs: int
    duplicates: int
    unavailable: int


@dataclass(slots=True)
class SchedulerMetrics:
    requested: int = 0
    started: int = 0
    succeeded: int = 0
    failed: int = 0
    timed_out: int = 0
    cancelled: int = 0
    dry_runs: int = 0
    duplicates: int = 0
    unavailable: int = 0

    def snapshot(self) -> SchedulerMetricsSnapshot:
        return SchedulerMetricsSnapshot(
            requested=self.requested,
            started=self.started,
            succeeded=self.succeeded,
            failed=self.failed,
            timed_out=self.timed_out,
            cancelled=self.cancelled,
            dry_runs=self.dry_runs,
            duplicates=self.duplicates,
            unavailable=self.unavailable,
        )
