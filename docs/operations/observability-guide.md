# Observability guide

## Current evidence boundary

The repository defines correlation IDs, request/event/pipeline identities, broker-neutral stream
metrics, readiness states, and an optional observability Compose placeholder. A live OpenTelemetry,
Prometheus, or Grafana profile has not been verified and must not be shown as active. This guide
defines the required telemetry contract for that future profile.

## Logs

Production-mode logs should be structured JSON; local development may use readable text. Required
fields include UTC timestamp, severity, stable event name, service/component, environment, and the
applicable request, correlation, event, pipeline-run, snapshot, or trace identity.

Never log access tokens, connection strings, secret URLs, full prompts, document bodies, raw event
payloads, arbitrary user text, or stack traces containing configuration. Sanitize CR/LF and bounded
free-text fields to reduce log injection. Record typed error category and safe exception summary.

## Metrics

Use bounded labels such as route template, method, status class, event type/version, job name, result,
model version, and provider name. Never label by raw portfolio, request, event, document, user, prompt,
or error-message values.

Minimum metric families:

- API request count and duration by route template/method/status class;
- database query duration/error and pool saturation when the live adapter exists;
- events consumed, duplicate, conflicting, late, retry, DLQ, and acknowledged;
- pipeline duration plus accepted/rejected/quarantined counts and freshness;
- risk calculation duration, insufficient-data result, and failure;
- outbox pending/oldest age/publication/retry;
- AI request, tool call, validation failure, refusal, fallback, and duration;
- model inference duration, active model identity, promotion result, and drift state.

Financial values, positions, prompts, evidence text, and model feature vectors are not metric labels.

## Traces

Create spans for the FastAPI request/application/repository path, event consumption through risk
recompute, scheduled job through reusable CLI service, AI classify/tool/retrieve/validate/fallback
path, and external adapter calls. Propagate W3C trace context where supported and retain the existing
request/correlation/event identities as attributes. External spans expose provider class and result,
not secret URL parameters or full payloads.

## Readiness and dashboards

Liveness answers whether the process can respond. Readiness names configured dependencies and must
degrade when an authoritative dependency is unavailable. It must never claim PostgreSQL, broker,
tracking, or provider readiness when the deterministic fallback is serving instead.

An optional dashboard should prioritize:

1. request rate/errors/duration and readiness;
2. data freshness, quality disposition, and pipeline duration;
3. event lag, duplicates, retries, DLQ, and outbox backlog;
4. risk calculation status/duration and snapshot freshness;
5. model version, drift, and promotion outcome; and
6. AI refusals, fallbacks, validation failures, tool calls, and latency.

Avoid decorative panels without an operational question or runbook link.

## Alert and incident expectations

Alert on symptoms requiring action: sustained readiness failure, stale canonical inputs, growing
outbox/consumer lag, DLQ spikes, repeated risk failures, invalid snapshot age, drift requiring review,
or elevated AI validation fallback. Every alert needs a severity, owner, bounded evaluation window,
safe first action, and link to `runbooks.md`. Thresholds require measured environment evidence and
must not be invented in this repository.

## Verification required before enabling the profile

- telemetry-disabled mode leaves core behavior and tests unchanged;
- collectors/exporters fail with bounded timeout and no application crash;
- representative logs contain required IDs and no prohibited content;
- metric label cardinality remains bounded under varied portfolio/event inputs;
- traces connect one API, event, and AI critical path without leaking payloads;
- dashboard queries and alert rules load against the actual chosen stack;
- service health, graceful shutdown, storage limits, and retention are documented and smoke-tested.
