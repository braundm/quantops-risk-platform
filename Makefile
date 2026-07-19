.PHONY: doctor setup up migrate seed demo replay test test-unit test-integration test-contract test-e2e test-performance lint format typecheck security ml-train-demo ml-evaluate ai-evaluate docs-check down clean

doctor:
	python scripts/doctor.py

setup:
	uv sync --all-packages
	pnpm install --frozen-lockfile

up:
	docker compose up --build -d

migrate:
	uv run alembic -c apps/api/alembic.ini upgrade head

seed:
	uv run python -m quantops_pipelines.cli generate-demo-dataset
	uv run python -m quantops_pipelines.cli seed-demo

demo: up migrate seed
	@echo "Web: http://localhost:5173  API: http://localhost:8000  Docs: http://localhost:8000/docs"

replay:
	uv run python -m quantops_stream_worker.cli replay --scenario volatility-shock --speed 50

test: test-unit test-contract

test-unit:
	uv run pytest -m "not integration and not e2e"

test-integration:
	uv run pytest -m integration

test-contract:
	uv run pytest -m contract

test-e2e:
	pnpm --filter @quantops/web test:e2e

test-performance:
	uv run pytest tests/performance

lint:
	uv run ruff check .
	pnpm lint

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy apps packages pipelines ml
	pnpm typecheck

security:
	uv run pip-audit
	pnpm audit --prod

ml-train-demo:
	uv run python -m ml.training.train --config ml/configs/demo.yaml

ml-evaluate:
	uv run python -m ml.evaluation.evaluate --config ml/configs/demo.yaml

ai-evaluate:
	uv run python -m quantops_ai.evaluation

docs-check:
	uv run python scripts/docs_check.py

down:
	docker compose down

clean:
	uv run python scripts/clean.py
