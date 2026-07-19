# QuantOps engineering evidence map

Last updated: 2026-07-19

This map links major portfolio claims to inspectable code, tests, and commands. It deliberately
records gaps next to evidence. Exact observed outcomes and commit history remain in
[`progress.md`](progress.md) and [`HANDOFF.md`](../HANDOFF.md).

| Claim | Implementation evidence | Test or command evidence | Current limit |
| --- | --- | --- | --- |
| Deterministic synthetic market data | `pipelines/src/quantops_pipelines/generator.py`; `data/synthetic/manifest.json` | `pipelines/tests/test_generator.py`; `python -m quantops_pipelines generate` repeats with zero changed files | Fixture behavior is not evidence about a live market source. |
| Explicit quality and quarantine rules | `pipelines/src/quantops_pipelines/quality.py`; typed quality cases under `data/synthetic` | `pipelines/tests/test_quality.py` | PostgreSQL seed/upsert and durable quarantine remain unverified. |
| Framework-independent domain | `packages/domain/quantops_domain` | `packages/domain/tests`; dependency-boundary test | Live transaction/concurrency evidence still needs PostgreSQL. |
| Exact PostgreSQL schema and repository adapters | `apps/api/alembic`; `apps/api/quantops_api/infrastructure/persistence` | persistence metadata/repository tests; offline Alembic SQL compilation | Docker/PostgreSQL was unavailable locally; a clean live migration is unchecked. |
| Reproducible risk analytics | `packages/risk_engine/src/quantops_risk` | 99 unit/property tests, 14 subtests, 98% branch-aware coverage; local benchmark script | Benchmark is one local observation, not a universal SLA. |
| Versioned REST product contract | `apps/api/quantops_api/api`; `apps/api/openapi.generated.json` | `apps/api/tests`; OpenAPI freshness test; 39 pass and one PostgreSQL skip | Process-local service is the active demo path; live persistence/client integration is pending. |
| Responsive research UI with explicit states | `apps/web/src`; typed local adapter | ESLint, TypeScript, 14 Vitest tests, production build, manual desktop/mobile browser QA | UI is not yet driven by a generated live API client; automated a11y/e2e is pending. |
| Versioned event compatibility | `packages/data_contracts/src/quantops_contracts` | 43 contract tests, canonical serialization/idempotency tests, 94% coverage | Contracts alone do not prove broker delivery. |
| Idempotent streaming behavior | `apps/stream_worker/src/quantops_stream_worker/consumer.py`; `outbox_publisher.py`; domain outbox | 29 tests cover duplicate/conflict, late/DLQ, retry, offset ordering, replay barriers, and broker outage | Adapters are process-local. Redpanda topics, consumer groups, and persisted replay risk updates are pending. |
| Leakage-safe risk-regime lifecycle | `ml/src/quantops_ml`; model card/artifact writers | 42 tests, 93% coverage; repeat run changes zero artifacts | Candidate is rejected; `rule-baseline-v1` remains active. MLflow service is not connected. |
| Grounded AI cannot invent authoritative figures | `packages/ai_engine/src/quantops_ai/citations.py`; `numerical.py`; `validation.py`; `workflow.py` | 110 tests, 97% coverage; citation and numerical validators at 100% branches | pgvector and external provider profiles remain unverified. |
| Deterministic AI safety evaluation | `packages/ai_engine/evals/v1/cases.jsonl`; checked evaluation report | 44/44 cases across 20 categories; deterministic labeled checks, no model grader as sole judge | Recorded latency is host-specific; external cost/tokens are null. |
| AI exposed without weakening risk authority | `apps/api/quantops_api/application/ai_service.py`; grounded-AI API routes | `apps/api/tests/test_grounded_ai_api.py` covers evidence reconciliation, refusal, scope, auth, idempotency, and rate limits | State is in-process and does not persist across restarts. |
| Read-only MCP boundary | `apps/mcp_server/quantops_mcp`; exact three-tool allowlist and fixed methodology resource | 10 protocol/security tests including real stdio client/server negotiation on MCP `2025-11-25` | Local stdio only; no authenticated remote or live-database claim. |
| No mutation through MCP | MCP read-service protocol and read-only annotations | Tests compare audit state before/after and reject out-of-scope/injection-shaped inputs | Annotations are hints; application authorization remains required for any future remote transport. |
| Repository secret/hygiene guard | `scripts/security_scan.py`; `.gitignore`; `docs/security/threat-model.md` | `tests/test_security_scan.py`; `python scripts/security_scan.py` | High-confidence patterns are not a replacement for platform secret protection or owner review. |

## Reproduce the current no-service gate

```text
uv sync --locked --all-packages
uv run ruff check .
uv run ruff format --check .
uv run pytest -m "not integration and not e2e"
uv run python scripts/docs_check.py
uv run python scripts/security_scan.py
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

The PostgreSQL, Redpanda, Docker smoke, Airflow, MLflow, and live-provider checks require their
explicit profiles. Their absence must produce a visible skip/unavailable status rather than a false
success.
