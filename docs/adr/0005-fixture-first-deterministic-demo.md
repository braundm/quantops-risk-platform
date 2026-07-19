# ADR 0005: Fixture-first deterministic demonstration

- Status: accepted
- Date: 2026-07-19

## Context

Live market, filing, macro, embedding, and language-model providers introduce credentials, changing
responses, rate limits, cost, and privacy concerns. They make CI and portfolio review unreliable.

## Decision

Ship visibly synthetic, deterministic fixtures as the required path. Record hashes, provenance,
quality cases, and regeneration behavior. Optional live adapters are isolated behind ports, use
recorded-fixture tests, and fail gracefully. No live or paid service is required by CI or the core
demo.

## Consequences

Reviewers can reproduce the same risk and failure stories without credentials. Synthetic behavior
must never be generalized to real markets, and optional adapter status must remain explicit in API,
UI, and documentation.
