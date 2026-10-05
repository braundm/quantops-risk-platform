# ADR 0009: MLflow as an optional reproducibility adapter

- Status: accepted
- Date: 2026-07-19

## Context

QuantOps needs inspectable experiment parameters, metrics, artifacts, model identity, promotion
decisions, and rollback metadata. The required no-key demo and CI must remain deterministic and
usable without a tracking server. Treating an unavailable MLflow service as authoritative would make
reproduction depend on mutable external state and could hide a failed tracking write behind a
successful model promotion.

## Decision

The framework-neutral ML lifecycle produces content-addressed local artifacts and a model card as
its authoritative reproducibility record. An MLflow port may mirror parameters, every evaluated
seed, selection policy, metrics, artifact hashes, active/candidate identity, and promotion outcome
when explicitly enabled. The adapter is disabled by default, has a bounded configuration surface,
and reports `tracking_disabled` or a typed failure without changing the deterministic evaluation or
promotion result.

Promotion is decided by versioned local gates before any registry transition is described as
successful. A future live adapter must use an isolated experiment, preserve dataset/code revisions,
avoid logging credentials or raw document bodies, and pass integration tests against a real tracking
service before the profile is marked verified.

## Alternatives considered

- **Require MLflow for every run:** rejected because it breaks the offline demo and makes unit tests
  depend on a mutable service.
- **Store only MLflow run IDs:** rejected because an external identifier is not a self-contained
  reproducibility record.
- **Commit binary model registries:** rejected because they are opaque, large, and difficult to
  review safely in Git.

## Consequences

Core experiments remain reproducible without network access and can be independently inspected in
Git artifacts. A live MLflow profile adds operational evidence and comparison UX without becoming a
single point of correctness. Until its integration gate passes, the repository must say that MLflow
is optional and unverified rather than showing a fictional active service.
