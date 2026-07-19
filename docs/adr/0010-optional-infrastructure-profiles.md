# ADR 0010: Optional infrastructure profiles must degrade safely

- Status: accepted
- Date: 2026-07-19

## Context

PostgreSQL is the designed source of record, while Redpanda, Airflow, MLflow, external providers,
Prometheus, and Grafana are useful production-style boundaries. Requiring every service for the core
demo would increase startup time, resource consumption, and failure modes. Empty or decorative
profiles must also not imply that an integration works merely because a service name appears in
Compose.

## Decision

Keep the core deterministic domain, risk, data, API, UI, ML, AI, and MCP demonstrations usable
without optional infrastructure. Each optional profile is disabled by default and may be activated
only when it has:

1. an explicit configuration contract with safe local defaults;
2. bounded health/readiness and graceful-unavailable behavior;
3. a real adapter behind an existing application port;
4. isolated integration or smoke evidence against the named service;
5. documented URLs, resource requirements, shutdown, recovery, and data retention; and
6. no paid account, live market source, external LLM, or secret requirement in CI.

Placeholder Compose files use an empty `services` map and a comment explaining the missing evidence.
They are declarations of deferred scope, not runnable profiles. The core application must surface
`not_configured` or `unavailable` honestly and must not silently substitute fake persistence for a
requested live mode.

## Alternatives considered

- **Start every service in the default Compose file:** rejected because it makes the demo fragile and
  obscures which dependency is required for which capability.
- **Delete deferred profiles entirely:** rejected because explicit placeholders document the intended
  boundary and prevent accidental claims that a missing file was overlooked.
- **Mock service health in Compose:** rejected because a green health check without a working adapter
  is misleading evidence.

## Consequences

The default project remains small and deterministic, while optional integrations have a clear
promotion path. Documentation and UI must distinguish designed, implemented, configured, and
verified states. More setup is required before demonstrating the full architecture, but failures are
localized and claims remain auditable.
