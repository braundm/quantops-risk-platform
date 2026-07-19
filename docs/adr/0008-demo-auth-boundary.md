# ADR 0008: Local demo authentication boundary

- Status: accepted for the local demo
- Date: 2026-07-19

## Context

QuantOps needs a small, testable authorization boundary without turning the portfolio project into
an identity platform. Read-only demo exploration should remain easy, while portfolio changes,
recomputation, scenarios, imports, model actions, and risk-brief generation must not be anonymous
writes. The bundled environment contains only fictional, synthetic data and represents one local
demo tenant.

## Decision

Read-only `GET` routes are public in local demo mode. State-changing routes require the
`X-Demo-Token` request header to match `QUANTOPS_DEMO_API_TOKEN`. Comparison uses a constant-time
primitive, the token is never logged or returned, and missing/invalid credentials share the same
bounded problem response. The placeholder in `.env.example` is publicly known and offers no
protection; it must be replaced before exposing the service beyond localhost.

Authorization is enforced at the HTTP/application boundary and covered by tests. The UI is not a
security boundary. Relevant accepted writes carry actor, request, and correlation identifiers into
the audit/outbox transaction. Health and readiness responses expose dependency state, not
connection strings or credentials.

## Consequences

This is appropriate only for a single-user local demonstration. It provides no user lifecycle,
tenant isolation, revocation list, role hierarchy, delegated authorization, or production session
management. CORS is an additional browser control and is not treated as authentication.

## Production upgrade path

A production design should terminate TLS at a trusted ingress, validate short-lived OIDC/OAuth2
access tokens by issuer, audience, signature, expiry, and nonce, and map immutable subject and
tenant claims to application-layer permissions. Add tenant keys to every owned aggregate and query,
RBAC for reader/operator/model-approver/auditor duties, automated key rotation, centralized secret
management, revocation/incident procedures, and authorization-focused audit retention. Prefer
workload identity/OIDC for deployment automation rather than static cloud credentials.
