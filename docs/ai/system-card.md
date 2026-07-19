# Grounded risk analyst system card

Last reviewed: 2026-07-19

## Purpose and authority

The QuantOps grounded risk analyst explains already-computed portfolio-risk evidence. It is a
bounded research and observability feature, not a general chatbot, financial adviser, price
predictor, or execution agent. The versioned risk engine and immutable evidence package are the
only authorities for figures; generated prose cannot create or change a metric.

## Default operating mode

The required path uses `DeterministicRiskBriefProvider` and needs no API key or network. It renders
only supplied synthetic evidence. Approved keyword retrieval is deterministic when embeddings are
unavailable. The optional OpenAI-compatible provider is behind an injected HTTP port, an explicit
HTTPS host allowlist, bounded response/timeout settings, and the same post-generation validators.
It is disabled by default and was not contacted by the recorded evaluation.

The deterministic workflow is exposed through the versioned application API for create/get brief
and synchronous evaluation operations. The current browser uses its typed local adapter rather than
that live API client, so UI presentation is not evidence of network integration.

## Inputs and data

Requests contain a bounded question plus explicit portfolio, snapshot, scenario, or document scope.
Evidence items carry stable IDs, portfolio scope, kind, source metadata, synthetic status, and
canonical metric units/values when applicable. Retrieved document content is untrusted data and is
never interpreted as a system instruction. The bundled evaluation and demo evidence are fictional.

## Workflow and controls

1. Classify unsupported, dangerous, or excessive requests before tool use.
2. Select from ten fixed read-only tools; enforce call, per-call time, total time, and byte budgets.
3. Retrieve only approved, deduplicated, portfolio-scoped evidence.
4. Generate a frozen structured `RiskBrief`.
5. Validate schema, citations, citation coverage, scope, numerical units/rounding, and content.
6. Permit one bounded repair, then use the deterministic fallback or structured refusal.

No tool can mutate state, query arbitrary SQL, read files or environment variables, execute shell
commands, or fetch a user-provided URL. Tool audit events record safe field names and evidence IDs,
not secrets, prompts, or document bodies.

## Refusal boundary

The classifier refuses buy/sell/short recommendations, guaranteed forecasts, order execution,
credentials or hidden-prompt requests, chain-of-thought extraction, arbitrary browsing, mutation,
prompt-injection attempts, and excessive tool-loop/context requests. Refusals provide a safe
alternative such as inspecting current exposure or a hypothetical scenario.

## Evaluation

Suite `1.0.0` contains 44 labeled JSONL cases across all 20 specified categories. The local
2026-07-19 run passed 44/44 cases with schema, citation, numerical-consistency, refusal,
tool-selection, and deterministic groundedness rates of `1.0`. It made 23 bounded tool calls; seven
adversarial provider cases intentionally exercised fallback. Citation and numerical-validator
modules reached 100% statement and branch coverage. No model-graded score is used as the primary
evaluator, and external cost/token fields remain null.

The checked report records observed local latency. Timing varies by host and is not a service-level
claim.

## Known limitations

- Synthetic evidence does not demonstrate real-market usefulness or generalization.
- Keyword retrieval is not semantic retrieval; pgvector integration remains unverified.
- The optional provider boundary is mocked in tests and has not been exercised with live data.
- Classification is deliberately conservative and can refuse legitimate but ambiguously phrased
  questions.
- A valid citation proves linkage to supplied evidence, not that the underlying market assumption
  is universally correct.

## Failure behavior

Unknown scope, insufficient evidence, invalid JSON, provider timeout, fabricated citation,
numerical mismatch, oversized response, tool error, or exhausted budget produces a bounded fallback
or refusal. None of these failures interrupts portfolio valuation or risk computation. See the
[threat model](../security/threat-model.md) for broader controls and residual risks.
