# QuantOps grounded AI engine

This package implements a bounded, offline-first risk analyst over explicitly supplied synthetic
evidence. It is not a general chatbot. It cannot trade, mutate portfolios, browse arbitrary URLs,
reveal prompts or secrets, or produce unsupported authoritative numbers.

The default provider is deterministic and requires no key. An optional OpenAI-compatible provider
uses an injected HTTP transport and a configuration-owned HTTPS endpoint; tests never use a
network. Every non-refusal answer passes schema, citation, numerical, content, and portfolio-scope
validation. One repair is allowed before deterministic fallback or refusal.

Run the versioned evaluation suite from this directory:

```powershell
python -m quantops_ai evaluate --output artifacts/evaluation-report.json
```

All documents and market facts in the demo are synthetic. Output is risk explanation only, never
investment advice, a price forecast, or an execution instruction.
