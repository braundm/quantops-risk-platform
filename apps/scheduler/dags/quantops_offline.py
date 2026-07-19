"""Guarded Airflow discovery module; safe to import without Airflow installed."""

from pathlib import Path

from quantops_scheduler.airflow_adapter import create_airflow_dags
from quantops_scheduler.errors import SchedulerUnavailableError

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]

try:
    DAG_OBJECTS = create_airflow_dags(WORKSPACE_ROOT)
except SchedulerUnavailableError:
    DAG_OBJECTS: dict[str, object] = {}
    SCHEDULER_STATUS = "scheduler_unavailable"
else:
    SCHEDULER_STATUS = "available"
    globals().update(DAG_OBJECTS)
