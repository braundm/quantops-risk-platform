# QuantOps implementation progress

Last updated: 2026-07-19

This file records observed results only. An unchecked item is not implemented or has not yet met its exit evidence.

## Milestone 0 — discovery and foundation

- [x] Read the authoritative 2,442-line master specification in full.
- [x] Confirm the workspace was empty and unrelated owner work would not be overwritten.
- [x] Inspect system and bundled Python, Node, pnpm, Git, Docker, `uv`, `gh`, Make, and Terraform availability.
- [x] Create the implementation plan and risk register.
- [x] Scaffold the initial monorepo, Compose core, safe local configuration, and continuity files.
- [x] Verify the locked Python workspace install.
- [x] Verify Python format/lint/type checks and backend smoke tests.
- [x] Verify pnpm install, peer dependencies, frontend lint/type checks/tests/build.
- [x] Verify repository hygiene and targeted secret-pattern scan.
- [x] Initialize Git on `main`.
- [x] Create the first scoped commit (`102406d`).

Observed commands:

```text
python --version
# Python 3.13.7

C:\Users\domin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe --version
# Python 3.12.13

C:\Users\domin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe --version
# v24.14.0

C:\Users\domin\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd --version
# 11.9.0 (bundled verification runtime; project declares current pnpm 11.15.0)

C:\Users\domin\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe --version
# git version 2.53.0.windows.3
```

Unavailable on system `PATH`: `git`, `uv`, `node`, `npm`, `pnpm`, `docker`, `gh`, `make`, and `terraform`. Bundled Git/Node/pnpm are usable by absolute path. Docker-backed checks remain pending.

Verified foundation gates:

```text
.venv\Scripts\uv.exe sync --locked --all-packages
# exit 0; resolved 70 packages, checked 68

.venv\Scripts\ruff.exe check apps/api scripts
# exit 0; All checks passed

.venv\Scripts\ruff.exe format --check apps/api scripts
# exit 0; 12 files already formatted

.venv\Scripts\mypy.exe apps/api
# exit 0; 9 source files, no issues

.venv\Scripts\pytest.exe apps/api/tests -q
# exit 0; 3 passed

pnpm install --frozen-lockfile --offline
# exit 0; lockfile already up to date

pnpm peers check
# exit 0; no peer dependency issues

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web typecheck
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
# all exit 0; 1 Vitest test passed; Vite 8.1.5 production build completed

.venv\Scripts\python.exe scripts/docs_check.py
# exit 0; 12 repository-owned Markdown files checked
```

Targeted scans found no known private-key, AWS, GitHub, OpenAI-style, or Slack token patterns and no repository-owned file over 1 MiB. This is not yet a substitute for the deeper Milestone 12 security gates.

## Milestone 1 — domain and persistence

- [x] Framework-independent value objects, entities, and repository ports.
- [ ] SQLAlchemy mappings and asynchronous repositories.
- [ ] Clean-database Alembic migration and PostgreSQL constraints/indexes.
- [ ] Optimistic concurrency, audit, and transactional outbox integration tests.
- [ ] ER model documentation.

Verified domain-package gates:

```text
.venv\Scripts\pytest.exe packages/domain/tests --cov=quantops_domain --cov-branch -q
# exit 0; 34 passed, 6 subtests passed; 84% combined branch coverage

.venv\Scripts\ruff.exe check packages/domain
.venv\Scripts\ruff.exe format --check packages/domain
# both exit 0

.venv\Scripts\mypy.exe packages/domain/quantops_domain packages/domain/tests
# exit 0; 15 source files, no issues

.venv\Scripts\uv.exe build --package quantops-domain --offline
# exit 0; sdist and wheel built
```

Persistence, migrations, database constraints, and PostgreSQL integration evidence remain pending; therefore Milestone 1 is not complete.

## Milestone 2 — synthetic market and data quality

- [x] Deterministic two-year synthetic dataset and manifest.
- [x] Intentional duplicate, late, missing, and malformed quality cases.
- [ ] Idempotent seed/upsert and quarantine path.
- [x] Lineage and byte-reproducibility tests.

File-generation, validation, and quarantine are implemented; PostgreSQL seed/upsert remains pending, so Milestone 2 is not yet complete.

Verified synthetic-data gates:

```text
.venv\Scripts\pytest.exe -c pipelines/pyproject.toml pipelines/tests --cov=quantops_pipelines --cov-branch -q
# exit 0; 19 passed; 92% combined branch coverage

.venv\Scripts\ruff.exe check pipelines
.venv\Scripts\ruff.exe format --check pipelines
# both exit 0

.venv\Scripts\mypy.exe --config-file pipelines/pyproject.toml pipelines/src/quantops_pipelines pipelines/tests
# exit 0; 10 source files, no issues

PYTHONPATH=pipelines/src .venv\Scripts\python.exe -m quantops_pipelines verify --dataset data/synthetic
# exit 0; status valid

PYTHONPATH=pipelines/src .venv\Scripts\python.exe -m quantops_pipelines generate --output data/synthetic
# exit 0; 2,088 bars; files_written=0; files_unchanged=11
```

Aggregate dataset SHA-256: `2796bd52b205182f471903f42638c6f6751093c658d1017ecf4be03c3c1b1150`.

## Milestone 3 — risk engine

- [x] Returns, valuation, volatility, covariance, VaR, ES, drawdown, concentration, contributions, scenarios, and backtesting.
- [x] Known-example and property tests, methodology documentation, and benchmark evidence.
- [x] Confirm framework independence and no `NaN` leakage.

Verified risk-engine gates:

```text
.venv\Scripts\pytest.exe packages/risk_engine/tests --cov=quantops_risk --cov-branch -q
# exit 0; 99 passed, 14 subtests passed; 98% combined branch coverage

.venv\Scripts\ruff.exe check packages/risk_engine
.venv\Scripts\ruff.exe format --check packages/risk_engine
# both exit 0

.venv\Scripts\mypy.exe packages/risk_engine/src/quantops_risk packages/risk_engine/tests
# exit 0; 28 source files, no issues

.venv\Scripts\uv.exe build packages/risk_engine --offline
# exit 0; sdist and wheel built

.venv\Scripts\python.exe packages/risk_engine/benchmarks/benchmark_risk_engine.py
# Python 3.12.13, Windows 11; 756 observations x 25 instruments; 0.223069 seconds
```

The benchmark is a local observation, not a universal SLA.

## Milestones 4–14

- [ ] Milestone 4 — application API.
- [ ] Milestone 5 — frontend product.
- [ ] Milestone 6 — streaming and outbox.
- [ ] Milestone 7 — Airflow and adapters.
- [ ] Milestone 8 — ML lifecycle.
- [ ] Milestone 9 — grounded AI.
- [ ] Milestone 10 — read-only MCP.
- [ ] Milestone 11 — operations and infrastructure.
- [ ] Milestone 12 — CI, security, and full testing.
- [ ] Milestone 13 — portfolio polish.
- [ ] Milestone 14 — clean-room verification and publication.

## Current blockers

- Docker is unavailable, so PostgreSQL/Redpanda integration gates cannot yet be claimed.
- GitHub CLI is unavailable; publication is intentionally deferred until the Definition of Done.

## Next work

Complete and verify Milestone 0, then continue with domain/persistence, deterministic data, and the risk engine while keeping the core runnable without optional services.
