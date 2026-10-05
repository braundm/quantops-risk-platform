FROM python:3.12.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy

RUN python -m pip install uv==0.11.29
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps ./apps
COPY packages ./packages
COPY pipelines ./pipelines
COPY ml ./ml
# Install the API closure once from the audited lock, independent of the source tree.
RUN uv sync --locked --package quantops-api --no-dev --no-editable --python /usr/local/bin/python

FROM python:3.12.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN addgroup --system quantops \
    && adduser --system --ingroup quantops --home /app quantops
COPY --from=builder /app/.venv /app/.venv
WORKDIR /app
USER quantops
EXPOSE 8000
CMD ["uvicorn", "quantops_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
