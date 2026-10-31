"""Static guardrails for the API image when a Docker daemon is unavailable in CI."""

from pathlib import Path


def test_dockerfile_installs_locked_production_packages_and_runs_as_non_root() -> None:
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(encoding="utf-8")

    assert "AS builder" in dockerfile
    assert "AS runtime" in dockerfile
    assert "COPY pyproject.toml uv.lock" in dockerfile
    assert "COPY packages ./packages" in dockerfile
    assert "COPY apps ./apps" in dockerfile
    install = next(line for line in dockerfile.splitlines() if line.startswith("RUN uv sync"))
    assert "--locked" in install
    assert "--package quantops-api" in install
    assert "--no-dev" in install
    assert "--no-editable" in install
    assert "adduser --system" in dockerfile
    assert "USER quantops" in dockerfile
    assert "COPY --from=builder /app/.venv /app/.venv" in dockerfile
    runtime = dockerfile.split("AS runtime", 1)[1]
    assert "pip install" not in runtime
    assert "uv sync" not in runtime
