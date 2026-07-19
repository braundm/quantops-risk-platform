# ADR 0003: Redpanda with at-least-once idempotent processing

- Status: accepted; broker integration evidence pending
- Date: 2026-07-19

## Context

The replay story needs Kafka-compatible events, but exactly-once claims across a database and
broker would be misleading. Publication can repeat after uncertain acknowledgements, and consumers
can restart before committing an offset.

## Decision

Use Redpanda as an optional Kafka-compatible profile with versioned envelopes. Write important
domain events to an outbox in the originating transaction. Publish at least once, commit consumer
offsets only after durable handling, and enforce stable idempotency keys in code and database
constraints. Bound retries and late-arrival windows; route permanent validation failures to a DLQ
with safe metadata.

## Consequences

Duplicate delivery is expected and observable rather than hidden. Replay can be deterministic
without corrupting state. The core application remains usable without Redpanda, and broker-backed
claims remain unchecked until integration tests run against the real service.
