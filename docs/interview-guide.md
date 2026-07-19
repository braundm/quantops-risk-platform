# QuantOps interview guide

This guide helps the repository owner explain the system accurately. It is not a script for claiming
work that has not been personally reviewed. Statements about live PostgreSQL, Redpanda, Airflow,
MLflow, Docker, or external providers must stay qualified until their pending gates pass.

## 30-second product pitch

QuantOps is a production-style market-risk research platform built around reproducibility and
traceability. It calculates versioned VaR, Expected Shortfall, volatility, drawdown, concentration,
risk contributions, and deterministic stress scenarios from a fixed synthetic multi-asset dataset.
Every displayed result carries methodology, quality, and evidence identity. A bounded AI analyst can
summarize approved evidence, but it cannot calculate authoritative metrics, mutate state, recommend
trades, or execute orders.

## Two-minute architecture walkthrough

The synchronous product is a modular FastAPI monolith. Framework-free domain and risk packages sit
at the center; infrastructure depends inward on them. SQLAlchemy and Alembic define the PostgreSQL
boundary, while the current no-service demo uses deterministic process-local application services.
Separate packages handle versioned events, an idempotent broker-neutral stream worker, offline-first
scheduler wrappers, a leakage-safe ML lifecycle, grounded AI, and a three-tool read-only MCP server.
The React UI presents portfolio, scenario, lineage, evidence, model, and audit views through a typed
local adapter. Optional Redpanda, Airflow, MLflow, provider, and observability profiles must fail
safely and are not prerequisites for unit tests.

## Five-minute demo

1. Open the dashboard and state that all data is deterministic and synthetic.
2. Point out portfolio value, historical and parametric VaR, Expected Shortfall, volatility,
   drawdown, and signed contributions. Open methodology details to show confidence, window, horizon,
   observations, units, and version.
3. Open evidence and trace one metric to snapshot, portfolio version, prices, and quality state.
4. Run `combined_liquidity_stress`; explain that inputs and result are immutable, versioned, and
   hypothetical and do not mutate the portfolio.
5. Inspect the canonical quality run and quarantine examples, including malformed and late records.
6. Open the grounded brief, verify a cited number, then explain how advice and prompt-injection
   requests return a refusal without tool or provider calls.
7. Finish on the model view: the transparent rule baseline remained active because the candidate
   failed promotion gates. This is risk-regime classification, not a price or profitability model.

## Risk mathematics explanation

- Prices are aligned under an explicit calendar policy before close-to-close returns are calculated.
- Historical VaR is an empirical loss quantile; parametric VaR uses covariance and an explicit normal
  approximation. Neither is a maximum possible loss.
- Expected Shortfall averages losses in the tail beyond the VaR threshold and exposes finite-sample
  limits.
- Volatility uses sample statistics and explicit annualization. Drawdown tracks peak, trough, and
  recovery where present.
- Signed Euler contributions reconcile to portfolio parametric risk within a documented tolerance;
  diversifying negative contributions are not clipped.
- Insufficient, stale, ambiguous-currency, or non-finite inputs produce typed non-trustworthy states,
  never a persuasive `NaN`.

## Data pipeline explanation

The generator uses fixed seed `20250317` to create 2,088 canonical bars across normal, volatile,
correlation-change, shock, recovery, and quality-stress intervals. A manifest records hashes and
lineage. Re-running generation is content-aware and byte-reproducible. Quality services classify
accepted, duplicate, late, missing, and malformed examples and write bounded quarantine evidence.
Versioned event envelopes provide stable idempotency keys. The broker-neutral consumer records
durability before acknowledging offsets and treats delivery as at-least-once, never exactly-once.

## AI safety explanation

Financial analytics are the authority; AI is a narrator. The workflow classifies intent, selects
from a fixed read-only tool allowlist, retrieves only approved portfolio-scoped evidence, validates
citations and numerical claims, permits one bounded repair, and otherwise falls back or refuses.
Budgets cap tool count, elapsed time, and response size. The 44-case deterministic evaluation covers
20 normal, numerical, cross-scope, injection, advice, execution, secret, and failure categories.

## ML lifecycle explanation

Ten point-in-time features are built without future data. Chronological partitions replace random
splits. A transparent rule baseline is evaluated before a fixed-seed K-Means candidate. Selection
uses validation results and reports every configured seed; test performance does not choose the
model. Promotion gates compare macro F1, adjusted Rand index, stress false-negative rate, and
calibration. The candidate was rejected, so `rule-baseline-v1` remains active. Content-addressed
artifacts, a model card, promotion metadata, and PSI/missingness/Jensen-Shannon drift evidence make
the result reproducible and reversible.

## Thirty likely technical questions

1. **Why a modular monolith?** The synchronous risk workflow needs strong transactional and domain
   boundaries, not network hops. Separate workers exist only where replay or isolation adds value.
2. **How do you prevent framework leakage?** Domain and risk packages have no FastAPI, SQLAlchemy,
   broker, MLflow, or provider imports; dependency direction is tested and documented.
3. **Why `Decimal`?** Quantities and monetary values need explicit precision and rounding; binary
   floating point would create misleading financial reconciliation behavior.
4. **How is currency handled?** Values carry validated ISO currencies and ambiguous conversion data
   is rejected. The demo is intentionally USD-only rather than hiding an incomplete FX layer.
5. **What is the VaR sign convention?** VaR is presented as a non-negative loss magnitude at a stated
   confidence and horizon, with methodology metadata beside the number.
6. **Why provide both historical and parametric VaR?** They expose different assumptions and failure
   modes: empirical history versus covariance and normality approximation.
7. **Why Expected Shortfall?** It describes average severity beyond VaR, while still requiring an
   explicit warning about sparse finite tails.
8. **How do contributions reconcile?** Signed Euler contributions use the same covariance-based risk
   definition as parametric VaR and are checked against the portfolio total within tolerance.
9. **How are missing observations handled?** Alignment is explicit, overlap counts are surfaced, and
   unlimited forward filling is prohibited.
10. **What makes scenarios reproducible?** Definitions, ordering, assumptions, snapshot identity,
    and result IDs are versioned; runs never mutate source positions or prices.
11. **How is optimistic concurrency enforced?** Portfolio writes require the expected version through
    ETag/`If-Match`, and persistence mappings define the corresponding version constraints.
12. **How is write retry safety handled?** Idempotency keys bind to normalized request parameters;
    reuse with different content is a conflict rather than an accidental duplicate action.
13. **Why at-least-once events?** It matches realistic broker behavior. Stable event identity,
    uniqueness, and idempotent consumers make duplicates harmless without a false exactly-once claim.
14. **When is an offset acknowledged?** Only after the consumer's durable boundary succeeds; tests
    cover ordering, duplicate delivery, retry, and broker-outage behavior.
15. **What goes to the DLQ?** Bounded metadata and safe failure context, not secrets or unbounded raw
    payloads.
16. **How do you handle late data?** The worker applies an explicit lateness policy and records metrics
    and disposition instead of silently rewriting trusted history.
17. **How is the synthetic dataset trustworthy?** Fixed configuration, record-level synthetic labels,
    manifest hashes, deterministic generation, and quality-case lineage are checked in tests.
18. **How do you prevent feature leakage?** Features use only information available at each timestamp,
    chronological splits are enforced, and dedicated tests perturb future observations.
19. **Why keep a rule baseline?** It is transparent, cheap, reproducible, and creates a meaningful
    promotion threshold for any more complex candidate.
20. **Why was the ML candidate rejected?** It did not clear the declared relative macro-F1 and
    calibration gates. Rejecting it is evidence that promotion policy is active.
21. **Does the model predict prices?** No. It classifies synthetic risk regimes and makes no direction,
    return, or profitability claim.
22. **What can the AI tools do?** Exactly bounded read-only evidence retrieval operations. They cannot
    write portfolios, trigger trades, run shell commands, or access arbitrary URLs or files.
23. **How are hallucinated numbers blocked?** Numerical statements are parsed and reconciled to
    canonical evidence under declared rounding rules before a brief is accepted.
24. **How is prompt injection handled?** Retrieved content remains untrusted data, tool choice is
    allowlisted, scope is validated independently, and prohibited intent produces a deterministic
    refusal.
25. **How is cross-portfolio leakage prevented?** Request scope, tool inputs, retrieved evidence, and
    citations must all match the approved portfolio identity.
26. **Why a deterministic AI provider?** The core demo and CI must work without keys, cost, network,
    or provider nondeterminism while exercising the same validation boundary.
27. **What does MCP expose?** Three read-only analytics tools and one fixed methodology resource over
    local stdio, with UUID/scope, timeout, and response-size checks.
28. **What is currently not live?** The critical API/UI path still uses deterministic local adapters;
    live PostgreSQL, Redpanda, Airflow, MLflow, external provider, and telemetry profiles need their
    recorded integration gates.
29. **What evidence supports quality claims?** Package tests and coverage, strict typecheck groups,
    checked OpenAPI, deterministic hashes, AI evaluation JSON, CI definitions, threat model, runbooks,
    and `docs/engineering-evidence.md`.
30. **What would production use require?** Real identity/OIDC and authorization, secrets management,
    HA storage/brokers, durable scheduler state, telemetry/SLOs, backups, deployment hardening, model
    governance, licensed data, and independent financial/security review.

## Ten trade-off questions

1. **Why not microservices?** They would add network consistency and operational cost before service
   boundaries justify independent scaling or ownership.
2. **Why not event-source everything?** Most synchronous reads/writes are clearer transactionally;
   events are reserved for replay and asynchronous decoupling.
3. **Why not claim exactly-once?** End-to-end exactly-once is usually an application illusion across
   broker, database, and side effects; idempotent at-least-once behavior is testable and honest.
4. **Why not use floats everywhere?** Numerical libraries may use floats internally, but financial
   inputs, outputs, storage, and reconciliation boundaries need explicit decimal semantics.
5. **Why not use deep learning?** The dataset is synthetic and modest, interpretability matters, and a
   complex model has no demonstrated advantage over the baseline.
6. **Why not random train/test splitting?** Time-series features would leak future regimes into model
   selection and produce misleading evaluation.
7. **Why not let the LLM calculate VaR?** Authoritative mathematics needs deterministic, versioned,
   independently testable code; the LLM is limited to grounded explanation.
8. **Why not expose a general-purpose MCP database tool?** Arbitrary queries expand data-exfiltration,
   mutation, and denial-of-service risk beyond the product's three approved use cases.
9. **Why not require Docker for every test?** Pure logic should remain fast and portable; service tests
   are a separate evidence layer, not a prerequisite for validating core invariants.
10. **Why not connect live market data immediately?** Licensing, rate limits, source instability, and
    non-reproducibility would weaken the default demo. Live adapters belong behind optional ports.

## Concepts the owner must understand

- VaR versus Expected Shortfall, covariance assumptions, signed Euler contribution, drawdown, and
  why historical correlation is unstable.
- Decimal precision, UTC timestamps, optimistic concurrency, transactional outbox, idempotency, and
  at-least-once delivery.
- Chronological ML evaluation, leakage, baseline comparison, promotion gates, drift, and rollback.
- Retrieval scope, prompt injection, citation and numerical validation, safe fallback, and MCP
  capability minimization.
- Which integrations are implemented as ports and which have actually run against live services.

## Owner exercises before claiming authorship

1. Run the quickstart without Codex and record any correction needed.
2. Recalculate one historical VaR example and one signed contribution reconciliation manually.
3. Trace one synthetic bar from manifest and quality result through risk evidence and UI display.
4. Explain and demonstrate duplicate-event idempotency and one DLQ outcome.
5. Run the ML lifecycle and explain why the candidate was not promoted.
6. Inspect one AI evaluation failure fixture and explain the validator or refusal that handles it.
7. Connect an MCP client over stdio and call one tool while confirming no mutation tool exists.
8. Review the threat model and rehearse one database, broker, and provider outage response.
9. Implement and test one small feature personally, then commit it under the owner's identity.
10. Replace owner-review placeholders only with actions the owner actually performed.
