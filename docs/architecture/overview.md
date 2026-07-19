# Architecture overview

QuantOps uses a modular monolith for synchronous workflows and narrowly scoped workers for
asynchronous replay, outbox publication, and scheduled pipelines. Solid lines below describe the
target boundaries from the authoritative specification; `docs/progress.md` is the source of truth
for which adapters have actually passed their exit evidence.

## System context

```mermaid
flowchart LR
  User["Risk analyst / engineering reviewer"] --> Web["QuantOps web application"]
  User --> Client["REST or read-only MCP client"]
  Web --> Platform["QuantOps platform"]
  Client --> Platform
  Fixtures["Bundled synthetic fixtures"] --> Platform
  Live["Optional official market / macro sources"] -.-> Platform
  Platform --> Provider["Optional external LLM provider"]
  Platform --> Export["Versioned JSON / CSV reports"]
```

The default demonstration needs no live market source or external LLM. Optional boundaries must
fail closed or degrade visibly without making deterministic risk calculations unavailable.

## Container boundaries

```mermaid
flowchart LR
  Web["React dashboard"] --> API["FastAPI modular monolith"]
  API --> App["Application services"]
  App --> Domain["Domain model"]
  App --> Risk["Pure risk engine"]
  App --> DB[("PostgreSQL + pgvector")]
  Replay["Deterministic market replay"] --> Broker["Redpanda (optional)"]
  Broker --> Worker["Idempotent stream worker"]
  Worker --> DB
  Scheduler["CLI pipelines / Airflow wrappers"] --> DB
  AI["Bounded risk analyst"] --> App
  MCP["Read-only MCP server"] --> App
```

The database is authoritative. Events provide replayable asynchronous decoupling with at-least-once semantics. The risk engine owns numerical calculations; the AI workflow can only retrieve bounded evidence and narrate validated results.

## Application component boundary

```mermaid
flowchart TB
  HTTP["FastAPI routers / problem details"] --> Services["Application services"]
  MCP["Read-only MCP transport"] --> Services
  Consumer["Idempotent event handlers"] --> Services
  Services --> Domain["Framework-free domain"]
  Services --> Risk["Versioned risk engine"]
  Services --> Contracts["Versioned event contracts"]
  Services --> Ports["Repository / clock / FX / evidence ports"]
  Ports --> SQL["Async SQLAlchemy adapters"]
  Ports --> Retrieval["Approved-document retrieval"]
  SQL --> DB[("PostgreSQL + pgvector")]
```

Dependencies point inward. Domain and risk modules do not import FastAPI, SQLAlchemy, Kafka,
MLflow, or provider SDKs. Transports validate and authorize input; application services coordinate
transactions; database and provider details remain replaceable adapters.

## Guarded portfolio-write flow

```mermaid
sequenceDiagram
  actor User
  participant API as FastAPI boundary
  participant App as Application service
  participant DB as PostgreSQL transaction
  User->>API: PATCH portfolio + expected version + demo token
  API->>API: authenticate, validate, attach request/correlation IDs
  API->>App: typed command
  App->>DB: UPDATE ... WHERE version = expected
  alt version matches
    App->>DB: append audit event and outbox event
    DB-->>App: commit aggregate + audit + outbox atomically
    App-->>API: revised portfolio and ETag
    API-->>User: 200
  else stale version
    DB-->>App: zero rows and current version
    App-->>API: optimistic-concurrency conflict
    API-->>User: 409 problem details
  end
```

The outbox is at-least-once: a publisher may send a row more than once. Stable idempotency keys and
consumer-side processing records prevent duplicates from changing authoritative state twice.

## Evidence-grounded explanation flow

```mermaid
flowchart LR
  Question["Bounded user question"] --> Classify["Support / safety classification"]
  Classify -->|"unsafe or unsupported"| Refuse["Structured refusal + safe alternative"]
  Classify -->|"supported"| Tools["Fixed read-only tool allowlist"]
  Tools --> Evidence["Scoped immutable evidence package"]
  Evidence --> Provider["Deterministic provider by default"]
  Provider --> Validate["Schema + citation + numerical + safety validation"]
  Validate -->|"valid"| Brief["Stored structured risk brief"]
  Validate -->|"invalid"| Fallback["One repair, deterministic fallback, or refusal"]
```

Generated language never becomes an authoritative risk value. Retrieved text is untrusted data,
not instruction, and factual factors must cite evidence inside the selected portfolio/snapshot
scope.

## Batch data and lineage flow

```mermaid
flowchart LR
  Sources["Synthetic fixtures / optional approved adapters"] --> Stage["Typed staging records"]
  Stage --> Quality{"Quality rules"}
  Quality -->|"accepted"| Store[("PostgreSQL source of record")]
  Quality -->|"invalid"| Quarantine["Safe quarantine reference"]
  Store --> Features["Point-in-time feature set"]
  Store --> Risk["Versioned risk calculation"]
  Features --> Model["Baseline / candidate evaluation"]
  Risk --> Manifest["Snapshot evidence manifest"]
  Model --> Manifest
  Quality --> Manifest
```

Every reusable pipeline owns a typed configuration hash, run/correlation ID, watermark where
appropriate, and deterministic record counts. Airflow may schedule these services but does not own
their business logic.

## Streaming event flow

```mermaid
sequenceDiagram
  participant Replay as Deterministic replay
  participant Broker as Redpanda (optional)
  participant Worker as Idempotent worker
  participant DB as PostgreSQL
  Replay->>Broker: versioned price-bar envelope
  Broker->>Worker: at-least-once delivery
  Worker->>Worker: validate, classify duplicate / late / invalid
  alt accepted and new
    Worker->>DB: durable price + processing identity
    Worker->>DB: controlled recompute request
    DB-->>Worker: commit
    Worker-->>Broker: commit offset
  else duplicate
    Worker-->>Broker: metric + safe offset commit
  else permanently invalid
    Worker->>Broker: safe DLQ envelope
    Worker-->>Broker: commit source offset after DLQ acknowledgement
  end
```

Possible duplicate publication is part of the design. The live broker path must not be described as
verified until the Redpanda integration gates in `docs/progress.md` pass.

## Risk computation and evidence flow

```mermaid
flowchart LR
  Portfolio["Portfolio version + positions"] --> Align["Price/calendar alignment"]
  Prices["Validated price lineage"] --> Align
  Align --> Engine["Pure risk engine"]
  Method["Methodology + configuration versions"] --> Engine
  Engine --> Snapshot["Immutable risk snapshot"]
  Snapshot --> Evidence["Content-addressed evidence manifest"]
  Evidence --> API["REST / read-only MCP"]
  Evidence --> Brief["Validated grounded brief"]
```

## ML training, promotion, and monitoring flow

```mermaid
flowchart LR
  Data["Canonical synthetic bars"] --> PIT["Point-in-time features"]
  PIT --> Split["Chronological train / validation / test"]
  Split --> Baseline["Rule baseline v1"]
  Split --> Candidate["Fixed-seed K-Means candidates"]
  Candidate --> Select["Median validation policy"]
  Baseline --> Gates{"Promotion gates"}
  Select --> Gates
  Gates -->|"all pass"| Active["Candidate active"]
  Gates -->|"any fail"| Fallback["Baseline remains active"]
  Active --> Drift["PSI / missingness / JSD monitoring"]
  Fallback --> Drift
```

The current candidate is rejected and the baseline remains active. This classification describes a
risk state; it is not a price or return forecast.
