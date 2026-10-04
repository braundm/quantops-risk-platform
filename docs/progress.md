# QuantOps implementation progress

Last updated: 2026-10-04

This file records observed results only. An unchecked item is not implemented or has not yet met its exit evidence.

## Retail history and education follow-up — 2026-10-04

- [x] Add strict historical CSV preview/confirmation and dated-FX repricing of current units.
- [x] Reuse historical risk calculations, suppress insufficient samples, validate aligned dates,
  reject duplicate/ambiguous mappings and label synthetic/stale history.
- [x] Add interactive charts, separate fee budgets, optional goals/limits and a ten-step synthetic
  decision experiment with signed cursors, costs, benchmark and confidence calibration.
- [x] Refine the responsive visual design and clear all new session data on explicit deletion.
- [x] Restore the local Python 3.12 environment after a blocked recreation attempt; remove the
  temporary repair environment. No source or portfolio data was lost.
- [x] Fix the frontend CI API prerequisite and upgrade dependencies flagged by the previous audit.

Observed verification:

```text
.venv/Scripts/python.exe -m pytest -q -o cache_dir=artifacts/pytest-retail-cache
# 531 passed, 1 skipped (isolated PostgreSQL unavailable), 20 subtests passed
.venv/Scripts/python.exe scripts/typecheck.py
# all 11 strict groups passed
.venv/Scripts/python.exe -m ruff check apps/api
.venv/Scripts/python.exe -m ruff format --check apps/api
# passed; 40 files formatted
pnpm --filter @quantops/web lint
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
# passed; 14 Vitest tests; production bundle built
.venv/Scripts/python.exe -m pip_audit --progress-spinner off --format json --output artifacts/updated-python-audit.json
pnpm audit --prod
# both passed; no known vulnerabilities in the audited installed/production dependencies
pnpm --filter @quantops/web test:e2e --workers=2
# 28 passed (desktop/mobile), including axe accessibility checks
.venv/Scripts/python.exe scripts/docs_check.py
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
# passed; 49 Markdown files; 218 Python files already formatted
.venv/Scripts/python.exe scripts/security_scan.py
git diff --cached --check
# passed after staging all new source files; no secret/hygiene or whitespace findings
# Running Vite proxy: /api/v1/health returned ok; /api/v1/retail/history-demo returned 1020 rows
```

Browser testing first found one desktop contrast issue: the expanded menu overflowed its dark
sidebar. Adding scroll containment corrected the actual layout; no accessibility rule was disabled.
Desktop and mobile history screenshots were visually reviewed. Optional service/production gates
remain separate from these local checks.

Hosted run `37211696446` passed all nine application, PostgreSQL, browser and security jobs.
Its final container job exposed an existing packaging defect: separately resolved wheel builds
collected both Pydantic 2.13.4 and 2.13.5, and wildcard installation demanded both. The API image
now installs its production dependency closure once from `uv.lock` with non-editable workspace
packages, then copies only the environment into the unprivileged runtime. Local Docker is
unavailable; hosted container verification is required for this correction.

The same `uv sync --locked --package quantops-api --no-dev --no-editable` command succeeded in a
temporary Windows environment with 35 packages. Its installed API imported successfully and
produced all 1020 synthetic history rows. The temporary environment was removed afterwards.
This verifies dependency selection and packaging, not the Linux container runtime.

## Retail first vertical flow — 2026-10-04

- [x] Preserve React/FastAPI, pure valuation/scenario calculations and existing research routes.
- [x] Connect the Polish personal workspace to stateless FastAPI calculations.
- [x] Verify manual/current-position CSV inputs, signed values, cash, quotation-currency exposures
  and concentration; reject unsupported derivatives and contract multipliers.
- [x] Verify combined price/FX sensitivity, short/long hedge direction, no/partial/full forward
  payoffs, separate costs, theoretical carry and oversized initial hedges after asset losses.
- [x] Verify readable report contents, stale-result invalidation, local restore/delete, base-currency
  rate reset, synthetic provenance and responsive keyboard/axe accessibility.
- [x] Document synthetic inputs, missing history, stale prices, no ETF look-through, model exclusions
  and actual/deferred scope in `docs/retail-first-flow.md`.
- [x] Add optional onboarding, user historical-risk data and a synthetic educational experiment
  in the follow-up recorded above.
- [ ] Complete a transaction-linked cost ledger, persistence/tenant authentication and separately
  scoped broker-specific read-only adapters.

Observed scoped gates:

```text
.venv\Scripts\python.exe -m pytest apps/api/tests packages/risk_engine/tests -q -o cache_dir=artifacts/pytest-retail-cache
# exit 0; 190 passed, 1 PostgreSQL integration test skipped, 14 subtests passed

.venv\Scripts\python.exe scripts/typecheck.py --group api --group risk
# exit 0; 35 API files and 30 risk files checked under strict mypy

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web typecheck
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
pnpm --filter @quantops/web test:e2e
# exit 0; 14 Vitest tests, production build, 22 desktop/mobile Playwright tests

.venv\Scripts\ruff.exe check <changed Python files>
.venv\Scripts\ruff.exe format --check <changed Python files>
# exit 0; lint passed and all 6 changed Python files already formatted

.venv\Scripts\python.exe scripts/security_scan.py
.venv\Scripts\python.exe scripts/docs_check.py
git diff --check
# exit 0; no high-confidence secret/hygiene findings, 48 Markdown files checked, clean diff
```

Initial verification caught an outdated exact route-set assertion (updated with the three new
retail endpoints), global research-table colors leaking into the light personal workspace (fixed
with scoped colors), and parallel browser tests exhausting the production-default 20/minute limit.
The test server alone uses a 1000/minute budget; a dedicated API test verifies the normal configurable
429 response and Retry-After header. Existing pytest cache permissions required a fresh ignored
`artifacts/pytest-retail-cache`; no test or warning check was disabled. The public OpenAPI snapshot
was regenerated and its existing equality gate passes. The owner subsequently explicitly
authorized recording these changes in Git and publishing them to GitHub on 2026-10-04. This
authorization overrides the prior publication restriction for this change; it does not mark the
retail MVP or master-spec Definition of Done complete. Use the existing branch and draft PR #11.

The entire retail MVP remains open. The completed scope is the specifically requested first flow:
portfolio → exposures → currency scenario → hedge comparison, plus CSV, local data controls,
before/after valuation and report export.

Local preview started with the documented commands on loopback ports 8000 and 5173. A direct
health request and a Vite-proxied demo request returned the healthy API and four synthetic positions.
The Codex browser-panel opening request was queued by the app; use `http://127.0.0.1:5173/` directly
if the preview panel is not visible. Development processes remain running for the owner to inspect.

Pre-publication repository security, documentation and whitespace checks passed again. The commit
contains only the 22 source, test, contract, example and documentation files belonging to this flow;
preview artifacts, build output and test caches are excluded. No merge or release is requested.

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
- [x] SQLAlchemy mappings and asynchronous repositories.
- [ ] Clean-database Alembic migration and PostgreSQL constraints/indexes.
- [ ] Optimistic concurrency, audit, and transactional outbox integration tests.
- [x] ER model documentation.

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

Verified persistence gates:

```text
.venv\Scripts\pytest.exe apps/api/tests -m "not integration" -q
# exit 0; 22 passed, 1 deselected

.venv\Scripts\ruff.exe check apps/api
.venv\Scripts\ruff.exe format --check apps/api
# both exit 0; 22 files formatted

.venv\Scripts\mypy.exe apps/api
# exit 0; 21 source files, no issues

PYTHONPATH=apps/api;packages/domain .venv\Scripts\alembic.exe -c apps/api/alembic.ini upgrade head --sql
# exit 0; PostgreSQL DDL compiled through revision 0001, including vector extension,
# semantic scenario versions, named constraints/indexes, and transactional outbox

.venv\Scripts\uv.exe build apps/api --offline
# exit 0; sdist and wheel built
```

The adapters include latest-per-instrument position reads, guarded portfolio updates, exact
`NUMERIC(38,12)` prevalidation, safe UTC handling, and same-transaction audit/outbox staging.
Their offline behavior and SQL shape are tested. A live clean-database upgrade, constraint
execution, pgvector/HNSW creation, and transaction/concurrency integration tests still require an
isolated PostgreSQL database. Therefore Milestone 1 is not complete.

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

## Milestone 4 — application API

- [x] Expose all 31 required versioned `/api/v1` paths with validated request/response schemas.
- [x] Compute deterministic portfolio risk, evidence, and scenario responses through the domain,
  contract, and risk-engine packages.
- [x] Add RFC 9457 problem details, request/correlation IDs, CORS allowlisting, bounded pagination,
  date validation, and rate limiting.
- [x] Protect demo writes, enforce ETag/`If-Match` concurrency, and detect idempotency-key conflicts.
- [x] Export JSON/CSV reports and check a deterministic OpenAPI snapshot for contract drift.
- [ ] Move the critical application path from the process-local adapter to PostgreSQL repositories.
- [ ] Generate the TypeScript client and complete live frontend integration.

Verified application-API gates:

```text
.venv\Scripts\pytest.exe apps/api/tests -q
# exit 0; 39 passed, 1 skipped (PostgreSQL integration unavailable)

.venv\Scripts\ruff.exe check apps/api
.venv\Scripts\ruff.exe format --check apps/api
# both exit 0

.venv\Scripts\mypy.exe apps/api
# exit 0; no issues

.venv\Scripts\uv.exe build apps/api --offline
# exit 0; sdist and wheel built
```

The process-local fallback contains 41 dates for each of four instruments (164 accepted bars),
distinct from the canonical 2,088-bar database fixture. It now exposes deterministic grounded risk
briefs and the 44-case synchronous AI evaluation while returning truthful unavailable responses for
other unconnected capabilities. Dockerfile structure is tested, but a container build and live
PostgreSQL execution remain unverified because Docker is unavailable. Milestone 4 is not complete
until the persistence critical path and generated live client are connected.

## Milestone 5 — frontend product

- [x] Responsive product routes, navigation, design system, and deterministic demo adapter.
- [x] Dashboard, portfolio, scenario, evidence/brief, market, model, pipeline, audit,
  methodology, and architecture views.
- [x] Loading, empty, error, stale, partial, insufficient-history, and offline states.
- [x] Frontend fixture risk/scenario values reconciled to the current API demo service.
- [ ] Generated OpenAPI client and live API integration.
- [x] Automated accessibility scan and keyboard/browser critical-path end-to-end suite.

Verified frontend gates:

```text
pnpm --filter @quantops/web lint
pnpm --filter @quantops/web typecheck
# both exit 0

pnpm --filter @quantops/web test
# exit 0; 2 files, 14 tests passed

pnpm --filter @quantops/web test:e2e
# exit 0; 14 Playwright tests passed across desktop Chromium and a Pixel 7 viewport
# six representative product routes passed automated WCAG A/AA axe scans in each project

pnpm --filter @quantops/web build
# exit 0; 29 modules; JS 280.54 kB (80.79 kB gzip), CSS 49.11 kB (10.60 kB gzip)
```

Browser QA exercised the landing page, dashboard, scenario selection/custom validation, evidence
briefs, desktop layout, and a 390 x 844 responsive viewport. The automated suite now covers the
landing page plus dashboard, scenario, grounded brief/evidence, model/drift, and pipeline-quality
routes at desktop and mobile sizes. It also verifies skip-link focus, keyboard navigation, scenario
execution, and evidence citation navigation. The mobile navigation scrollbar, scenario-export
decimal rounding, metadata contrast, decorative ARIA, and scrollable-table keyboard access were
corrected from these reviews. Milestone 5 remains incomplete only because the generated OpenAPI
client and live API integration are not connected.

## Milestone 6 — streaming and outbox

- [x] Versioned event-envelope and payload contracts.
- [x] Broker-neutral deterministic replay, idempotent consumer, and outbox-publisher services.
- [x] Duplicate/conflicting-content, late/out-of-order, bounded retry, safe DLQ, and metrics behavior.
- [x] Commit-after-durability ordering, partition replay barriers, and broker-outage simulation.
- [x] Controlled `portfolio.changed.v1` to `risk.recompute.requested.v1` outbox derivation.
- [ ] Live Redpanda producer/consumer adapter and isolated broker integration tests.
- [ ] Replay-driven persisted risk snapshot update and optional live UI updates.

Verified event-contract gates:

```text
.venv\Scripts\pytest.exe -c packages/data_contracts/pyproject.toml \
  packages/data_contracts/tests --cov=quantops_contracts --cov-branch -q
# exit 0; 43 passed; 94% combined branch coverage

.venv\Scripts\ruff.exe check packages/data_contracts
.venv\Scripts\ruff.exe format --check packages/data_contracts
# both exit 0; 12 files formatted

.venv\Scripts\mypy.exe --config-file packages/data_contracts/pyproject.toml \
  packages/data_contracts/src/quantops_contracts packages/data_contracts/tests
# exit 0; 12 source files, no issues

.venv\Scripts\uv.exe build packages/data_contracts --offline
# exit 0; sdist and wheel built
```

The six v1 contracts enforce type/version pairing, UTC/non-nil identifiers, bounded payloads,
finite Decimal values, canonical JSON, stable idempotency keys, and explicit synthetic labels.
They intentionally have no broker dependency.

Verified broker-neutral worker gates:

```text
.venv\Scripts\pytest.exe -c apps/stream_worker/pyproject.toml apps/stream_worker/tests \
  --cov=quantops_stream_worker --cov-branch -q
# exit 0; 29 passed; 89% combined branch-aware coverage

.venv\Scripts\ruff.exe check apps/stream_worker
.venv\Scripts\ruff.exe format --check apps/stream_worker
# both exit 0; 18 files formatted

.venv\Scripts\mypy.exe --config-file apps/stream_worker/pyproject.toml \
  apps/stream_worker/src apps/stream_worker/tests
# exit 0; 17 source files, no issues

.venv\Scripts\uv.exe build apps/stream_worker --offline
# exit 0; sdist and wheel built
```

The process-local adapters demonstrate exact redelivery, idempotency conflicts, bounded lateness,
metadata-only DLQ records, planned retry delays without sleeping, broker outage behavior, and
acknowledged publication ordering. They do not prove consumer-group rebalancing, topic/ACL setup,
or durable Redpanda behavior. Milestone 6 remains incomplete until the live adapter, isolated broker
tests, and replay-driven persisted risk update pass.

## Milestone 7 — Airflow and adapters

- [x] Add four typed, offline-first job wrappers over the existing data, ML, and AI CLIs.
- [x] Derive deterministic configuration hashes and UUIDv5 run identities.
- [x] Enforce process-local duplicate suppression, bounded execution, dry-run, timeout,
  cancellation, sanitized failures, and observable run counts/statuses.
- [x] Add guarded optional Airflow DAG discovery that degrades to `scheduler_unavailable`.
- [ ] Exercise the DAGs against a real Airflow scheduler and durable metadata/run store.
- [ ] Add database ingestion/upsert scheduling after the PostgreSQL critical path exists.

Verified scheduler gates:

```text
.venv\Scripts\pytest.exe -c apps/scheduler/pyproject.toml apps/scheduler/tests -q
# exit 0; 37 passed

.venv\Scripts\ruff.exe check apps/scheduler
.venv\Scripts\mypy.exe --config-file apps/scheduler/pyproject.toml apps/scheduler/src apps/scheduler/tests
# both exit 0; mypy checked 18 source files

.venv\Scripts\uv.exe --cache-dir .uv-cache build --package quantops-scheduler --offline
# exit 0; sdist and wheel built
```

The tests execute the real existing pipeline, ML, and AI CLI boundaries without network access.
No active Airflow service, cross-host idempotency, or database ingestion is claimed.

## Milestone 8 — ML lifecycle

- [x] Build ten point-in-time risk-regime features with explicit provenance and leakage tests.
- [x] Implement a documented deterministic rule baseline and pure-Python K-Means candidate.
- [x] Use chronological partitions and report every fixed seed under a median-validation policy.
- [x] Evaluate macro F1, adjusted Rand index, stress false-negative rate, and calibration error.
- [x] Enforce automated promotion gates, retain the baseline on rejection, and generate a model card.
- [x] Produce deterministic, content-addressed lifecycle artifacts with dataset and code revisions.
- [x] Monitor PSI, missingness change, and Jensen-Shannon regime drift.
- [ ] Exercise the optional MLflow adapter against a real tracking service.
- [ ] Expose the lifecycle catalog and active model through the application API.

Verified ML gates:

```text
.venv\Scripts\pytest.exe -c ml/pyproject.toml ml/tests --cov=quantops_ml --cov-branch -q
# exit 0; 42 passed; 93% combined branch coverage

.venv\Scripts\ruff.exe check ml
.venv\Scripts\ruff.exe format --check ml
# both exit 0; 25 files formatted

.venv\Scripts\mypy.exe --config-file ml/pyproject.toml -p quantops_ml -p ml.tests
# exit 0; 24 source files, no issues

.venv\Scripts\uv.exe build ml --offline
# exit 0; sdist and wheel built
```

The lifecycle produced 462 feature rows from the canonical synthetic dataset. Seed `7` was selected
by the declared median-validation policy, not by test performance. The candidate failed relative
macro-F1 and calibration gates, so `rule-baseline-v1` remains active. Operational drift was
detected and MLflow was truthfully reported as disabled. Two consecutive runs at code revision
`72cfa241760ffb02e682ef58caab176bedab41d1` produced artifact hash
`0b0738757fbade763be9688c60592c33c9b2978114c2f79daf7e7a3f8081cb52`; the second changed zero of
ten files. Milestone 8 remains incomplete until the real MLflow profile and API catalog are proven.

## Milestone 9 — grounded AI

- [x] Define frozen, portfolio-scoped evidence, request, brief, refusal, and trace schemas.
- [x] Implement a fixed ten-tool read-only protocol with call, time, and response-size budgets.
- [x] Provide a useful no-key deterministic provider and an isolated optional OpenAI-compatible port.
- [x] Add bounded workflow, one repair, deterministic fallback, and safe refusal behavior.
- [x] Add approved-scope keyword retrieval with prompt-injection isolation and relevance thresholds.
- [x] Validate schemas, citations, evidence scope, canonical numbers/rounding, and prohibited content.
- [x] Version 44 labeled evaluation cases covering every one of the 20 required categories.
- [x] Store a machine-readable evaluation report and document the system boundary.
- [ ] Exercise pgvector retrieval and the optional provider against configured external services.
- [x] Expose deterministic briefs, structured refusal, and evaluations through the application API.
- [ ] Connect the generated/live UI client to the API brief endpoints.

Verified grounded-AI gates:

```text
.venv\Scripts\pytest.exe -c packages/ai_engine/pyproject.toml packages/ai_engine/tests \
  --cov=quantops_ai --cov-branch -q
# exit 0; 110 passed; 97% combined branch-aware coverage
# citation and numerical validator modules: 100% statements and branches

.venv\Scripts\ruff.exe check packages/ai_engine
.venv\Scripts\ruff.exe format --check packages/ai_engine
# both exit 0; 25 files formatted

.venv\Scripts\mypy.exe --config-file packages/ai_engine/pyproject.toml \
  -p quantops_ai -p packages.ai_engine.tests
# exit 0; 24 source files, no issues

.venv\Scripts\uv.exe build packages/ai_engine --offline
# exit 0; sdist and wheel built; wheel contains evals/v1/cases.jsonl

.venv\Scripts\python.exe -m quantops_ai evaluate \
  --cases packages/ai_engine/evals/v1/cases.jsonl \
  --output $env:TEMP\quantops-ai-evaluation-root.json
# exit 0; 44 passed, 0 failed across 20 categories
```

All deterministic schema, citation, numerical, refusal, tool-selection, and groundedness rates were
`1.0`; 23 tool calls were made. Seven deliberately invalid-provider cases used the safe fallback.
External cost/token fields are null because no provider call occurred. Evaluation latency is a
local observation and is not a portable benchmark. API integration additionally verifies auth,
idempotency/conflict, rate limiting, unknown scope, deterministic refusals with zero tool/provider
calls, and synchronous evaluation. Milestone 9 remains incomplete until live UI client integration
and configured pgvector/external-provider profiles are separately proven.

## Milestone 10 — read-only MCP

- [x] Use the official Python MCP SDK `1.28.1`, capped below its future v2 boundary.
- [x] Expose exactly three read-only tools over the existing application-service read methods.
- [x] Expose one fixed, bounded risk-methodology resource through local stdio transport.
- [x] Validate UUID and literal demo scope and cap reads at one second and responses at 32 KiB.
- [x] Return structured synthetic/no-advice outputs with evidence identity where applicable.
- [x] Prove the exact tool/resource surface, read-only annotations, no audit mutation, invalid-scope
  rejection, injection-as-data behavior, timeout/size failure, and stdio client/server operation.
- [x] Document package-level threats, explicitly absent capabilities, and remote-transport gaps.

Verified MCP gates:

```text
.venv\Scripts\pytest.exe -c apps/mcp_server/pyproject.toml apps/mcp_server/tests -q
# exit 0; 10 passed, including an actual stdio client/server exchange on protocol 2025-11-25

.venv\Scripts\ruff.exe check apps/mcp_server
.venv\Scripts\ruff.exe format --check apps/mcp_server
# both exit 0; 10 files formatted

.venv\Scripts\mypy.exe --config-file apps/mcp_server/pyproject.toml \
  -p quantops_mcp -p apps.mcp_server.tests
# exit 0; 9 source files, no issues

.venv\Scripts\uv.exe build apps/mcp_server --offline
# exit 0; sdist and wheel built
```

The allowlist contains `get_latest_portfolio_risk`, `get_snapshot_evidence`, and
`list_system_scenarios`; no write, recompute, scenario-run, shell, filesystem, arbitrary URL,
environment, raw database, prompt, sampling, or arbitrary-resource capability exists. Milestone 10
is complete for the required local stdio boundary. Authenticated multi-tenant remote transport is a
future design and is not claimed.

## Milestone 11 — operations and infrastructure

- [x] Document system, batch, streaming, risk/evidence, AI, and ML architecture flows.
- [x] Add eight incident runbooks with detection, impact, diagnosis, safe mitigation, recovery, and
  verification.
- [x] Add explicit backup/restore guidance, migration policy, a blameless sanitized postmortem
  template, and an observability contract for the deferred telemetry profile.
- [x] Keep API image multi-stage/non-root and build the grounded-AI wheel before the dependent API.
- [ ] Add structured telemetry, bounded metrics, traces, and a verified optional observability profile.
- [ ] Run core/optional Docker profiles and verify health, readiness, and graceful shutdown.

Static Dockerfile tests cover the builder/runtime split, all five required workspace wheels,
grounded-AI evaluation-data inclusion, and non-root runtime identity. Docker remains unavailable in
this environment, so image build/start evidence is intentionally unchecked. Kubernetes/Terraform
remain P2 and no resource or paid service has been created.

## Milestone 12 — CI, security, and full testing

- [x] Add a deterministic high-confidence secret, sensitive-filename, and oversized-file scanner.
- [x] Test scanner behavior without rendering matched secret values.
- [x] Add a STRIDE-style threat model covering the required data, event, AI/MCP, supply-chain,
  container, denial-of-service, and financial-misinterpretation threats.
- [x] Record the minimum ADR set plus the local demo-auth boundary.
- [x] Map major engineering claims to inspectable files/tests/commands.
- [x] Add a statically validated, least-privilege ten-job CI workflow, dependency updates,
  evidence artifacts, isolated PostgreSQL migration job, dependency/SBOM gates, and container smoke
  definitions.
- [x] Observe the first GitHub-hosted CI run, network vulnerability audits, PostgreSQL service job,
  and Docker image smoke jobs after publication.
- [x] Complete automated browser accessibility and critical-path e2e tests on desktop/mobile Chromium.
- [ ] Complete live PostgreSQL/Redpanda and clean-room service tests.

Verified no-service repository gates after AI/stream/MCP integration:

```text
.venv\Scripts\pytest.exe -m "not integration and not e2e" -q
# exit 0; 428 passed, 1 integration test deselected, 20 subtests passed

.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
# both exit 0; 187 files formatted

.venv\Scripts\python.exe scripts/docs_check.py
# exit 0; 45 Markdown files checked at the time of the gate

.venv\Scripts\python.exe scripts/security_scan.py
# exit 0; no high-confidence secret or hygiene findings
```

The scanner explicitly permits the committed 1.16 MiB canonical synthetic JSON fixture while its
manifest/hash checks remain authoritative; other repository files over 1 MiB fail the gate.

Final local service-free integration gate after scheduler, CI tooling, and portfolio images:

```text
.venv\Scripts\python.exe -m pytest -m "not integration and not e2e" -q
# exit 0; 468 passed, 1 integration test deselected, 20 subtests passed

.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
# both exit 0; 210 Python files formatted

.venv\Scripts\python.exe scripts/typecheck.py
# exit 0; 11 isolated strict mypy groups passed

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web typecheck
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
# all exit 0; 14 Vitest tests; production build completed

.venv\Scripts\python.exe scripts/docs_check.py
.venv\Scripts\python.exe scripts/security_scan.py
# both exit 0; 48 Markdown files; no high-confidence secret or hygiene findings
```

## Milestone 13 — portfolio polish

- [x] Replace the scaffold README with a product-oriented quickstart, demo story, architecture,
  feature evidence, methods/safety summary, observed status, and visible limitations.
- [x] Capture seven actual running-product images for the landing page, dashboard, scenario/stress,
  grounded brief, model/drift, and data-quality views.
- [x] Keep architecture diagrams, methodology, model/AI cards, engineering evidence, runbooks,
  threat model, and all ten required decision topics linked and factual, including MLflow
  reproducibility and safely optional infrastructure profiles.
- [x] Add the interview guide with pitch, walkthrough, demo, domain explanations, 30 technical
  questions, ten trade-off questions, concepts, and personal owner exercises.
- [x] Add a truthful AI-assisted-development record with observed verification, concrete corrected
  errors, review limits, and separate owner-review actions.
- [x] Complete automated browser accessibility and Playwright critical-path coverage.

## Milestone 14 — clean-room verification and publication

- [x] Run the strongest clean local service-free gate available in this environment.
- [x] Inspect repository images, lockfile, documentation, status, and high-confidence secret/hygiene
  results.
- [ ] Run the Docker/PostgreSQL/Redpanda/clean-checkout gates on a Docker-capable host.
- [x] Publish public `braundm/quantops-risk-platform`, configure `origin`, description, and ten concise
  repository topics, and push `main`; hosted CI passed at verified commit `4f7627b`.
- [x] Observe the initial hosted CI run to completion; do not create a release tag while the full
  Definition of Done remains open.

## Current blockers

- Docker is unavailable, so PostgreSQL/Redpanda integration gates cannot yet be claimed.
- GitHub Actions run `29694259171` passed on `main`, including the PostgreSQL migration and
  unprivileged API/frontend container smoke jobs.
- Local Docker remains unavailable, so the same service and container behavior cannot yet be
  reproduced on this workstation.

Scoped verification for the frontend container permission fix:

```text
pnpm --filter @quantops/web build
# exit 0; Vite 8.1.5 production build completed

.venv\Scripts\python.exe scripts/docs_check.py
.venv\Scripts\python.exe scripts/security_scan.py
# both exit 0; 48 Markdown files; no high-confidence secret or hygiene findings
```

## Next work

Connect the generated TypeScript client to the live API boundary, then implement and verify the
PostgreSQL-backed critical application path and Redpanda adapter. On a Docker-capable clean host,
repeat migrations, persistence/Redpanda integration, image, and Compose smoke tests. Keep the
release tag and remaining service-dependent evidence unchecked until those gates pass.
