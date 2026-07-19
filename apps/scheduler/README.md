# QuantOps scheduler

This package is the Milestone 7 offline orchestration boundary. It registers four jobs and
delegates every business operation to an existing public CLI:

| Job | Public CLI | Default schedule |
| --- | --- | --- |
| `generate_demo_dataset` | `python -m quantops_pipelines generate` | manual only |
| `verify_demo_dataset` | `python -m quantops_pipelines verify` | daily at 03:00 UTC |
| `run_ml_lifecycle` | `python -m quantops_ml run` | Mondays at 04:00 UTC |
| `evaluate_ai_workflow` | `python -m quantops_ai evaluate` | Mondays at 05:00 UTC |

The scheduler does not copy generator, verification, feature, model, promotion, drift, or AI
evaluation logic. Scheduled ML runs explicitly keep MLflow disabled. No job performs database
ingestion and no network service is required by this package or its tests.

## Execution contract

`JobRegistry.plan` hashes the normalized typed configuration and derives a UUIDv5 from job name,
configuration hash, logical UTC time, and dry-run flag. `JobExecutor` reserves that identity before
starting a process. A replay returns the existing terminal or running record without invoking the
CLI again. Records expose only bounded status, counts, hashes, attempts, and replay counts; captured
stdout and stderr are never stored in the ledger.

Set `dry_run=True` on `JobExecutor.execute` to validate and record a plan without spawning a child
process. Each definition has a timeout. Cooperative cancellation cancels the command task, and the
subprocess adapter first terminates and then kills a child that does not exit within its grace
period. Existing CLIs use content-aware writes, but a process terminated during a write may still
leave partial external artifacts; verify outputs before retrying operationally.

`InMemoryRunStore` provides thread-safe idempotency inside one scheduler process. It is deliberately
not described as durable or cross-worker coordination. A production deployment must supply a
durable `RunStore` implementation before relying on idempotency across hosts.

## Optional Airflow boundary

Airflow is intentionally not a package dependency in this offline slice. The discovery module at
`dags/quantops_offline.py` imports safely when Airflow is absent and reports
`SCHEDULER_STATUS = "scheduler_unavailable"`. When compatible Airflow DAG and Python operator APIs
are present, `create_airflow_dags` creates one DAG per registry entry. DAG callbacks reconstruct
typed configuration and call the same framework-neutral executor.

This repository slice proves guarded DAG construction with fakes; it does not claim that an Airflow
service, metadata database, executor, or scheduler daemon is installed or running.

## Local quality gates

From the repository root with the project virtual environment available:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check --no-cache apps/scheduler
.\.venv\Scripts\python.exe -m ruff check --no-cache apps/scheduler
.\.venv\Scripts\python.exe -m mypy --config-file apps/scheduler/pyproject.toml apps/scheduler/src apps/scheduler/tests
.\.venv\Scripts\python.exe -m pytest -c apps/scheduler/pyproject.toml -p no:cacheprovider apps/scheduler/tests -q
```
