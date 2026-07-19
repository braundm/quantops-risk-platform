"""Guarded Airflow integration tests using local fakes only."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

from quantops_scheduler.airflow_adapter import (
    airflow_availability,
    airflow_task_entrypoint,
    create_airflow_dags,
)
from quantops_scheduler.errors import SchedulerUnavailableError
from quantops_scheduler.models import JobName
from quantops_scheduler.registry import default_job_configs


class FakeDag:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.tasks: list[FakePythonOperator] = []


class FakePythonOperator:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        dag = kwargs.get("dag")
        if not isinstance(dag, FakeDag):
            raise TypeError("fake operator requires a fake DAG")
        dag.tasks.append(self)


def _fake_importer(name: str) -> ModuleType:
    module = ModuleType(name)
    if name == "airflow":
        module.__dict__["DAG"] = FakeDag
        return module
    if name == "airflow.operators.python":
        module.__dict__["PythonOperator"] = FakePythonOperator
        return module
    raise ModuleNotFoundError(name)


def _missing_importer(name: str) -> ModuleType:
    raise ModuleNotFoundError(name)


def test_missing_airflow_reports_stable_unavailable_status(workspace_root: Path) -> None:
    availability = airflow_availability(importer=_missing_importer)

    assert not availability.available
    assert availability.code == "scheduler_unavailable"
    with pytest.raises(SchedulerUnavailableError):
        create_airflow_dags(workspace_root, importer=_missing_importer)


def test_fake_airflow_builds_one_non_catchup_dag_per_job(workspace_root: Path) -> None:
    availability = airflow_availability(importer=_fake_importer)
    dags = create_airflow_dags(workspace_root, importer=_fake_importer)

    assert availability.available
    assert set(dags) == {f"quantops_{name.value}" for name in JobName}
    for dag in dags.values():
        assert isinstance(dag, FakeDag)
        assert dag.kwargs["catchup"] is False
        assert dag.kwargs["max_active_runs"] == 1
        assert len(dag.tasks) == 1
        task = dag.tasks[0]
        assert task.kwargs["task_id"] == "run_registered_job"
        assert task.kwargs["python_callable"] is airflow_task_entrypoint
        op_kwargs = task.kwargs["op_kwargs"]
        assert isinstance(op_kwargs, dict)
        assert op_kwargs["scheduled_for"] == "{{ logical_date.isoformat() }}"


def test_airflow_callback_supports_dry_run_without_child_process(
    workspace_root: Path,
) -> None:
    config = default_job_configs(workspace_root)[JobName.VERIFY_DEMO_DATASET]

    result = airflow_task_entrypoint(
        job_name=JobName.VERIFY_DEMO_DATASET.value,
        config=config.to_mapping(),
        scheduled_for="2031-01-02T03:04:05Z",
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["attempt_count"] == 0
    assert result["counts"] == {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "artifacts_written": 0,
    }


def test_dag_discovery_file_is_guarded_and_contains_no_business_imports(
    workspace_root: Path,
) -> None:
    source = (workspace_root / "apps" / "scheduler" / "dags" / "quantops_offline.py").read_text(
        encoding="utf-8"
    )

    assert "except SchedulerUnavailableError" in source
    assert 'SCHEDULER_STATUS = "scheduler_unavailable"' in source
    for forbidden in (
        "from quantops_pipelines",
        "from quantops_ml",
        "from quantops_ai",
        "generate_dataset(",
        "verify_dataset(",
    ):
        assert forbidden not in source


def test_operator_callback_is_typed_callable() -> None:
    callback: Callable[..., dict[str, object]] = airflow_task_entrypoint

    assert callback is airflow_task_entrypoint
