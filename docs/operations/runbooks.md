# QuantOps operational runbooks

Last reviewed: 2026-07-19

These runbooks cover the local/demo architecture. Commands and service names must be adjusted to
the selected profile. Never delete volumes, reset data, rotate credentials, or contact an external
provider as an improvised mitigation. Preserve request, correlation, pipeline-run, and event IDs.

## 1. PostgreSQL unavailable

- **Detection:** `/api/v1/ready` reports the required database unhealthy; connection failures rise;
  migrations, writes, or repository queries fail.
- **Impact:** authoritative portfolio, price, risk, audit, and outbox operations are unavailable.
  Static documentation and explicitly process-local demo behavior may remain usable.
- **Diagnosis:** inspect the safe readiness reason, container/service health, disk space, connection
  pool saturation, certificate/credential rotation status, and PostgreSQL logs. Do not print the
  connection string.
- **Safe mitigation:** stop accepting authoritative writes, leave readiness failed, and restore the
  configured database endpoint or capacity. Do not switch silently to in-memory persistence.
- **Recovery:** confirm PostgreSQL is accepting connections, run the migration status check, and
  allow bounded reconnects. Drain any outbox backlog only after transactions are healthy.
- **Verification:** readiness is healthy; a read-only fixture query and a reversible isolated test
  transaction succeed; audit/outbox counts reconcile; no unexpected migration ran.

## 2. Redpanda or outbox publication unavailable

- **Detection:** broker connection errors, publisher retries, increasing outbox backlog, or streaming
  readiness/metrics show no recent delivery.
- **Impact:** synchronous committed state remains authoritative, but replay, live updates, and
  asynchronous recomputation are delayed.
- **Diagnosis:** inspect broker profile health, topic metadata/ACLs, publisher correlation IDs,
  oldest unpublished row age, retry count, and the last safe error class.
- **Safe mitigation:** keep events in the outbox, use bounded backoff, and disable replay if backlog
  growth threatens the database. Never mark an event published without an acknowledgement.
- **Recovery:** restore the broker, resume one publisher instance, and drain in order. Expect possible
  duplicate publication and rely on consumer idempotency.
- **Verification:** backlog returns to zero, duplicates do not change authoritative counts, offsets
  advance only after durable processing, and processed/duplicate/retry metrics reconcile.

## 3. Malformed, late, or poison event

- **Detection:** rejected/late/DLQ counters increase or a partition stops progressing under bounded
  retry policy.
- **Impact:** the invalid record is not applied; later valid records may wait if the failure is not
  classified permanently.
- **Diagnosis:** use event ID, type, schema version, producer, and safe validation codes. Do not log
  the full payload or authorization data. Determine transient versus deterministic failure.
- **Safe mitigation:** send permanently invalid input to the versioned DLQ with redacted metadata;
  retry only transient failures within the configured cap. Preserve the original source offset.
- **Recovery:** fix the producer or add an explicitly reviewed schema migration, then replay from a
  known boundary into an isolated verification consumer before production scope.
- **Verification:** DLQ visibility exists, the source partition progresses, duplicate replay is a
  no-op, and deterministic risk output matches the expected fixture.

## 4. Migration failure

- **Detection:** deployment/migration job exits nonzero, readiness remains failed, or Alembic reports
  a revision mismatch.
- **Impact:** new application code must not serve against an unknown or partially migrated schema.
- **Diagnosis:** capture current revision, failed revision, PostgreSQL error code, lock activity, and
  available disk. Review the generated SQL and backup/restore readiness without exposing secrets.
- **Safe mitigation:** halt rollout and application writes. Prefer forward correction in a new
  reviewed revision; use downgrade only when that revision explicitly supports and tests it.
- **Recovery:** restore from a verified backup if the database is inconsistent, or apply the corrected
  migration in a clone before the target environment.
- **Verification:** clean-database upgrade and existing-data upgrade both reach head; constraints,
  indexes, extension state, and representative queries pass; application readiness becomes healthy.

## 5. Stale, missing, or partial market data

- **Detection:** freshness/quality status is stale or partial, gap rules fire, or risk returns an
  insufficient-history status.
- **Impact:** risk may be unavailable or explicitly partial; numbers must not be labeled current or
  complete.
- **Diagnosis:** inspect lineage ranges, source watermark, accepted/quarantined counts, instrument
  calendar alignment, and adapter retrieval status.
- **Safe mitigation:** retain the last snapshot with a visible timestamp and stale/partial label.
  Do not forward-fill silently or advance the watermark past rejected input.
- **Recovery:** repair or re-ingest the bounded missing range idempotently, rerun quality checks, then
  recompute from the earliest affected timestamp.
- **Verification:** freshness returns within policy, row counts and hashes reconcile, affected
  snapshots receive updated evidence, and unrelated historical snapshots remain immutable.

## 6. Model artifact missing, incompatible, or drifted

- **Detection:** artifact hash/schema mismatch, load failure, failed promotion gate, or operational
  PSI/Jensen-Shannon threshold breach.
- **Impact:** candidate classification is unavailable or unreliable; risk calculations are unaffected.
- **Diagnosis:** verify dataset hash, feature schema, code revision, promotion record, active-model
  identity, and drift windows. Never unpickle an untrusted model.
- **Safe mitigation:** keep or restore `rule-baseline-v1`, report candidate/drift status, and stop
  candidate promotion. Do not retrain automatically on unreviewed data.
- **Recovery:** reproduce training/evaluation with fixed configuration and seeds, review all gates,
  then publish a new content-addressed artifact only if policy passes.
- **Verification:** deterministic inference repeats, schema and hash match, model card is complete,
  API/UI identify the true active baseline/candidate, and risk values are unchanged.

## 7. External AI provider timeout or invalid output

- **Detection:** provider timeout/error, invalid JSON, unknown citation, numerical mismatch, scope
  violation, or excessive response/tool budget.
- **Impact:** one generated explanation fails; authoritative portfolio risk and the dashboard remain
  available.
- **Diagnosis:** inspect redacted provider status, validation issue codes, safe trace counts, fallback
  flag, and request/correlation ID. Never log keys, hidden prompts, full document bodies, or raw
  provider output containing sensitive content.
- **Safe mitigation:** perform at most one bounded repair, then use the deterministic provider or a
  structured refusal. Disable the optional provider if failures persist.
- **Recovery:** correct allowlisted configuration or provider compatibility and exercise mocked plus
  isolated non-sensitive checks before re-enabling.
- **Verification:** deterministic fallback passes schema/citation/numerical validators, prohibited
  trade/secret/injection requests remain refused, and no external failure affects risk calculation.

## 8. Artifact store or local disk failure

- **Detection:** write/rename failure, checksum mismatch, low disk, or an expected report/model
  artifact is absent.
- **Impact:** a pipeline/evaluation may fail to publish evidence; existing database state should not
  be relabeled complete.
- **Diagnosis:** inspect free space, permissions, target path ownership, temporary-file residue, and
  expected content hash. Do not broaden permissions recursively.
- **Safe mitigation:** stop the affected writer, preserve the last verified artifact, and mark the run
  failed. Never overwrite a known-good artifact with partial content.
- **Recovery:** restore capacity/permissions, rerun the idempotent writer to a temporary file, verify
  its hash, then atomically replace the target.
- **Verification:** manifest and file hashes agree, a second run changes zero content, failed run
  metadata remains visible, and no unrelated files were removed.
