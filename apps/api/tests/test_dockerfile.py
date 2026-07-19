"""Static guardrails for the API image when a Docker daemon is unavailable in CI."""

from pathlib import Path


def test_dockerfile_builds_workspace_wheels_and_runs_as_non_root() -> None:
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(encoding="utf-8")

    assert "AS builder" in dockerfile
    assert "AS runtime" in dockerfile
    assert "packages/data_contracts" in dockerfile
    assert "packages/domain" in dockerfile
    assert "packages/risk_engine" in dockerfile
    assert "packages/ai_engine" in dockerfile
    assert "COPY packages/ai_engine/evals" in dockerfile
    assert dockerfile.index("/build/ai_engine") < dockerfile.index("/build/api")
    assert dockerfile.count("python -m pip wheel") == 5
    assert "adduser --system" in dockerfile
    assert "USER quantops" in dockerfile
    assert "COPY --from=builder /wheels /wheels" in dockerfile
