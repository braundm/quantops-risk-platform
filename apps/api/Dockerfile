FROM python:3.12.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY packages/data_contracts/pyproject.toml /build/data_contracts/pyproject.toml
COPY packages/data_contracts/README.md /build/data_contracts/README.md
COPY packages/data_contracts/src /build/data_contracts/src
RUN python -m pip wheel --wheel-dir /wheels /build/data_contracts

COPY packages/domain/pyproject.toml /build/domain/pyproject.toml
COPY packages/domain/quantops_domain /build/domain/quantops_domain
RUN python -m pip wheel --wheel-dir /wheels /build/domain

COPY packages/risk_engine/pyproject.toml /build/risk_engine/pyproject.toml
COPY packages/risk_engine/README.md /build/risk_engine/README.md
COPY packages/risk_engine/src /build/risk_engine/src
RUN python -m pip wheel --find-links /wheels --wheel-dir /wheels /build/risk_engine

COPY packages/ai_engine/pyproject.toml /build/ai_engine/pyproject.toml
COPY packages/ai_engine/README.md /build/ai_engine/README.md
COPY packages/ai_engine/src /build/ai_engine/src
COPY packages/ai_engine/evals /build/ai_engine/evals
RUN python -m pip wheel --find-links /wheels --wheel-dir /wheels /build/ai_engine

COPY apps/api/pyproject.toml /build/api/pyproject.toml
COPY apps/api/quantops_api /build/api/quantops_api
RUN python -m pip wheel --find-links /wheels --wheel-dir /wheels /build/api

FROM python:3.12.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv /opt/venv \
    && addgroup --system quantops \
    && adduser --system --ingroup quantops --home /app quantops
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels
WORKDIR /app
USER quantops
EXPOSE 8000
CMD ["uvicorn", "quantops_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
