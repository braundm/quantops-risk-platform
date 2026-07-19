"""Framework-neutral command, clock, and run-store ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from quantops_scheduler.models import CommandResult, JobPlan, RunRecord


@runtime_checkable
class CommandRunner(Protocol):
    async def run(self, command: tuple[str, ...]) -> CommandResult: ...


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class RunStore(Protocol):
    def reserve(self, plan: JobPlan, *, at: datetime) -> tuple[RunRecord, bool]: ...

    def mark_running(self, run_id: UUID, *, at: datetime) -> RunRecord: ...

    def finish(self, record: RunRecord) -> RunRecord: ...

    def get(self, run_id: UUID) -> RunRecord | None: ...
