# QuantOps handoff

Last updated: 2026-07-19

## Current state

The repository began empty. The authoritative master specification has been read in full. Milestone 0 is committed as `102406d`, domain as `af3ac48`, risk as `1027ef2`, and deterministic data as `f747731`. The PostgreSQL schema, Alembic revision, async adapters, and persistence tests are implemented locally and ready for the next focused commit. A real clean-database migration remains unverified because PostgreSQL/Docker is unavailable.

## Architecture in force

Use a modular monolith for synchronous business behavior, framework-free domain/risk packages, and separate worker processes only where replay, scheduling, or isolation is justified. PostgreSQL is the source of record; Redpanda, Airflow, MLflow, external LLM providers, and observability are optional profiles.

## Toolchain discovered

- System Python: 3.13.7 (`C:\\Python3.13\\python.exe`), with pip but no project dependencies installed.
- Bundled Codex Python: 3.12.13.
- Bundled Codex Node: 24.14.0; pnpm: 11.9.0.
- Bundled Codex Git: 2.53.0.
- Workspace `uv`: 0.11.29; locked Python dependencies resolve successfully.
- Project package manager declaration: pnpm 11.15.0. Bundled pnpm 11.9.0 was used only as the verification runtime and the frozen lockfile passes.
- Docker, GitHub CLI, GNU Make, `uv`, and Terraform are not on the system `PATH`.
- The directory was not a Git repository at discovery time.

## Last successful commands

```text
Get-Content -Encoding UTF8 C:\Users\domin\Downloads\QuantOps_AI_Codex_Master_Prompt.md
C:\Users\domin\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe --version
C:\Users\domin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --version
C:\Users\domin\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd --version
.venv\Scripts\uv.exe sync --locked --all-packages
.venv\Scripts\ruff.exe check apps/api scripts
.venv\Scripts\mypy.exe apps/api
.venv\Scripts\pytest.exe apps/api/tests -m "not integration" -q
PYTHONPATH=apps/api;packages/domain .venv\Scripts\alembic.exe -c apps/api/alembic.ini upgrade head --sql
.venv\Scripts\uv.exe build apps/api --offline
pnpm --filter @quantops/web lint
pnpm --filter @quantops/web typecheck
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
.venv\Scripts\python.exe scripts/docs_check.py
```

## Blockers and limitations

- Docker-backed PostgreSQL/Redpanda tests cannot run until Docker is available.
- GitHub publication cannot occur until the project is complete and `gh` authentication is available.
- Any command not yet listed in `docs/progress.md` as passing must be treated as unverified.

## Exact next action

Commit the verified persistence slice, then integrate the versioned event-contract package. After
that, continue application services/API and connect idempotent database seeding when PostgreSQL is
available.

## Uncommitted changes

Persistence schema/adapters/tests, `docs/data-model.md`, dependency-lock updates, and the separate
`packages/data_contracts` package are currently uncommitted. Frontend Milestone 5 work may also be
in progress; inspect `git status` before modifying `apps/web`.
