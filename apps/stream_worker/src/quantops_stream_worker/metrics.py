"""Small in-process counters with immutable snapshots."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    processed: int
    duplicates: int
    late: int
    rejected: int
    retries: int
    dead_lettered: int
    commits: int
    broker_outages: int


@dataclass(slots=True)
class WorkerMetrics:
    processed: int = 0
    duplicates: int = 0
    late: int = 0
    rejected: int = 0
    retries: int = 0
    dead_lettered: int = 0
    commits: int = 0
    broker_outages: int = 0

    def snapshot(self) -> MetricsSnapshot:
        return MetricsSnapshot(
            processed=self.processed,
            duplicates=self.duplicates,
            late=self.late,
            rejected=self.rejected,
            retries=self.retries,
            dead_lettered=self.dead_lettered,
            commits=self.commits,
            broker_outages=self.broker_outages,
        )
