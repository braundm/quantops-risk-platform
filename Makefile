UV ?= uv
PNPM ?= pnpm
PYTHON := $(UV) run python
PYTEST := $(UV) run pytest -p no:cacheprovider

.PHONY: doctor setup up down migrate seed demo clean compose-check docker-build \
	test test-unit test-integration test-contract test-e2e test-performance test-openapi \
	event-test stream-test scheduler-test mcp-test ai-test ai-evaluate ml-test \
	ml-train-demo ml-evaluate web-lint web-typecheck web-test web-build \
	lint format format-check typecheck security security-scan dependency-audit docs-check

doctor:
	python scripts/doctor.py

setup:
	$(UV) sync --locked --all-packages --all-groups
	$(PNPM) install --frozen-lockfile

up:
	docker compose up --build -d

down:
	docker compose down

migrate:
	$(UV) run alembic -c apps/api/alembic.ini upgrade head

seed:
	$(PYTHON) -m quantops_pipelines generate
	$(PYTHON) -m quantops_pipelines verify --dataset data/synthetic

demo: up migrate seed
	@echo "Web: http://localhost:5173  API: http://localhost:8000  Docs: http://localhost:8000/docs"

compose-check:
	docker compose config --quiet

docker-build: compose-check
	docker build --file apps/api/Dockerfile --tag quantops-api:local .
	docker build --file apps/web/Dockerfile --tag quantops-web:local .

test: test-unit test-contract stream-test scheduler-test ai-test ml-test web-test

test-unit:
	$(PYTEST) -m "not integration and not e2e"

test-integration:
	$(PYTEST) -m integration

test-contract: event-test mcp-test

# The repository currently has deterministic Vitest UI tests, not a browser E2E harness.
test-e2e: web-test

test-performance:
	$(PYTHON) packages/risk_engine/benchmarks/benchmark_risk_engine.py

test-openapi:
	$(PYTEST) apps/api/tests/test_health.py::test_checked_in_openapi_snapshot_matches_application

event-test:
	$(PYTEST) -c packages/data_contracts/pyproject.toml packages/data_contracts/tests

stream-test:
	$(PYTEST) -c apps/stream_worker/pyproject.toml apps/stream_worker/tests

scheduler-test:
	$(PYTEST) -c apps/scheduler/pyproject.toml apps/scheduler/tests

mcp-test:
	$(PYTEST) -c apps/mcp_server/pyproject.toml apps/mcp_server/tests

ai-test:
	$(PYTEST) -c packages/ai_engine/pyproject.toml packages/ai_engine/tests

ai-evaluate:
	$(PYTHON) -m quantops_ai evaluate --output artifacts/ci/ai-evaluation-report.json

ml-test:
	$(PYTEST) -c ml/pyproject.toml ml/tests

ml-train-demo: ml-evaluate

ml-evaluate:
	$(PYTHON) -m quantops_ml run \
		--prices data/synthetic/canonical/price_bars.csv \
		--manifest data/synthetic/manifest.json \
		--output artifacts/ci/ml-demo

web-lint:
	$(PNPM) --filter @quantops/web lint

web-typecheck:
	$(PNPM) --filter @quantops/web typecheck

web-test:
	$(PNPM) --filter @quantops/web test

web-build:
	$(PNPM) --filter @quantops/web build

lint: format-check
	$(UV) run ruff check .
	$(PNPM) lint

format:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

format-check:
	$(UV) run ruff format --check .

typecheck:
	$(PYTHON) scripts/typecheck.py
	$(PNPM) typecheck

security: security-scan dependency-audit

security-scan:
	$(PYTHON) scripts/security_scan.py

dependency-audit:
	mkdir -p artifacts/ci
	$(UV) export --locked --all-packages --all-groups --no-emit-workspace \
		--format requirements.txt --output-file artifacts/ci/python-requirements.txt
	$(UV) run pip-audit --requirement artifacts/ci/python-requirements.txt \
		--require-hashes --strict
	$(UV) export --locked --all-packages --no-dev --no-emit-workspace \
		--format cyclonedx1.5 --output-file artifacts/ci/python-sbom.cdx.json
	$(PNPM) audit --prod

docs-check:
	$(PYTHON) scripts/docs_check.py

clean:
	$(PYTHON) scripts/clean.py
