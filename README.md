# QuantOps

**Market Risk, Data, and Grounded AI Research Platform**

QuantOps is a production-style portfolio project for ingesting deterministic synthetic market data, computing reproducible portfolio risk, inspecting lineage and quality, and generating evidence-grounded risk explanations through bounded read-only tools.

> **Current status:** the deterministic domain, risk, synthetic-data, event-contract, application-API, and frontend research flows are implemented and tested. The browser UI currently uses a typed local adapter, while the API uses a process-local deterministic service. PostgreSQL, streaming, scheduling, ML/AI API integration, and clean-room infrastructure evidence remain in progress and are not claimed. See [implementation progress](docs/progress.md).

## Product boundary

QuantOps is a research, engineering, and risk-observability platform. It does not connect to brokerage accounts, execute orders, promise returns, predict guaranteed price directions, or provide buy/sell recommendations. Required demo data and documents are fictional and visibly labeled synthetic.

## Architecture

The synchronous product is a modular FastAPI monolith backed by PostgreSQL. Framework-free domain and risk packages sit behind application services. Redpanda replay, Airflow wrappers, MLflow, the grounded AI workflow, MCP, and observability are separate optional boundaries so the core demo can degrade safely. See the [architecture overview](docs/architecture/overview.md).

## Prerequisites

- Python 3.12–3.14 and [uv](https://docs.astral.sh/uv/)
- Node 22.12+ and pnpm 11
- Git
- Docker Compose for PostgreSQL and the full local demo

Run `python scripts/doctor.py` (or `powershell -File scripts/dev.ps1 doctor`) for actionable diagnostics.

## Local quickstart

```bash
uv sync --all-packages
pnpm install --frozen-lockfile
uv run pytest apps/api/tests
pnpm --filter @quantops/web test
pnpm --filter @quantops/web build
uv run uvicorn quantops_api.main:app --app-dir apps/api --reload
```

Then open API docs at `http://localhost:8000/docs`. The deterministic research UI runs with `pnpm --filter @quantops/web dev` at `http://localhost:5173`. Its current adapter is deliberately local and typed; it does not imply that PostgreSQL or an external provider is connected.

## Quality commands

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy apps packages pipelines ml
uv run pytest
pnpm lint
pnpm typecheck
pnpm test
pnpm build
uv run python scripts/docs_check.py
```

Docker, streaming, model, AI, MCP, performance, and clean-room results will be documented only after they have actually run.

## License

MIT. Author details remain an owner-review item before publication.
