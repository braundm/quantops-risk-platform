# QuantOps handoff

Last updated: 2026-07-19

## Current state

The repository began empty. The authoritative master specification has been read in full. Milestone 0 is committed as `102406d`, domain as `af3ac48`, and the verified risk engine as `1027ef2`. The deterministic fixture/data-quality package passes 19 tests and 92% combined branch coverage; database seed/upsert is still pending. Persistence is under active implementation.

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
.venv\Scripts\pytest.exe apps/api/tests -q
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

Commit the verified synthetic fixture/data-quality foundation, then finish persistence adapters/migrations and connect idempotent database seeding.

## Uncommitted changes

Foundation files are intentionally uncommitted until Milestone 0 gates pass.
