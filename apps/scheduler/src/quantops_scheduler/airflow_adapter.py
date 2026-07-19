"""Optional Airflow DAG construction around the framework-neutral job executor."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import cast

from quantops_scheduler.errors import SchedulerUnavailableError
from quantops_scheduler.executor import JobExecutor
from quantops_scheduler.models import (
    JobName,
    RunStatus,
    SchedulerAvailability,
    SchedulerMetrics,
)
from quantops_scheduler.registry import (
    config_from_mapping,
    default_job_configs,
    default_registry,
)
from quantops_scheduler.runtime import InMemoryRunStore, SystemClock
from quantops_scheduler.subprocess_runner import SubprocessCommandRunner

ModuleImporter = Callable[[str], ModuleType]

_AIRFLOW_STORE = InMemoryRunStore()
_AIRFLOW_METRICS = SchedulerMetrics()


def airflow_availability(*, importer: ModuleImporter = import_module) -> SchedulerAvailability:
    try:
        _airflow_components(importer)
    except SchedulerUnavailableError:
        return SchedulerAvailability(
            available=False,
            code="scheduler_unavailable",
            detail="Airflow is not installed or its Python operator API is unavailable.",
        )
    return SchedulerAvailability(
        available=True,
        code="available",
        detail="Airflow DAG and Python operator APIs are importable.",
    )


def create_airflow_dags(
    workspace_root: Path,
    *,
    importer: ModuleImporter = import_module,
) -> dict[str, object]:
    """Build one guarded Airflow DAG per registered offline job."""
    dag_factory, operator_factory = _airflow_components(importer)
    registry = default_registry()
    configs = default_job_configs(workspace_root)
    dags: dict[str, object] = {}
    for definition in registry.definitions:
        dag_id = f"quantops_{definition.name.value}"
        dag = dag_factory(
            dag_id=dag_id,
            schedule=definition.schedule,
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            catchup=False,
            max_active_runs=1,
            tags=["quantops", "offline"],
        )
        operator_factory(
            task_id="run_registered_job",
            python_callable=airflow_task_entrypoint,
            op_kwargs={
                "job_name": definition.name.value,
                "config": configs[definition.name].to_mapping(),
                "scheduled_for": "{{ logical_date.isoformat() }}",
                "dry_run": False,
            },
            dag=dag,
        )
        dags[dag_id] = dag
    return dags


def airflow_task_entrypoint(
    *,
    job_name: str,
    config: Mapping[str, object],
    scheduled_for: str,
    dry_run: bool = False,
) -> dict[str, object]:
    """Execute a registered job from Airflow without importing business internals."""
    name = JobName(job_name)
    parsed_time = _parse_scheduled_for(scheduled_for)
    executor = JobExecutor(
        default_registry(),
        _AIRFLOW_STORE,
        SubprocessCommandRunner(),
        SystemClock(),
        metrics=_AIRFLOW_METRICS,
    )
    receipt = asyncio.run(
        executor.execute(
            name,
            config_from_mapping(name, config),
            scheduled_for=parsed_time,
            dry_run=dry_run,
        )
    )
    record = receipt.record
    if record.status not in {RunStatus.DRY_RUN, RunStatus.SUCCEEDED}:
        code = record.failure_code or "unknown"
        raise RuntimeError(f"scheduled job ended with status={record.status.value} code={code}")
    return {
        "run_id": str(record.run_id),
        "job_name": record.job_name.value,
        "status": record.status.value,
        "config_hash": record.config_hash,
        "scheduled_for": record.scheduled_for.isoformat().replace("+00:00", "Z"),
        "replayed": receipt.replayed,
        "attempt_count": record.attempt_count,
        "replay_count": record.replay_count,
        "counts": {
            "processed": record.counts.processed,
            "succeeded": record.counts.succeeded,
            "failed": record.counts.failed,
            "artifacts_written": record.counts.artifacts_written,
        },
    }


def _airflow_components(
    importer: ModuleImporter,
) -> tuple[Callable[..., object], Callable[..., object]]:
    try:
        airflow_module = importer("airflow")
        operator_module = importer("airflow.operators.python")
        dag_factory = cast(Callable[..., object], airflow_module.DAG)
        operator_factory = cast(Callable[..., object], operator_module.PythonOperator)
    except (ImportError, AttributeError) as error:
        raise SchedulerUnavailableError from error
    return dag_factory, operator_factory


def _parse_scheduled_for(value: str) -> datetime:
    if not value:
        raise ValueError("scheduled_for must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("scheduled_for must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("scheduled_for must be timezone-aware")
    return parsed.astimezone(UTC)
