"""Contract tests for operational endpoints and the published route surface."""

import json
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from quantops_api.main import create_app


def test_health_and_readiness_contracts_include_request_identity() -> None:
    request_id = "7acb6fd2-7134-4bb2-bfdb-a2334f2d72b2"
    correlation_id = "152600bf-9111-4537-ab8b-4acebd89af20"
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": request_id, "X-Correlation-ID": correlation_id},
        )
        readiness = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "quantops-api",
        "version": "0.1.0",
    }
    assert response.headers["X-Request-ID"] == request_id
    assert response.headers["X-Correlation-ID"] == correlation_id
    assert readiness.json()["status"] == "ready"
    assert readiness.json()["checks"] == {
        "application_service": "ready",
        "database": "not_configured",
    }


def test_version_identifies_risk_methodology() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/version")

    assert response.status_code == 200
    assert response.json() == {
        "name": "QuantOps",
        "version": "0.1.0",
        "methodology_version": "1.0.0",
    }


def test_openapi_contains_the_required_versioned_routes() -> None:
    required_paths = {
        "/api/v1/health",
        "/api/v1/ready",
        "/api/v1/version",
        "/api/v1/instruments",
        "/api/v1/instruments/{instrument_id}",
        "/api/v1/instruments/{instrument_id}/prices",
        "/api/v1/portfolios",
        "/api/v1/portfolios/{portfolio_id}",
        "/api/v1/portfolios/{portfolio_id}/positions",
        "/api/v1/portfolios/{portfolio_id}/risk/latest",
        "/api/v1/portfolios/{portfolio_id}/risk/history",
        "/api/v1/portfolios/{portfolio_id}/risk/recompute",
        "/api/v1/risk/snapshots/{snapshot_id}",
        "/api/v1/risk/snapshots/{snapshot_id}/evidence",
        "/api/v1/scenarios",
        "/api/v1/portfolios/{portfolio_id}/scenarios/{scenario_id}/run",
        "/api/v1/scenario-runs/{scenario_run_id}",
        "/api/v1/pipelines/runs",
        "/api/v1/pipelines/runs/{run_id}",
        "/api/v1/data-quality/issues",
        "/api/v1/data-quality/summary",
        "/api/v1/models",
        "/api/v1/models/{model_id}",
        "/api/v1/models/{model_id}/evaluations",
        "/api/v1/models/{model_id}/drift",
        "/api/v1/portfolios/{portfolio_id}/risk-briefs",
        "/api/v1/risk-briefs/{brief_id}",
        "/api/v1/ai/evaluations/run",
        "/api/v1/audit-events",
        "/api/v1/reports/portfolios/{portfolio_id}.json",
        "/api/v1/reports/portfolios/{portfolio_id}.csv",
    }
    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert set(schema["paths"]) == required_paths
    assert "ProblemDetails" in schema["components"]["schemas"]
    assert all(
        UUID(value)
        for value in (response.headers["X-Request-ID"], response.headers["X-Correlation-ID"])
    )


def test_checked_in_openapi_snapshot_matches_application() -> None:
    snapshot = json.loads(
        (Path(__file__).parents[1] / "openapi.generated.json").read_text(encoding="utf-8")
    )

    assert snapshot == create_app().openapi()


def test_invalid_request_ids_are_replaced_and_demo_token_is_never_disclosed() -> None:
    configured_token = "replace-with-a-local-random-token"
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5173",
                "X-Request-ID": "not-a-uuid",
                "X-Correlation-ID": "also-not-a-uuid",
            },
        )
        preflight = client.options(
            "/api/v1/portfolios",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-QuantOps-Demo-Token,Content-Type",
            },
        )
        schema = client.get("/openapi.json")

    assert UUID(response.headers["X-Request-ID"])
    assert UUID(response.headers["X-Correlation-ID"])
    assert response.headers["X-Request-ID"] != "not-a-uuid"
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert preflight.status_code == 200
    assert "x-quantops-demo-token" in preflight.headers["access-control-allow-headers"].lower()
    assert configured_token not in response.text
    assert configured_token not in preflight.text
    assert configured_token not in schema.text
