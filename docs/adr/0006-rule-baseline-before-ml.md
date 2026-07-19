# ADR 0006: Rule baseline before a learned regime model

- Status: accepted
- Date: 2026-07-19

## Context

A regime model trained on designed synthetic periods can appear sophisticated while performing
poorly out of sample. Promotion needs an understandable fallback and a comparison that cannot be
selected after inspecting test results.

## Decision

Define and version a deterministic rule baseline first. Train candidates with point-in-time
features, chronological partitions, fixed seeds, and a declared median-validation selection policy.
Promote only when every automated compatibility, leakage, performance, calibration, determinism,
and model-card gate passes. Otherwise retain the baseline and publish the rejection.

## Consequences

The active classifier is always available and explainable. A learned candidate is not described as
a price predictor, and weak results remain visible rather than being optimized away or cherry-picked.
