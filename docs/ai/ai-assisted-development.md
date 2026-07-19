# AI-assisted development record

## Purpose and scope

Codex assisted with repository design, implementation, tests, documentation, local verification,
Git history, and initial GitHub publication. This record distinguishes observed engineering evidence
from actions that still require owner review. It does not claim that a human independently reviewed
every generated line or that unavailable infrastructure was exercised.

## Areas assisted by Codex

- Monorepo, quality-tool, Docker Compose, documentation, and Git scaffolding.
- Framework-independent domain entities, value objects, ports, and pure risk calculations.
- SQLAlchemy mappings, repositories, unit of work, Alembic migration, and offline SQL validation.
- Deterministic synthetic fixture generation, manifests, data quality, quarantine, and lineage.
- Versioned API schemas/routes, concurrency/idempotency boundaries, OpenAPI, exports, and tests.
- Responsive React/TypeScript research UI and typed deterministic demo adapter.
- Versioned event contracts and broker-neutral replay/consumer/outbox worker behavior.
- Point-in-time ML features, baseline/candidate lifecycle, evaluation, promotion, artifacts, and drift.
- Bounded grounded-AI workflow, retrieval, tools, validators, evaluation cases, and API integration.
- Three-tool read-only MCP server and local stdio integration tests.
- Offline scheduler wrappers, guarded Airflow boundary, CI, Dependabot, security scanner, threat model,
  ADRs, architecture, runbooks, README, screenshots, and handoff evidence.

## Verification Codex actually performed

Observed commands and exact counts are maintained in `docs/progress.md`. The final pre-publication
local gate included:

```text
python -m pytest -m "not integration and not e2e" -q
# 468 passed, 1 integration test deselected, 20 subtests passed

ruff check .
ruff format --check .
# passed; 210 Python files formatted

python scripts/typecheck.py
# 11 isolated strict mypy groups passed

pnpm --filter @quantops/web lint
pnpm --filter @quantops/web typecheck
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
# passed; 14 Vitest tests and a Vite production build

python scripts/docs_check.py
python scripts/security_scan.py
# passed; no high-confidence secret or repository-hygiene findings
```

Package-specific coverage, the 44/44 deterministic AI evaluation, model lifecycle results, fixture
hashes, and risk benchmark are recorded with their commands in `docs/progress.md`. GitHub Actions was
subsequently observed passing on `main`; this does not substitute for still-pending live service and
clean-room gates.

## Concrete corrections made during the build

These are observed corrections, not hypothetical examples:

1. **API container dependency gap.** A static CI review found that the API image built the API wheel
   without first building/copying the grounded-AI package and its evaluation data. The Dockerfile and
   structural test were corrected to include all required workspace wheels and AI evaluation assets.
2. **Root mypy collision.** A broad recursive mypy command produced duplicate `__main__`/namespace
   module errors across independent packages. It was replaced with `scripts/typecheck.py`, which runs
   11 strict, isolated package groups and has focused orchestration tests.
3. **Stale developer commands.** Make/PowerShell targets referenced nonexistent seed, stream, ML, AI,
   and e2e commands. Targets were aligned to the actual public CLIs and unavailable capabilities were
   no longer presented as implemented workflows.
4. **Frontend mobile navigation.** Browser QA found horizontal navigation behavior that was awkward
   at the narrow viewport. The mobile navigation scrollbar/layout was corrected and rechecked.
5. **Scenario export rounding.** Browser review exposed inconsistent decimal presentation between the
   scenario result and export. Formatting was reconciled to the deterministic adapter values.
6. **Truthful integration labels.** UI and API documentation was revised to say `local adapter`,
   `process-local`, or `not configured` rather than implying live PostgreSQL, broker, model, or
   provider integration.
7. **Scheduler build environment.** An isolated build initially lacked the Hatchling backend. After
   adding the scheduler to the locked uv workspace, an offline workspace sync and package build
   succeeded without changing the package's declared build system.
8. **GitHub authentication diagnosis.** `gh auth status` appeared invalid inside the restricted
   network sandbox despite browser login. It was rechecked with approved network access, after which
   repository creation and push succeeded under the authenticated owner account.

## How generated changes were reviewed

- Scoped diffs and staged file lists were inspected before commits.
- Relevant narrow tests were run before each major integration commit.
- The service-free monorepo gate was repeated after integrating the scheduler and CI tooling.
- Public docs distinguish implemented deterministic boundaries from unavailable live integrations.
- Actual app pages were opened at desktop and mobile sizes before repository screenshots were saved.
- A deterministic scanner checked high-confidence credential patterns, sensitive filenames, and
  unexpected large files without printing matched values.
- Commit history was kept in focused conventional commits; unrelated owner work was not overwritten.

## Known limitations of the review

- No claim is made that the owner manually reviewed every generated source line.
- Docker was unavailable during the main local build, so clean PostgreSQL/pgvector, Redpanda, image,
  and Compose behavior still needs independent execution.
- The current UI and API deterministic adapters are not yet one live generated-client path.
- Airflow, MLflow, external LLM, pgvector retrieval, and observability are optional/incomplete live
  profiles even where ports, wrappers, or configuration exist.
- Automated Playwright accessibility and critical-path tests remain pending.
- Security scanning is a high-confidence repository gate, not a penetration test or formal audit.

## Owner-review actions

The owner should complete and date these truthfully before presenting the repository as personal
work:

- [ ] Run the documented quickstart from a clean checkout without Codex assistance.
- [ ] Review every public claim in README, progress, system/model cards, and engineering evidence.
- [ ] Recalculate and explain at least one VaR and contribution example.
- [ ] Trace one event, one quality case, and one evidence-backed AI factor end to end.
- [ ] Run Docker-backed PostgreSQL/Redpanda and container smoke gates on a capable host.
- [ ] Explain the baseline/candidate decision, leakage controls, AI validators, and MCP allowlist.
- [ ] Implement, test, and commit one meaningful change personally.
- [ ] Replace the README author placeholder with the owner's chosen professional identity.

Do not mark an item complete merely because Codex performed it. The checkbox records personal owner
verification only.
