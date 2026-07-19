# Database migration policy

## Principles

- Alembic revisions are immutable after merge and use deterministic, reviewed SQLAlchemy metadata.
- Every migration must be safe for a clean database and for the declared supported previous revision.
- Schema changes and application behavior must be deployable in an expand/migrate/contract sequence
  when a one-step change could break running readers or writers.
- PostgreSQL constraints are part of the domain safety boundary, not documentation-only hints.
- Migration logs must not contain credentials or sensitive row contents.

## Authoring checklist

1. State the data invariant and compatibility window the change supports.
2. Give every constraint and important index a stable name.
3. Separate schema expansion from large backfills; make backfills restartable and observable.
4. Avoid table rewrites or long blocking locks without a measured plan and maintenance decision.
5. For new required fields, add nullable/default-compatible storage first, backfill and validate, then
   enforce `NOT NULL` in a later reviewed revision.
6. Define downgrade behavior honestly. A destructive or lossy downgrade must fail with a clear
   operator instruction rather than pretend reversibility.
7. Update mappings, repositories, API contracts, seed/upsert behavior, and tests in the same change.
8. Review generated SQL for extension, index, precision, timestamp, and cascade behavior.

## Verification gates

Offline compilation is a fast structural check:

```text
uv run alembic -c apps/api/alembic.ini upgrade head --sql
```

A migration is not live-verified until CI or an operator performs all of the following against an
isolated PostgreSQL database whose name contains `test`:

1. create the database and required extensions from clean state;
2. upgrade from base to head;
3. assert named constraints, indexes, numeric precision, vector support, and repository behavior;
4. insert and reject representative valid/invalid records;
5. exercise same-transaction audit/outbox behavior and optimistic concurrency;
6. restart the application and confirm readiness plus one read/write flow; and
7. drop the isolated database after retaining sanitized evidence.

## Deployment and rollback

- Take and verify a restorable backup before a migration that changes mutable production data.
- Stop or gate incompatible writers before the contract phase.
- Monitor migration duration, locks, errors, database capacity, readiness, and application error rate.
- Prefer roll-forward with a corrected revision after expansion. Restore from backup only under the
  incident plan when data consistency cannot be recovered safely.
- Never edit the recorded Alembic version manually to make a failed deployment appear successful.
