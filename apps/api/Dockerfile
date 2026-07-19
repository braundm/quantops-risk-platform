FROM python:3.12.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/quantops_api ./quantops_api
RUN python -m pip wheel --wheel-dir /wheels .

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
