"""End-to-end HTTP contract tests over the deterministic application service."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from quantops_api.application.demo_service import DEMO_PORTFOLIO_ID
from quantops_api.main import create_app
from quantops_api.settings import Settings

TOKEN = "replace-with-a-local-random-token"
AUTH = {"X-Demo-Token": TOKEN}
PORTFOLIO_PATH = f"/api/v1/portfolios/{DEMO_PORTFOLIO_ID}"


def test_market_portfolio_and_risk_fixture_reconcile() -> None:
    with TestClient(create_app()) as client:
        instruments = client.get("/api/v1/instruments?limit=2")
        portfolio = client.get(PORTFOLIO_PATH)
        positions = client.get(f"{PORTFOLIO_PATH}/positions")
        risk = client.get(f"{PORTFOLIO_PATH}/risk/latest")
        snapshot = client.get(f"/api/v1/risk/snapshots/{risk.json()['id']}")
        evidence = client.get(f"/api/v1/risk/snapshots/{risk.json()['id']}/evidence")

    assert instruments.status_code == 200
    assert instruments.json()["total"] == 4
    assert len(instruments.json()["items"]) == 2
    assert instruments.json()["next_offset"] == 2
    assert portfolio.headers["ETag"] == '"1"'
    assert positions.json()["total"] == 4
    assert risk.json()["portfolio_value"] == "1503208.4501000"
    assert risk.json()["methodology_version"] == "1.0.0"
    assert risk.json()["quality_status"] == "complete"
    assert snapshot.json() == risk.json()
    assert evidence.json()["evidence_id"] == risk.json()["evidence_id"]


def test_writes_require_token_and_portfolio_etag() -> None:
    with TestClient(create_app()) as client:
        unauthenticated = client.patch(
            PORTFOLIO_PATH, headers={"If-Match": '"1"'}, json={"name": "Rejected"}
        )
        missing_precondition = client.patch(PORTFOLIO_PATH, headers=AUTH, json={"name": "Rejected"})
        updated = client.patch(
            PORTFOLIO_PATH,
            headers={**AUTH, "If-Match": '"1"'},
            json={"name": "Renamed demo"},
        )
        stale = client.patch(
            PORTFOLIO_PATH,
            headers={**AUTH, "If-Match": '"1"'},
            json={"description": "stale update"},
        )

    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["content-type"].startswith("application/problem+json")
    assert missing_precondition.status_code == 428
    assert updated.status_code == 200
    assert updated.headers["ETag"] == '"2"'
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_version"
    assert "Traceback" not in stale.text


def test_risk_recompute_is_idempotent_and_audited() -> None:
    headers = {**AUTH, "Idempotency-Key": "risk-recompute-0001"}
    with TestClient(create_app()) as client:
        missing_key = client.post(f"{PORTFOLIO_PATH}/risk/recompute", headers=AUTH, json={})
        created = client.post(
            f"{PORTFOLIO_PATH}/risk/recompute",
            headers=headers,
            json={"confidence_level": 0.975},
        )
        replay = client.post(
            f"{PORTFOLIO_PATH}/risk/recompute",
            headers=headers,
            json={"confidence_level": 0.975},
        )
        conflicting_reuse = client.post(
            f"{PORTFOLIO_PATH}/risk/recompute",
            headers=headers,
            json={"confidence_level": 0.99},
        )
        audit = client.get("/api/v1/audit-events?aggregate_type=risk_snapshot")

    assert missing_key.status_code == 400
    assert missing_key.json()["code"] == "invalid_request"
    assert created.status_code == 201
    assert created.headers["Idempotent-Replay"] == "false"
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replay"] == "true"
    assert replay.json() == created.json()
    assert conflicting_reuse.status_code == 409
    assert conflicting_reuse.json()["code"] == "conflict"
    assert audit.json()["total"] == 1


def test_create_portfolio_and_replace_positions_advance_etag_once() -> None:
    with TestClient(create_app()) as client:
        instrument_id = client.get("/api/v1/instruments?symbol=QTECH").json()["items"][0]["id"]
        created = client.post(
            "/api/v1/portfolios",
            headers=AUTH,
            json={"name": "API-created portfolio", "base_currency": "usd"},
        )
        portfolio_id = created.json()["id"]
        replaced = client.put(
            f"/api/v1/portfolios/{portfolio_id}/positions",
            headers={**AUTH, "If-Match": created.headers["ETag"]},
            json={
                "items": [
                    {
                        "instrument_id": instrument_id,
                        "quantity": "2.5",
                        "average_cost": "500",
                        "currency": "usd",
                        "tags": {"book": "test"},
                    }
                ]
            },
        )
        fetched = client.get(f"/api/v1/portfolios/{portfolio_id}")
        positions = client.get(f"/api/v1/portfolios/{portfolio_id}/positions")

    assert created.status_code == 201
    assert created.headers["ETag"] == '"1"'
    assert created.json()["version"] == 1
    assert replaced.status_code == 200
    assert replaced.headers["ETag"] == '"2"'
    assert replaced.json()["portfolio"]["version"] == 2
    assert fetched.headers["ETag"] == '"2"'
    assert positions.json()["items"][0]["quantity"] == "2.5"


def test_pagination_sorting_is_stable_and_interval_is_validated() -> None:
    with TestClient(create_app()) as client:
        first_page = client.get("/api/v1/instruments?limit=2&offset=0").json()
        second_page = client.get("/api/v1/instruments?limit=2&offset=2").json()
        repeated = client.get("/api/v1/instruments?limit=2&offset=0").json()
        instrument_id = first_page["items"][0]["id"]
        invalid_interval = client.get(f"/api/v1/instruments/{instrument_id}/prices?interval=1h")

    symbols = [item["symbol"] for item in first_page["items"] + second_page["items"]]
    assert symbols == sorted(symbols)
    assert first_page == repeated
    assert first_page["next_offset"] == 2
    assert second_page["next_offset"] is None
    assert invalid_interval.status_code == 422
    assert invalid_interval.json()["code"] == "validation_error"


def test_system_scenario_flow_and_exports() -> None:
    headers = {**AUTH, "Idempotency-Key": "scenario-run-0001"}
    with TestClient(create_app()) as client:
        scenarios = client.get("/api/v1/scenarios")
        run = client.post(f"{PORTFOLIO_PATH}/scenarios/equity_selloff_15pct/run", headers=headers)
        fetched = client.get(f"/api/v1/scenario-runs/{run.json()['id']}")
        json_report = client.get(f"/api/v1/reports/portfolios/{DEMO_PORTFOLIO_ID}.json")
        csv_report = client.get(f"/api/v1/reports/portfolios/{DEMO_PORTFOLIO_ID}.csv")

    assert scenarios.status_code == 200
    assert scenarios.json()["total"] == 5
    assert run.status_code == 201
    assert run.json()["pnl"] == "-87343.337085000"
    assert fetched.json() == run.json()
    assert json_report.json()["synthetic"] is True
    assert json_report.json()["not_investment_advice"] is True
    assert csv_report.headers["content-type"].startswith("text/csv")
    assert "QTECH" in csv_report.text


def test_validation_and_unconfigured_capabilities_are_honest() -> None:
    with TestClient(create_app()) as client:
        instrument_id = client.get("/api/v1/instruments").json()["items"][0]["id"]
        invalid_window = client.get(
            f"/api/v1/instruments/{instrument_id}/prices?start=2025-01-02&end=2025-01-01"
        )
        invalid_limit = client.get("/api/v1/instruments?limit=101")
        models = client.get("/api/v1/models")
        model = client.get("/api/v1/models/not-real")
        brief = client.post(
            f"{PORTFOLIO_PATH}/risk-briefs",
            headers={**AUTH, "Idempotency-Key": "risk-brief-0001"},
            json={},
        )

    assert invalid_window.status_code == 400
    assert invalid_window.headers["content-type"].startswith("application/problem+json")
    assert invalid_limit.status_code == 422
    assert invalid_limit.json()["errors"][0]["location"][-1] == "limit"
    assert models.json()["items"] == []
    assert models.json()["status"] == "not_configured"
    assert model.status_code == 404
    assert brief.status_code == 201
    assert brief.json()["execution_mode"] == "deterministic-in-memory"
    assert brief.json()["brief"]["answer_type"] == "risk_explanation"
    assert brief.json()["validation"]["valid"] is True


def test_pipeline_quality_and_expensive_rate_limit() -> None:
    settings = Settings(expensive_rate_limit=1, expensive_rate_window_seconds=60)
    with TestClient(create_app(settings=settings)) as client:
        pipelines = client.get("/api/v1/pipelines/runs")
        quality = client.get("/api/v1/data-quality/summary")
        first = client.post(
            f"{PORTFOLIO_PATH}/risk/recompute",
            headers={**AUTH, "Idempotency-Key": "rate-limit-first"},
            json={},
        )
        limited = client.post(
            f"{PORTFOLIO_PATH}/risk/recompute",
            headers={**AUTH, "Idempotency-Key": "rate-limit-second"},
            json={},
        )

    assert pipelines.json()["items"][0]["status"] == "succeeded"
    assert quality.json()["unresolved_issues"] == 0
    assert quality.json()["intentional_fixture_issues"] == 1
    assert first.status_code == 201
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) >= 1
    assert UUID(limited.headers["X-Request-ID"])
