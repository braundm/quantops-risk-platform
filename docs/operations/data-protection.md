# Local data protection and recovery

## Scope

This document covers the designed PostgreSQL source of record and the deterministic local demo. It
does not claim that production backups have run in the current environment. Canonical synthetic
fixtures in `data/synthetic` are reproducible source artifacts; mutable database state, audit rows,
outbox records, risk snapshots, scenario runs, and model metadata require a real backup policy once
the PostgreSQL profile is active.

## Data classes

| Class | Recovery source | Notes |
| --- | --- | --- |
| Canonical synthetic fixtures | Git plus manifest regeneration | Verify aggregate and file hashes before use. |
| PostgreSQL portfolio/risk state | Database backup and WAL/PITR in production | Preserve portfolio versions, audit, outbox, and evidence together. |
| Quarantine and pipeline runs | Database backup or bounded exported artifacts | Retain source event and pipeline-run identity. |
| ML lifecycle artifacts | Content-addressed artifact store plus metadata backup | Never restore an artifact without verifying its hash. |
| AI evaluation reports | Versioned cases plus generated report | Reports are reproducible and contain no provider secret. |

## Backup policy for a real deployment

1. Encrypt backups at rest and in transit using owner-controlled keys.
2. Use a least-privilege backup identity that cannot alter application data.
3. Take scheduled full backups and continuous WAL/archive backups where the recovery-point objective
   requires point-in-time recovery.
4. Record database engine/extension versions, Alembic revision, start/end timestamps, object count,
   encrypted location, checksum, and retention class.
5. Keep at least one copy outside the primary failure domain and apply immutable retention where
   operationally justified.
6. Exclude application secrets, raw prompts, and credentials from backup manifests and logs.
7. Test restore into an isolated environment on a schedule; a successful backup command alone is not
   recovery evidence.

Recovery-point and recovery-time objectives are owner/deployment decisions. They must not be invented
for this portfolio project.

## Restore rehearsal

1. Declare the isolated target, incident/rehearsal ID, desired recovery timestamp, and approved
   operator. Confirm the target database name clearly denotes a non-production test.
2. Provision the same supported PostgreSQL major version and required extensions, including vector.
3. Restore the backup without exposing connection strings in logs.
4. Run `alembic current` and compare the restored revision to the recorded manifest. Apply migrations
   only through the reviewed migration policy.
5. Verify constraints and counts for portfolios, positions, prices, risk snapshots, scenario results,
   evidence, audit events, pipeline runs, outbox rows, and model metadata.
6. Recompute one deterministic risk snapshot from restored inputs and reconcile value, risk, method,
   data revision, and evidence identity.
7. Confirm unpublished outbox rows are neither lost nor published twice when processing resumes.
8. Run readiness and targeted integration tests, then document elapsed time and any deviation from
   the intended recovery objectives.
9. Destroy or sanitize the isolated restore according to retention policy.

## Deterministic demo recovery

The no-service demo is restored by a clean checkout, locked dependency sync, fixture verification,
and normal startup. Regeneration must leave canonical files byte-identical:

```text
uv run python -m quantops_pipelines generate --output data/synthetic
uv run python -m quantops_pipelines verify --dataset data/synthetic
```

Do not describe fixture regeneration as a backup of mutable database state.
