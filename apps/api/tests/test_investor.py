"""Provider provenance, schema guards, CSV idempotency and offline demo contract."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from quantops_api.api.investor import Market, analyze_workspace, investor_demo
from quantops_api.main import create_app


def test_sourced_prices_and_fictional_ownership_remain_separate() -> None:
    workspace = investor_demo()
    result = analyze_workspace(workspace)
    assert result.price_provenance == "provider_snapshot"
    assert result.transaction_provenance == "synthetic"
    assert result.result.observations == 252
    assert result.result.var95 is not None and result.result.var95 >= 0
    assert result.result.es95 is not None and result.result.es95 >= result.result.var95
    assert sum(p.weight for p in result.result.positions) == pytest.approx(1)
    assert sum(p.risk_contribution or 0 for p in result.result.market_points) == pytest.approx(1)
    apple = next(p for p in result.result.positions if p.symbol == "AAPL")
    assert apple.opened.isoformat() == "2025-04-01"
    assert apple.holding_days > 300
    assert result.result.gross_exposure != result.result.equity
    workspace.market.series["AAPL"].rows[-1].close += Decimal(1)
    assert analyze_workspace(workspace).price_provenance == "user_supplied"


@pytest.mark.parametrize("case", ["duplicates", "multiplier", "fx", "expiry"])
def test_market_import_rejects_unsafe_contract_changes(case: str) -> None:
    market = investor_demo().market.model_dump(mode="json")
    if case == "duplicates":
        market["series"]["AAPL"]["rows"].append(market["series"]["AAPL"]["rows"][-1])
    elif case == "multiplier":
        market["catalog"][-1]["multiplier"] = "1"
    elif case == "fx":
        market["series"]["PLN=X"]["rows"][-1]["close"] = "0"
    else:
        market["catalog"][-1]["expiry"] = "2040-01-01"
    with pytest.raises(ValidationError):
        Market.model_validate(market)


def test_csv_protects_identity_and_reports_invalid_values() -> None:
    header = "id,date,action,symbol,quantity,price,amount_pln,fee_pln,source\n"
    row = "11f05b3c-b421-4a59-9fd0-5e98c85d6195,2025-04-01,deposit,,0,0,10000,0,user\n"
    with TestClient(create_app()) as client:
        valid = client.post("/api/v1/investor/csv-preview", json={"text": header + row})
        assert valid.json()["importable"] is True
        for text in (header + row + row, header + row.replace("10000", "NaN")):
            response = client.post("/api/v1/investor/csv-preview", json={"text": text})
            assert response.json()["importable"] is False


def test_demo_analysis_route_is_finite_and_exportable_without_network() -> None:
    with TestClient(create_app()) as client:
        demo = client.get("/api/v1/investor/demo")
        assert demo.status_code == 200
        response = client.post("/api/v1/investor/analyze", json=demo.json())
        assert response.status_code == 200
        assert "NaN" not in response.text and "Infinity" not in response.text
        assert len(response.json()["result"]["positions"]) == 6
        assert len(response.json()["scenarios"]) == 2
