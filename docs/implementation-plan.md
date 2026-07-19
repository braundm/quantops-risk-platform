# Implementation plan

## Delivery strategy

QuantOps is delivered as thin, verified vertical slices. Framework-free financial logic and deterministic fixtures come before infrastructure-heavy integrations. Each milestone must leave the repository runnable and record actual verification in `docs/progress.md`.

1. Establish reproducible Python/TypeScript workspaces, smoke tests, Compose, CI skeleton, and continuity documents.
2. Model domain invariants first, then map them into PostgreSQL with explicit constraints, audit, outbox, and optimistic concurrency.
3. Generate canonical synthetic fixtures and exercise validation, idempotency, quarantine, and lineage.
4. Build and thoroughly test the independent risk engine before exposing it through application services and REST.
5. Build the dashboard against versioned API contracts and deterministic fixtures.
6. Add streaming, Airflow wrappers, ML lifecycle, grounded AI, and MCP as bounded optional profiles.
7. Add observability and deployment examples only after the coherent P0/P1 product is stable.
8. Run clean-room verification, capture real screenshots, then and only then publish.

## Architectural constraints

- Synchronous business behavior remains a modular monolith.
- PostgreSQL owns durable state. Kafka-compatible events are at-least-once and idempotent, never described as exactly-once.
- `Decimal`/`NUMERIC`, UTC-aware timestamps, UUIDs, and explicit currencies are mandatory at financial boundaries.
- Numerical engines are authoritative; AI receives immutable evidence and only narrates it.
- Optional service outages degrade features without making the core demo unusable.

## Verification cadence

Run package-local unit/type/lint gates during development, then root gates before each milestone commit. Run Docker-backed checks only when Docker is available. Never convert an unavailable gate into a passing claim.
