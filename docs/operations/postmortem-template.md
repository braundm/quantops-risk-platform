# Incident postmortem template

Use this template for material reliability, data, model, security, or financial-correctness incidents.
The report must be blameless, evidence-based, sanitized, and explicit about uncertainty. Do not paste
tokens, connection strings, raw prompts, document bodies, customer data, or unbounded payloads.

## Summary

- Incident ID:
- Title:
- Severity and rationale:
- Status:
- Start / detection / mitigation / recovery times (UTC):
- Affected capabilities and environments:
- Incident commander and review owner:
- One-paragraph user and engineering impact:

## What happened

Describe observed behavior and the violated invariant. Distinguish authoritative risk/data impact
from presentation-only impact. State whether results, lineage, audit records, outbox events, model
status, or AI evidence may be incomplete or untrustworthy.

## Detection

- First signal and correlation/request/event/pipeline IDs:
- Expected alert or test that should have detected it:
- Why detection occurred at this time:
- Detection gaps without invented metrics:

## Timeline

| UTC time | Observed event, decision, or action | Evidence reference |
| --- | --- | --- |
| | | |

## Impact and data integrity

- Requests/jobs/events affected:
- Portfolios or scopes affected:
- Earliest/latest affected timestamps:
- Duplicate, late, quarantined, or lost record assessment:
- Risk/model/AI outputs that were invalidated or regenerated:
- Security/privacy assessment:
- Advice/execution boundary assessment (must remain no advice and no execution):

## Root cause

State the technical and process causes supported by evidence. Separate trigger, contributing factors,
and latent conditions. Do not stop at an individual action or use “human error” as a root cause.

## Response and recovery

- Safe-mode or write/replay/provider controls used:
- Data or artifact restoration/recomputation performed:
- Idempotency and reconciliation evidence:
- Validation proving recovery:
- Residual uncertainty:

## What worked / what did not

Record concrete strengths and gaps in tests, dashboards, runbooks, ownership, communication, and
system behavior.

## Corrective actions

| Priority | Action | Owner | Due date | Verification / closure evidence |
| --- | --- | --- | --- | --- |
| P0 | | | | |

Actions should prefer durable invariant, test, tooling, or observability improvements over reminders.

## Review

- Reviewers and date:
- Links to sanitized logs, traces, tests, commits, and runbook changes:
- Owner approval for closure:
- Follow-up rehearsal date:
