# QuantOps event contracts

This package contains the versioned JSON contracts shared by QuantOps producers and consumers.
It deliberately has no broker, Kafka, database, FastAPI, or provider SDK dependency.

Supported v1 event types:

- `market.price_bar.v1`
- `portfolio.changed.v1`
- `risk.recompute.requested.v1`
- `risk.snapshot.created.v1`
- `ai.brief.requested.v1`
- `ai.brief.created.v1`

Use `EventEnvelope` to create an event, `to_canonical_json()` for deterministic transport bytes,
and `parse_event_json()` at untrusted boundaries. The parser rejects unknown/future versions and
oversized input before payload validation. Decimal values serialize as canonical JSON strings,
timestamps serialize in UTC, and the idempotency key is derived from each payload's stable natural
identity rather than delivery-specific envelope IDs.
