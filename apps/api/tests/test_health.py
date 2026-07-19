"""Smoke tests for the initial HTTP contract."""

from fastapi.testclient import TestClient
from quantops_api.main import create_app


def test_health_contract() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "quantops-api",
        "version": "0.1.0",
    }


def test_version_identifies_methodology() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/version")

    assert response.status_code == 200
    assert response.json() == {
        "name": "QuantOps",
        "version": "0.1.0",
        "methodology_version": "0.1.0",
    }


def test_openapi_contains_only_versioned_operational_routes() -> None:
    with TestClient(create_app()) as client:
        schema = client.get("/openapi.json").json()

    assert set(schema["paths"]) == {
        "/api/v1/health",
        "/api/v1/ready",
        "/api/v1/version",
    }
