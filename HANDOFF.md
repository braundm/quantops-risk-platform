# QuantOps handoff

Last updated: 2026-07-19

## Current state

The authoritative 2,442-line master specification was read in full. The repository now contains the
framework-free domain and risk cores, deterministic data/quality pipelines, PostgreSQL mappings and
migrations, a 31-route FastAPI surface, a responsive typed-demo UI, versioned events, broker-neutral
streaming, offline scheduling wrappers, a leakage-safe ML lifecycle, bounded grounded AI, and an
official-SDK read-only MCP server. The final local service-free gate passes 468 Python tests plus 20
subtests, strict typechecks across 11 isolated groups, all frontend gates, documentation checks, and
the repository security scan.

The public repository is https://github.com/braundm/quantops-risk-platform. Local `main` tracks
`origin/main`; the initial GitHub Actions CI run started against commit `fe73a64` after publication.

Focused commits through `fe73a64` preserve the implementation history. A final documentation-only
commit records publication state; use `git log -1` for its immutable SHA.

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
pnpm --filter @quantops/web build
# exit 0; 14 Vitest tests; Vite production build

.venv\Scripts\python.exe scripts/docs_check.py
.venv\Scripts\python.exe scripts/security_scan.py
# exit 0; 50 Markdown files; no high-confidence secret/hygiene findings

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
- Live Airflow/MLflow/provider/observability profiles, generated UI client integration, and browser
  e2e/accessibility remain unverified.
- The full master-spec Definition of Done remains open; do not create the `v0.1.0` release tag yet.

## Exact next action

Complete the remaining ADR topics for MLflow reproducibility and optional infrastructure profiles,
then add browser accessibility/critical-path automation if dependencies can be introduced safely.
On a Docker-capable clean host, run the remaining PostgreSQL/Redpanda/container gates before creating
a release tag or calling the project complete.

## Working tree expectation

The current work belongs to `agent/portfolio-polish`. Commit and push the interview/AI-development
documentation as one scope, preserve `origin`, and inspect `git status --short --branch` before
future edits.
