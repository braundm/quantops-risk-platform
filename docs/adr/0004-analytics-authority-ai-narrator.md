# ADR 0004: Transparent analytics are authoritative; AI narrates

- Status: accepted
- Date: 2026-07-19

## Context

Market-risk figures require reproducibility, units, versioned methodology, and evidence. A language
model is not a reliable calculator or source of record and may fabricate numbers or citations.

## Decision

Only the typed risk engine and persisted evidence create authoritative metrics. The AI workflow may
retrieve bounded read-only evidence and explain it in a structured response. Every factual factor
must cite an in-scope evidence ID, and numerical claims are validated against canonical values and
rounding rules. Invalid provider output falls back deterministically or is refused.

## Consequences

Risk calculation works without an external model. Generated prose can never update portfolios,
prices, scenarios, or risk snapshots. Explanations may be less free-form, but they are inspectable,
testable, and safer.
