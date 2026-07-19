# ADR 0007: Bounded read-only AI and MCP tools

- Status: accepted; transport integration evidence pending
- Date: 2026-07-19

## Context

Tool-using assistants and MCP clients can broaden an application's attack surface through prompt
injection, excessive context, arbitrary resource access, and accidental mutation.

## Decision

Expose a fixed allowlist of typed read-only application tools with portfolio/snapshot scope,
response-size, timeout, and call-count budgets. Retrieved text is untrusted data. Provide no shell,
filesystem, arbitrary URL, raw database, environment, or mutation tool. MCP uses local stdio by
default and exposes only approved methodology/model-card resources. AI requests apply deterministic
scope, refusal, citation, and numerical validators.

## Consequences

Clients can inspect risk evidence without gaining write authority. Some open-ended questions are
refused or answered narrowly. Any future tool requires an explicit security review and regression
tests before joining the allowlist.
