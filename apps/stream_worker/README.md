# QuantOps stream worker

This package implements the broker-independent part of the QuantOps streaming and transactional
outbox design. It validates the shared `quantops-contracts` envelope before processing and uses the
domain `OutboxEvent` retry state machine for publication. The supplied adapters are deterministic,
process-local implementations intended for replay tests and offline demonstrations.

## Delivery behavior

- Stable contract-derived idempotency keys make exact redelivery a successful duplicate.
- Reusing the same identity with different canonical content is a permanent conflict and is written
  to the dead-letter sink.
- Each topic partition has an event-time watermark. Bounded out-of-order events are processed and
  counted as late; events beyond the configured age or out-of-order bounds are safely dead-lettered.
- Contract-invalid data is permanently rejected. Dead-letter records contain only broker
  coordinates, bounded classifications, UUIDs, byte counts, and SHA-256 digests—never raw payloads
  or exception text.
- Transient processing, dead-letter storage, publish, and commit failures use a bounded exponential
  schedule. Services return the planned millisecond delays and never sleep internally.
- An input offset is committed only after the event/output is durably recorded, an exact duplicate
  is already durable, or a permanent rejection is durably dead-lettered. Exhausted transient work
  leaves the offset uncommitted, and replay blocks later offsets in that partition.
- A validated `portfolio.changed.v1` event deterministically creates exactly one controlled
  `risk.recompute.requested.v1` domain outbox record. Its request/event IDs, correlation, causation,
  methodology, and price-dataset hash are explicit and replay-stable.

Counters cover processed records, duplicates, accepted late records, rejections, scheduled retries,
dead letters, commits, and broker outages. Consumer and publisher instances may use separate metric
objects when those lifecycles need independent dashboards.

## Integration boundary

There is **no live Redpanda/Kafka adapter in this milestone**. `InMemoryBrokerPublisher` records
acknowledged publications and can deterministically simulate an outage. It does not prove broker
connectivity, consumer-group rebalancing, transactional Kafka semantics, or production durability.
A future adapter must implement the ports, preserve idempotency keys, use acknowledged publishing,
commit offsets only after durable work, and add an integration test against an isolated broker.

Run the standalone gates from the repository root:

```powershell
.\.venv\Scripts\ruff.exe format --check apps/stream_worker
.\.venv\Scripts\ruff.exe check apps/stream_worker
.\.venv\Scripts\mypy.exe --config-file apps/stream_worker/pyproject.toml `
  apps/stream_worker/src apps/stream_worker/tests
.\.venv\Scripts\pytest.exe -c apps/stream_worker/pyproject.toml apps/stream_worker/tests
```
