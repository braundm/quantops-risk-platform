# QuantOps handoff

Last updated: 2026-10-04

## Retail history, education and visual refinement

The personal workspace now includes aligned historical price/FX CSV preview, VaR/ES, volatility,
drawdown, correlation and a keyboard-accessible chart. It reprices current fixed quantities, not
investor transaction performance. Insufficient/inconsistent history suppresses precise metrics.
An optional survey checks loss willingness/capacity and applies a personal concentration threshold.
A separate cost budget excludes fees already embedded in prices. The ten-step synthetic education
exercise reveals future observations only after a decision and reports costs and Brier calibration.
The UI has a refined green/cream palette, clearer cards, responsive chart panels and a scrollable
sidebar. Delete clears the portfolio and all added session panels. Method details and exclusions
are maintained in `docs/retail-first-flow.md`.

Python verification: 531 tests plus 20 subtests passed, one PostgreSQL integration test skipped;
strict typechecks passed across 11 groups. Frontend lint, 14 Vitest tests and build passed.
Desktop/mobile Playwright coverage passed all 28 tests, including automated accessibility checks.
Documentation checks passed for 49 Markdown files; repository-wide Ruff checks passed.
Updated Python and production Node audits found no known vulnerabilities. The browser CI job now installs
the locked Python API required by its tests. The local Python environment was restored to 3.12
after a locked-process interruption; the temporary repair environment was removed.

Hosted application, PostgreSQL, frontend and security gates passed at `6fd665f`. The container job
found duplicate independently resolved Pydantic wheels. The follow-up Dockerfile uses one locked,
non-editable API dependency environment and retains the unprivileged runtime. Confirm the follow-up
hosted container job before claiming container verification; Docker is unavailable locally.

Remaining work includes transaction/flow history, persisted named scenarios, authenticated durable
storage and any separately scoped read-only data adapters. The education cursor is intentionally
single-process and replayable; synthetic trials are not evidence of strategy performance. No full
retail MVP completion, external-service verification or production readiness is claimed.

## Retail flow added on 2026-10-04

The default `/` route now serves a Polish personal portfolio workspace connected to FastAPI.
The former landing page is preserved at `/research`; existing research routes and risk calculations
remain available. See `docs/retail-first-flow.md` for launch commands, the full CSV mapping, model
assumptions, local data handling and the actual/synthetic/deferred capability split.

Implemented and verified: manual current positions, atomic CSV preview/confirm, signed spot
valuation and exposures, concentration, combined asset/FX shocks, no/partial/full signed forward
comparisons with entry/holding estimates, before/after valuation, explicit local save/restore/delete,
readable report export and stale-result invalidation. Synthetic origin is retained in the example
CSV and modified fictional holdings. New portfolios require user FX; changing base currency clears
foreign rates instead of silently reusing rates with different units. The API is stateless and
rate-limited; it adds no hosted user accounts or PostgreSQL persistence.

Scoped gates: 190 API/risk Python tests and 14 subtests passed; one PostgreSQL test skipped because
no isolated database was configured. API/risk strict typechecks passed. Frontend lint, typecheck,
14 Vitest tests, production build and 22 desktop/mobile Playwright tests passed, including report
contents, CSV rejection, local data deletion and axe checks. Exact commands are in `docs/progress.md`.

The follow-up above adds historical risk, the optional survey and synthetic education. Transaction/
flow contracts and broker-specific read-only adapters remain separate deferred work.
This is a working retail application slice, not completion of the entire
retail MVP or the original master-spec Definition of Done. The owner explicitly authorized a Git
commit and GitHub publication on 2026-10-04, overriding the earlier publication restriction for
this change. Publish on the existing `agent/portfolio-polish` branch and update draft PR #11;
do not merge or create a release tag as part of this request.

## Previous research baseline (2026-07-19)

## Current state

The authoritative 2,442-line master specification was read in full. The repository now contains the
framework-free domain and risk cores, deterministic data/quality pipelines, PostgreSQL mappings and
migrations, a 31-route FastAPI surface, a responsive typed-demo UI, versioned events, broker-neutral
streaming, offline scheduling wrappers, a leakage-safe ML lifecycle, bounded grounded AI, and an
official-SDK read-only MCP server. The final local service-free gate passes 468 Python tests plus 20
subtests, strict typechecks across 11 isolated groups, 14 Vitest tests, 14 desktop/mobile Playwright
tests with axe scans, the frontend production build, documentation checks, and the repository
security scan.

The public repository is https://github.com/braundm/quantops-risk-platform. Local work is on
`agent/portfolio-polish`, tracking the same branch on `origin`; draft PR #11 contains the current
portfolio/documentation improvements.

Focused commits through `4f7627b` on `main` preserve the published implementation history. Use
`git log -1` on the active branch for its latest immutable SHA.

## Architecture in force

Use a modular monolith for synchronous behavior, framework-free domain/risk packages, and separate
workers only for replay, scheduling, or isolation. PostgreSQL is the designed source of record;
Redpanda, Airflow, MLflow, external LLM providers, and observability remain optional boundaries. The
current UI and API run deterministic local adapters independently, so live integration must not be
claimed.

Milestone 13 now includes `docs/interview-guide.md` and
`docs/ai/ai-assisted-development.md`; both separate observed Codex verification from personal owner
review and keep unavailable integrations explicitly qualified.

## Last successful local gates

```text
.venv\Scripts\uv.exe --cache-dir .uv-cache sync --locked --all-packages --offline
# exit 0; quantops-scheduler installed from the workspace

.venv\Scripts\python.exe -m pytest -m "not integration and not e2e" -q
# exit 0; 468 passed, 1 deselected, 20 subtests passed

.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
# exit 0; 210 Python files formatted

.venv\Scripts\python.exe scripts/typecheck.py
# exit 0; 11 strict isolated mypy groups

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web typecheck
pnpm --filter @quantops/web test
pnpm --filter @quantops/web test:e2e
pnpm --filter @quantops/web build
# exit 0; 14 Vitest tests; 14 desktop/mobile Playwright tests; Vite production build

.venv\Scripts\python.exe scripts/docs_check.py
.venv\Scripts\python.exe scripts/security_scan.py
# exit 0; 56 Markdown files; no high-confidence secret/hygiene findings

.venv\Scripts\pytest.exe -c apps/scheduler/pyproject.toml apps/scheduler/tests -q
.venv\Scripts\uv.exe --cache-dir .uv-cache build --package quantops-scheduler --offline
# exit 0; 37 tests; sdist and wheel built
```

The current workstation uses bundled Git/Node/pnpm and workspace `uv`. GitHub CLI 2.96.0 is installed
at `C:\Program Files\GitHub CLI\gh.exe` and authenticated as `braundm`, although the current shell
does not include it in `PATH`. Docker, GNU Make, and Terraform remain absent from `PATH`.

## Honest blockers and limitations

- Docker-backed clean PostgreSQL, pgvector, Redpanda, image, and Compose gates were not runnable.
- GitHub Actions run `29694259171` passed on `main` after the unprivileged nginx cache/PID permission
  correction in commit `4f7627b`.
- Live Airflow/MLflow/provider/observability profiles and generated UI client integration remain
  unverified.
- The full master-spec Definition of Done remains open; do not create the `v0.1.0` release tag yet.

## Exact next action

Connect the generated TypeScript client and PostgreSQL-backed critical application path. On a
Docker-capable clean host, run the remaining Redpanda/clean-room gates and exercise the documented
backup/migration/observability procedures before creating a release tag or calling the project
complete.

## Working tree expectation

The current work belongs to `agent/portfolio-polish` and draft PR #11. Preserve `origin`, keep
commits narrowly scoped, and inspect `git status --short --branch` before future edits.
