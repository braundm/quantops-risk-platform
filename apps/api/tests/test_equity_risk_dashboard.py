"""Equity scope, score provenance and backward compatibility of risk reports."""

from decimal import Decimal

from fastapi.testclient import TestClient
from quantops_api.api.xtb import risk_example
from quantops_api.application.portfolio_risk import analyze_imported_risk
from quantops_api.main import create_app


def test_equity_example_has_five_scored_equities_and_documented_synthetic_sectors() -> None:
    request = risk_example("equities_only")
    report = analyze_imported_risk(request)
    assert report.status == "complete" and report.before is not None
    assert report.asset_scope == "equities_only" and report.scope == "securities_only"
    assert all(p.asset_class == "equity" for p in report.positions)
    assert len(report.positions) == 5
    assert report.before.diagnostics.score.status == "available"
    assert report.before.diagnostics.score.value is not None
    assert "unknown" not in report.before.exposures["sector"]
    assert sum(report.before.weights.values()) == 1
    assert "synthetic_history" in report.warnings
    assert request.cash == [] and not request.cash_confirmed


def test_equity_subset_discloses_the_omitted_etf_and_never_includes_its_value() -> None:
    request = risk_example().model_copy(
        update={
            "scope": "securities_only",
            "asset_scope": "equities_only",
            "cash": [],
            "cash_confirmed": False,
        }
    )
    before = request.model_dump_json()
    report = analyze_imported_risk(request)
    assert report.before is not None
    assert report.out_of_scope == {"CSPX.UK": "outside_selected_equity_scope"}
    assert set(report.before.weights) == {"AAPL.US", "MSFT.US"}
    assert report.before.value == sum(report.before.position_values.values())
    assert request.model_dump_json() == before


def test_provider_valuation_staleness_suppresses_score_even_with_long_history() -> None:
    request = risk_example("equities_only")
    for history in request.histories:
        history.origin = "user"
    report = analyze_imported_risk(request)
    assert report.before is not None
    assert report.before.diagnostics.score.status == "stale_valuation"
    assert report.before.diagnostics.score.value is None


def test_old_mixed_contract_remains_supported_but_has_no_equity_only_score() -> None:
    report = analyze_imported_risk(risk_example())
    assert report.before is not None and not report.out_of_scope
    assert "CASH:PLN" in report.before.weights and "CSPX.UK" in report.before.weights
    assert report.before.diagnostics.score.value is None
    assert report.before.diagnostics.score.status == "outside_equity_scope"


def test_equity_scope_and_diagnostic_schema_roundtrip_through_api() -> None:
    with TestClient(create_app()) as client:
        example = client.get("/api/v1/xtb/risk-example?asset_scope=equities_only")
        assert example.status_code == 200
        payload = example.json()
        response = client.post("/api/v1/xtb/risk", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["before"]["diagnostics"]["methodology"] == "equity-diagnostics@1.0.0"
        assert isinstance(body["before"]["diagnostics"]["score"]["value"], int)
        for stress in body["before"]["diagnostics"]["single_position_stress"]:
            assert Decimal(stress["value_after"]) == Decimal(body["before"]["value"]) + Decimal(
                stress["pnl"]
            )
        invalid = client.post("/api/v1/xtb/risk", json={**payload, "scope": "full_account"})
        assert invalid.status_code == 422
        assert invalid.headers["content-type"].startswith("application/problem+json")
