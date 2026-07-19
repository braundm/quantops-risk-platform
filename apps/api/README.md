# QuantOps API

The FastAPI application exposes the versioned `/api/v1` contract. In local demo mode it uses a
process-local, deterministic application service so the product can be explored without claiming
that PostgreSQL, an ML model, or an AI provider is connected. Writes require the configured demo
token, portfolio updates use ETags, and repeatable expensive writes require an idempotency key.

## Dataset boundary

The in-memory fallback contains four synthetic instruments and **41 business dates per instrument
(164 accepted price bars total)**. Its fixed `2024-12-31T21:02:00Z` valuation and risk values are
computed by `quantops-risk`; they are not hard-coded response metrics. This compact fallback is
distinct from the canonical database demo fixture, which contains **2,088 price bars**. Do not use
the fallback's row count as evidence that the database fixture was loaded.

The readiness response identifies the active deterministic-demo mode and reports the database as
`not_configured`. The ML catalog remains explicitly unconfigured. Grounded-AI risk briefs and the
versioned AI evaluation suite run synchronously through a process-local deterministic provider:
they use only the API's authoritative synthetic snapshot values and approved packaged documents,
return validated evidence IDs and safe trace summaries, never call an external provider, and do
not persist across process restarts.

## OpenAPI compatibility

`openapi.generated.json` is the checked-in schema snapshot. Regenerate it after contract changes:

```powershell
.\.venv\Scripts\python.exe apps/api/scripts/export_openapi.py `
  --output apps/api/openapi.generated.json
```

The API contract test fails when the snapshot is stale.
