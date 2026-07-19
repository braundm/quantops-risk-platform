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

Focused commits through `9aaeb7f` preserve the implementation history. The final portfolio/CI/
scheduler commit is named `feat(platform): complete verified portfolio delivery`; use `git log -1`
for its immutable SHA.

## Architecture in force

Use a modular monolith for synchronous behavior, framework-free domain/risk packages, and separate
workers only for replay, scheduling, or isolation. PostgreSQL is the designed source of record;
Redpanda, Airflow, MLflow, external LLM providers, and observability remain optional boundaries. The
current UI and API run deterministic local adapters independently, so live integration must not be
claimed.

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
# exit 0; 48 Markdown files; no high-confidence secret/hygiene findings

.venv\Scripts\pytest.exe -c apps/scheduler/pyproject.toml apps/scheduler/tests -q
.venv\Scripts\uv.exe --cache-dir .uv-cache build --package quantops-scheduler --offline
# exit 0; 37 tests; sdist and wheel built
```

The current workstation uses bundled Git/Node/pnpm and workspace `uv`; Docker, `gh`, GNU Make, and
Terraform are absent from `PATH`.

## Honest blockers and limitations

- Docker-backed clean PostgreSQL, pgvector, Redpanda, image, and Compose gates were not runnable.
- GitHub Actions is defined and statically validated, but no hosted run exists before publication.
- Live Airflow/MLflow/provider/observability profiles, generated UI client integration, and browser
  e2e/accessibility remain unverified.
- GitHub CLI is absent, so repository creation/push cannot be authenticated or bypassed.
- The full master-spec Definition of Done remains open; do not create the `v0.1.0` release tag yet.

## Exact next action

Install GitHub CLI, authenticate, and publish the prepared `main` history:

```text
winget install --id GitHub.cli
gh auth login
gh repo create quantops-risk-platform --public --source . --remote origin --push --description "Production-style market risk, data lineage, and grounded AI research platform"
gh repo edit --add-topic python --add-topic fastapi --add-topic postgresql --add-topic fintech --add-topic data-engineering --add-topic machine-learning --add-topic llm --add-topic mcp --add-topic docker --add-topic react
```

After publication, observe/fix the initial CI run. On a Docker-capable clean host, run the remaining
PostgreSQL/Redpanda/container/browser gates before creating a release tag or calling the project
complete.

## Working tree expectation

The working tree should be clean after the final scoped commit. Preserve any existing remote and
inspect `git status --short --branch` before future edits.
