# QuantOps handoff

Last updated: 2026-07-19

## Current state

The repository began empty. The authoritative master specification has been read in full. Milestone 0 is committed as `102406d`, domain as `af3ac48`, risk as `1027ef2`, deterministic data as `f747731`, PostgreSQL persistence as `9bdd210`, event contracts as `764b545`, the deterministic frontend as `3aefae6`, the application API as `72cfa24`, and the offline ML lifecycle as `2718de5`. The bounded grounded-AI package now passes 110 tests at 97% branch-aware coverage and all 44 versioned deterministic evaluations. Its default provider needs no key; citations, numbers, scope, safety, and tool budgets are validated. A real clean-database migration remains unverified because PostgreSQL/Docker is unavailable.

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
PYTHONPATH=apps/api;packages/domain .venv\Scripts\alembic.exe -c apps/api/alembic.ini upgrade head --sql
.venv\Scripts\uv.exe build apps/api --offline
.venv\Scripts\pytest.exe -c ml/pyproject.toml ml/tests --cov=quantops_ml --cov-branch -q
.venv\Scripts\mypy.exe --config-file ml/pyproject.toml -p quantops_ml -p ml.tests
.venv\Scripts\python.exe -m quantops_ml run --prices data/synthetic/canonical/price_bars.csv --manifest data/synthetic/manifest.json --output ml/artifacts/demo --code-revision 72cfa241760ffb02e682ef58caab176bedab41d1
.venv\Scripts\pytest.exe -c packages/ai_engine/pyproject.toml packages/ai_engine/tests --cov=quantops_ai --cov-branch -q
.venv\Scripts\mypy.exe --config-file packages/ai_engine/pyproject.toml -p quantops_ai -p packages.ai_engine.tests
.venv\Scripts\python.exe -m quantops_ai evaluate --cases packages/ai_engine/evals/v1/cases.jsonl --output $env:TEMP\quantops-ai-evaluation-root.json
.venv\Scripts\pytest.exe -c packages/data_contracts/pyproject.toml packages/data_contracts/tests --cov=quantops_contracts --cov-branch -q
.venv\Scripts\mypy.exe --config-file packages/data_contracts/pyproject.toml packages/data_contracts/src/quantops_contracts packages/data_contracts/tests
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

Commit the reviewed grounded-AI package, then finish its deterministic API integration. Review the
parallel stream-worker and MCP packages when their isolated gates finish. Connect idempotent
database seeding and live persistence integration when PostgreSQL is available.

## Uncommitted changes

Grounded AI, its API integration, security/architecture/ADR documents, stream-worker, MCP, and root
workspace/lock changes are separate in-progress scopes; inspect `git status` before modifying them.
