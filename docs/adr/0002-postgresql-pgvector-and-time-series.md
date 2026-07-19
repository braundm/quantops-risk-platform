# ADR 0002: PostgreSQL, pgvector, and time-oriented tables

- Status: accepted; live integration evidence pending
- Date: 2026-07-19

## Context

Portfolio state, immutable risk evidence, audit history, idempotency records, and approved document
chunks need transactional integrity and queryable lineage. Adding separate transactional, vector,
and time-series databases would enlarge the operational surface of the demonstration.

## Decision

Use PostgreSQL as the source of record, PostgreSQL-native constraints and indexes for time-oriented
queries, and pgvector for approved-document retrieval. Keep repository ports independent of
SQLAlchemy. Preserve exact money with `NUMERIC`, UTC timestamps, immutable identifiers, and explicit
semantic versions. Consider partitioning only after measured table size and query plans justify it.

## Consequences

Transactional outbox, audit, and portfolio changes can commit atomically. Vector retrieval shares
the same scope metadata as evidence. A clean live migration and pgvector query plan still require a
real PostgreSQL service; offline DDL compilation is not equivalent proof.
