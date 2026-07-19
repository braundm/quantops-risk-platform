# MCP threat model

## Assets and trust boundaries

The protected assets are portfolio state, risk and evidence integrity, local files, process and
environment data, database credentials, and the distinction between deterministic calculations and
model-generated text. MCP clients and every supplied argument are untrusted. Application-service
records are trusted only after typed mapping and output validation.

This package supports local stdio development only. It does not define HTTP authentication,
multi-tenant authorization, or a live-database deployment boundary.

## Allowed data flow

```text
MCP client -> typed, scoped read request -> bounded adapter -> DemoQuantOpsService read method
           <- validated structured result + explicit evidence/safety labels <-
```

Only the fixed `demo` scope is accepted. Portfolio and snapshot UUIDs must parse and must belong to
the seeded demo portfolio. The scenario catalog has no user-controlled query or execution input.

## Threats and controls

| Threat | Control |
|---|---|
| Prompt injection in identifiers or scope | Inputs are data validated as UUID and literal scope; no input is interpreted as an instruction. |
| Capability escalation | The exported tool list is an exact three-name allowlist; tests reject mutation-like names and verify read-only annotations. |
| Cross-portfolio access | IDs are checked against the single approved demo portfolio after UUID validation. |
| Arbitrary file, shell, URL, environment, or database access | No such parameter or adapter exists; methodology content is a package constant. |
| Duplicate business logic | The adapter calls application-service read methods and only maps their records to MCP schemas. |
| Resource exhaustion | Application calls have a one-second timeout; results are serialized and rejected above 32 KiB; scenario count is capped. |
| Misleading model authority | Outputs are labelled synthetic and not investment advice; MCP never computes authoritative metrics or samples an LLM. |
| Error detail leakage | Validation/application failures return bounded public messages; no tracebacks, credentials, or internal paths are intentionally returned. |
| Mutation through a read method | The adapter accepts only a narrow read-service protocol. Integration tests compare application audit state before and after calls. |

## Explicitly absent capabilities

- portfolio creation, edits, or position replacement;
- risk recomputation or scenario execution;
- replay control, data ingestion, or audit writes;
- raw SQL or ORM session access;
- filesystem paths, shell commands, URLs, arbitrary resource URIs, environment keys, secrets, or
  provider configuration;
- MCP prompts, sampling, elicitation, roots, or model-controlled follow-up actions.

## Residual risks and production work

Tool annotations are hints and clients must not treat them as authorization. A future remote
transport needs authenticated principals, tenant-aware authorization in the application layer,
audience-bound tokens, request quotas, transport body limits, security telemetry, and deployment
tests against the chosen data adapter. The deadline limits how long MCP waits for a synchronous
read; Python cannot forcibly stop a worker thread, so a timed-out read may finish in the background.
That operation remains confined to the read-only service protocol. None of the production controls
listed here are claimed.
