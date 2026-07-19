# Engineering risk register

| Risk | Impact | Mitigation | Current state |
|---|---|---|---|
| Financial formula/sign error | Misleading risk figures | Pure versioned functions, hand-worked examples, property tests, reconciliation tolerances | Open until Milestone 3 gates pass |
| Look-ahead leakage | Invalid ML evidence | Timestamp-safe features, chronological splits, train-only scalers, explicit leakage tests | Planned |
| Duplicate/replayed events | Corrupt state or inflated counts | Stable idempotency keys, unique constraints, durable processing before offset commit | Planned |
| Stale or incomplete prices | False confidence | Typed insufficient/stale quality states and evidence manifests | Planned |
| Currency ambiguity | Incorrect valuation | Currency value object, explicit FX boundary, single-currency required fixture | In design |
| Prompt injection/fabricated claims | Unsafe or ungrounded brief | Read-only allowlist, untrusted retrieval boundary, citation and numerical validators, deterministic fallback | Planned |
| Optional service coupling | Demo becomes fragile | Core runs without broker/Airflow/MLflow/external LLM/observability | In design |
| Dependency/supply-chain issue | Build or security failure | Lockfiles, pinned CI actions, audits, SBOM, minimal dependencies | Open until scans run |
| Newly released toolchain incompatibility | Lint/build failure despite individually stable packages | Prefer the newest mutually supported versions; TypeScript 6.0.3 is pinned until typescript-eslint supports TypeScript 7 | Mitigated and documented |
| Tooling absent locally | Unverified integration paths | Bundled runtimes for unit/build gates; record Docker/gh limitations truthfully | Active: Docker and gh unavailable |
| Scope inflation | Broad but shallow implementation | P0 before P1, P1 before P2, milestone exit evidence, factual progress log | Controlled |
| Secret leakage | Public credential exposure | `.gitignore`, environment-only secrets, redaction, secret scan before commits/publication | Controls started |
| AI-generated code ownership gap | Owner cannot defend project | AI-assistance record and explicit owner verification exercises | Planned |
