# Architecture overview

QuantOps uses a modular monolith for synchronous workflows and narrowly scoped workers for asynchronous replay, outbox publication, and scheduled pipelines.

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
