# ADR 0001: Modular monolith with narrow workers

- Status: accepted
- Date: 2026-07-19

## Context

QuantOps needs transactional portfolio workflows, independently testable financial calculations,
and a few asynchronous boundaries. Splitting every capability into a network service would add
deployment and consistency cost before there is evidence that independent scaling is needed.

## Decision

Use one FastAPI modular monolith for synchronous application behavior. Keep the domain and risk
engine framework-independent. Run only replay consumers, outbox publication, scheduling, grounded
AI, and MCP transports as narrow processes when isolation or asynchronous delivery justifies it.
All boundaries call typed application services instead of duplicating SQL or financial formulas.

## Consequences

Local development and consistency remain simple, and extraction stays possible through explicit
ports. A worker outage degrades its optional capability without changing authoritative risk math.
Module ownership and dependency-direction tests are required to prevent the monolith becoming an
unstructured codebase.
