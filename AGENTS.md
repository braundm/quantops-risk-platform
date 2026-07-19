# QuantOps agent guide

This repository implements the authoritative specification in `QuantOps_AI_Codex_Master_Prompt.md` (kept outside the repository by the owner). Public documentation and code comments must be written in professional English.

## Product boundary

QuantOps is a market-risk research and observability platform. It is not a trading bot. Never add order execution, brokerage connectivity, return guarantees, price-direction claims, or buy/sell recommendations. Synthetic fixtures must always be visibly marked synthetic.

## Architecture

- `packages/domain`: framework-independent entities, value objects, and ports.
- `packages/risk_engine`: pure, versioned financial calculations; no framework, database, or network imports.
- `apps/api`: FastAPI application, application services, SQLAlchemy adapters, migrations, and observability.
- `apps/web`: React/TypeScript dashboard.
- `packages/data_contracts`: versioned Pydantic event envelopes and payloads.
- `pipelines`: reusable CLI-first ingestion and data-quality services.
- `apps/stream_worker`, `apps/mcp_server`, and `apps/scheduler`: asynchronous and integration boundaries.
- `ml`: leakage-safe regime features, training, evaluation, and monitoring.
- `infra`: optional infrastructure profiles. The core demo must remain usable without them.

Dependencies point inward: infrastructure may import application/domain packages, but domain and risk packages must never import FastAPI, SQLAlchemy, Kafka clients, MLflow, or provider SDKs.

## Standard commands

Preferred toolchain is Python 3.12+, `uv`, Node 22+, and `pnpm` 11.15.

```text
make doctor             # or: pwsh scripts/dev.ps1 doctor
make setup              # or: pwsh scripts/dev.ps1 setup
make lint
make typecheck
make test-unit
make test-integration
make test-contract
make test-e2e
make security
make docs-check
```

On Windows without GNU Make, use `scripts/dev.ps1`. Never make live providers, external LLMs, Docker, Redpanda, Airflow, or MLflow prerequisites for unit tests.

## Engineering rules

- Python is fully typed. Use UTC-aware datetimes, UUID identifiers, `Decimal` for quantities and money, and explicit ISO currency validation.
- Public APIs use Pydantic v2 and RFC 9457-style problem details.
- Keep calculations deterministic; no authoritative metric may be calculated by an LLM.
- Validate all event contracts, support at-least-once delivery honestly, and enforce idempotency in code plus database constraints.
- Never propagate `NaN` as a trustworthy result. Return a typed insufficient/invalid status.
- AI tools are bounded and read-only. Every factual factor must cite an in-scope evidence ID, and numerical claims must be validated.
- Tests should demonstrate behavior and invariants. Do not weaken tests or suppress checks merely to obtain a green result.
- Use `apply_patch` for intentional source edits. Preserve unrelated owner work.

## Verification and handoff

After meaningful changes, run the narrowest relevant checks, record exact outcomes in `docs/progress.md`, and update `HANDOFF.md`. A milestone is complete only when its exit evidence is actually verified. Before a commit, inspect the diff and scan for secrets and generated junk.

Do not publish to GitHub until Milestone 14 and the Definition of Done have been met. Preserve any existing remote; never create paid resources.
