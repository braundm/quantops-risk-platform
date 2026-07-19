# PostgreSQL data model

QuantOps uses UUID primary keys, UTC-aware timestamps, explicit `NUMERIC` precision for quantities/money, named constraints, and query-driven indexes. PostgreSQL is the durable source of truth; domain objects remain independent from SQLAlchemy.

```mermaid
erDiagram
  INSTRUMENT ||--o{ PRICE_BAR : has
  INSTRUMENT ||--o{ POSITION : referenced_by
  INSTRUMENT ||--o{ RISK_CONTRIBUTION : explains
  PORTFOLIO ||--o{ POSITION : owns
  PORTFOLIO ||--o{ RISK_SNAPSHOT : measured_by
  PORTFOLIO ||--o{ SCENARIO_RUN : stressed_by
  PORTFOLIO ||--o{ GENERATED_RISK_BRIEF : narrated_by
  PIPELINE_RUN ||--o{ PRICE_BAR : ingests
  PIPELINE_RUN ||--o{ DATA_QUALITY_ISSUE : reports
  PIPELINE_RUN ||--o{ RISK_SNAPSHOT : produces
  RISK_SNAPSHOT ||--o{ RISK_CONTRIBUTION : decomposes
  RISK_SNAPSHOT ||--o{ GENERATED_RISK_BRIEF : grounds
  SCENARIO_DEFINITION ||--o{ SCENARIO_RUN : versions
  SCENARIO_RUN o|--o{ GENERATED_RISK_BRIEF : contextualizes
  DOCUMENT ||--o{ DOCUMENT_CHUNK : contains
  MODEL_VERSION ||--o{ MODEL_EVALUATION : evaluated_by

  INSTRUMENT {
    uuid id PK
    string source
    string symbol
    string asset_class
    string quote_currency
    bool is_demo
  }
  PRICE_BAR {
    uuid id PK
    uuid instrument_id FK
    uuid pipeline_run_id FK
    timestamptz observed_at
    numeric open
    numeric high
    numeric low
    numeric close
    numeric volume
    string source_event_id
    string quality_status
  }
  PORTFOLIO {
    uuid id PK
    string base_currency
    int version
    bool is_demo
  }
  POSITION {
    uuid id PK
    uuid portfolio_id FK
    uuid instrument_id FK
    numeric quantity
    numeric average_cost
    timestamptz as_of
  }
  PIPELINE_RUN {
    uuid id PK
    string pipeline_name
    string config_hash
    string status
    timestamptz watermark_before
    timestamptz watermark_after
  }
  DATA_QUALITY_ISSUE {
    uuid id PK
    uuid pipeline_run_id FK
    string rule_code
    string severity
    string entity_reference
  }
  RISK_SNAPSHOT {
    uuid id PK
    uuid portfolio_id FK
    uuid pipeline_run_id FK
    int portfolio_version
    string methodology_version
    numeric confidence_level
    string quality_status
  }
  RISK_CONTRIBUTION {
    uuid risk_snapshot_id PK,FK
    uuid instrument_id PK,FK
    numeric market_value
    numeric volatility_contribution
    string evidence_id
  }
  SCENARIO_DEFINITION {
    uuid id PK
    string name
    int version
    jsonb shocks
  }
  SCENARIO_RUN {
    uuid id PK
    uuid portfolio_id FK
    uuid scenario_definition_id FK
    int portfolio_version
    int scenario_version
    numeric pnl_impact
  }
  DOCUMENT {
    uuid id PK
    string source_identifier
    string content_hash
    bool is_synthetic
  }
  DOCUMENT_CHUNK {
    uuid id PK
    uuid document_id FK
    int chunk_index
    vector embedding
    string evidence_id
  }
  MODEL_VERSION {
    uuid id PK
    string model_name
    string semantic_version
    string approval_status
    string mlflow_run_id
  }
  MODEL_EVALUATION {
    uuid id PK
    uuid model_version_id FK
    string evaluation_type
    string status
  }
  GENERATED_RISK_BRIEF {
    uuid id PK
    uuid portfolio_id FK
    uuid risk_snapshot_id FK
    uuid scenario_run_id FK
    string validation_status
  }
```

`MARKET_EVENT`, `AUDIT_EVENT`, and `OUTBOX_EVENT` are append-oriented operational records. They carry correlation/causation identifiers without owning the aggregates they reference. The outbox row is inserted in the same transaction as business state and may be published more than once; consumers must remain idempotent.

## Important constraints

- Instrument identity is unique on `(source, symbol)` and symbols are canonical uppercase.
- Price bars are unique on `(instrument_id, interval, observed_at, source)` and `(source, source_event_id)`; OHLC, positive-price, volume, interval, and currency checks reject invalid rows.
- A position is point-in-time unique for `(portfolio_id, instrument_id, as_of)` and stores quantity/average cost as `NUMERIC(38, 12)`.
- Portfolio writes guard the stored version and raise an optimistic-concurrency error when an expected version no longer matches.
- Risk snapshots bind a portfolio version, methodology version, window, confidence, pipeline run, quality state, and evidence manifest.
- Scenario definitions and results are versioned; results are immutable application facts.
- Document chunks are unique by `(document_id, chunk_index)` and evidence ID. Vector dimensions are fixed by the schema.
- Outbox idempotency keys are unique. Status/timestamp/attempt checks prevent contradictory publication state.

## Time-series policy

The initial demo migration keeps `price_bars` as a regular table with descending instrument/time and latest-price indexes. The deterministic fixture is intentionally small, so declarative time partitioning would add migration and uniqueness complexity without improving the required demo. A production-volume migration should introduce range partitions by `observed_at`, create future partitions before cutover, and retain an idempotency constraint whose key includes the partition column or a separate global event ledger. This is a documented scaling path, not a claim that the initial table is already partitioned.

## Migration ownership

Alembic owns schema evolution. The first revision enables the `vector` extension and creates the complete application schema. Extension availability, migration upgrade, constraints, and query behavior require PostgreSQL integration verification; offline SQL compilation alone is not evidence of a successful live migration.
