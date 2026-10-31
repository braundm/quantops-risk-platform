"""Exercise the actual portfolio-to-forward boundary without external services."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from quantops_api.main import create_app
from quantops_api.settings import Settings

D = Decimal
PATH = "/api/v1/retail"
HEADER = "account,symbol,asset_class,currency,quantity,price,multiplier,as_of,source\n"
ROW = "Mine,OWN,equity,USD,100,100,1,2026-01-02T16:00:00Z,user\n"


def demo(client: TestClient) -> dict[str, Any]:
    response = client.get(f"{PATH}/demo")
    assert response.status_code == 200
    return response.json()  # type: ignore[no-any-return]


def test_combined_shock_reconciles_and_forward_preserves_asset_risk() -> None:
    with TestClient(create_app()) as client:
        portfolio = demo(client)
        response = client.post(
            f"{PATH}/analyze",
            json={
                "portfolio": portfolio,
                "asset_shock": "-0.2",
                "fx_shock": "-0.1",
                "base_rate": "0",
                "foreign_rate": "0",
                "entry_bps": "0",
            },
        )
    assert response.status_code == 200
    result = response.json()
    assert result["source"] == "synthetic"
    assert D(result["net_value"]) == 81500
    # USD: 40000*(.8*.9-1) = -11200; EUR -4300; PLN -2000; cash unchanged.
    assert D(result["unhedged_impact"]) == -17500
    assert sum((D(p["impact"]) for p in result["positions"]), D(0)) == -17500
    assert D(result["hedges"][2]["payoff"]) == 4000
    assert D(result["hedges"][2]["portfolio_impact"]) == -13500
    assert result["hedges"][2]["overhedged_after_shock"] is True
    assert result["historical_risk_status"] == "insufficient_data"
    assert "stale_prices" in result["warnings"]


@pytest.mark.parametrize("holdings", ["empty", "cash", "short", "no-usd"])
def test_empty_cash_short_and_absent_currency_are_honestly_supported(holdings: str) -> None:
    with TestClient(create_app()) as client:
        portfolio = demo(client)
        if holdings == "empty":
            portfolio["positions"] = []
        elif holdings == "cash":
            portfolio["positions"] = portfolio["positions"][-1:]
        elif holdings == "no-usd":
            portfolio["positions"] = portfolio["positions"][1:]
        else:
            portfolio["positions"] = portfolio["positions"][:1]
            portfolio["positions"][0]["quantity"] = "-100"
        response = client.post(
            f"{PATH}/analyze",
            json={
                "portfolio": portfolio,
                "base_rate": "0",
                "foreign_rate": "0",
                "entry_bps": "0",
            },
        )
    assert response.status_code == 200
    result = response.json()
    if holdings == "short":
        assert D(result["unhedged_impact"]) == 4000
        assert D(result["hedges"][2]["payoff"]) == -4000
        assert D(result["hedges"][2]["portfolio_impact"]) == 0
        assert result["impact_fraction"] is None
        assert result["gross_to_equity"] is None
    else:
        assert D(result["unhedged_impact"]) == 0
        assert all(D(h["base_notional"]) == 0 for h in result["hedges"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", "NaN"),
        ("price", "-1"),
        ("quantity", "0"),
        ("currency", "ZZZ"),
        ("multiplier", "100"),
        ("asset_class", "option"),
        ("as_of", "2026-01-02T16:00:00"),
        ("as_of", "2099-01-01T00:00:00Z"),
    ],
)
def test_bad_positions_return_problem_details(field: str, value: str) -> None:
    with TestClient(create_app()) as client:
        portfolio = demo(client)
        portfolio["positions"][0][field] = value
        response = client.post(f"{PATH}/analyze", json={"portfolio": portfolio})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "Traceback" not in response.text


@pytest.mark.parametrize("case", ["missing-fx", "base-fx", "duplicate", "duplicate-id"])
def test_inconsistent_portfolio_is_rejected(case: str) -> None:
    with TestClient(create_app()) as client:
        portfolio = demo(client)
        if case == "missing-fx":
            del portfolio["fx"]["USD"]
        elif case == "base-fx":
            portfolio["fx"]["PLN"] = "2"
        elif case == "duplicate":
            portfolio["positions"].append(portfolio["positions"][0])
        else:
            portfolio["positions"][1]["id"] = portfolio["positions"][0]["id"]
        response = client.post(f"{PATH}/analyze", json={"portfolio": portfolio})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "text,valid",
    [
        (HEADER + ROW, True),
        (HEADER + ROW + ROW, False),
        (HEADER, False),
        (HEADER + ROW.replace(",1,2026", ",100,2026"), False),
        (HEADER + ROW.replace(",USD,", ",ZZZ,"), False),
        (HEADER + ROW.replace(",100,100,", ",NaN,100,"), False),
        ("date,symbol,quantity\n2026-01-01,OWN,10", False),
        (HEADER + ROW.rstrip() + ",extra\n", False),
        (HEADER + ROW + 'Mine,"unterminated', False),
    ],
)
def test_csv_preview_is_atomic_and_does_not_create_history(text: str, valid: bool) -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"{PATH}/csv-preview", json={"text": text})
    assert response.status_code == 200
    result = response.json()
    assert result["importable"] is valid
    assert result["import_kind"] == "current_positions"
    if valid:
        assert result["positions"][0]["source"] == "user"
    else:
        assert result["errors"]


def test_requests_do_not_leak_positions_into_other_clients() -> None:
    with TestClient(create_app()) as first, TestClient(create_app()) as second:
        changed = demo(first)
        changed["positions"][0]["quantity"] = "999"
        assert first.post(f"{PATH}/analyze", json={"portfolio": changed}).status_code == 200
        assert demo(second)["positions"][0]["quantity"] == "100"


def test_retail_limit_and_synthetic_csv_provenance_are_enforced() -> None:
    with TestClient(create_app(settings=Settings(expensive_rate_limit=1))) as client:
        portfolio = demo(client)
        first = client.post(f"{PATH}/analyze", json={"portfolio": portfolio})
        second = client.post(f"{PATH}/analyze", json={"portfolio": portfolio})
        preview = client.post(
            f"{PATH}/csv-preview",
            json={
                "text": HEADER + ROW.replace(",user", ",synthetic"),
            },
        )
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"]
    assert preview.json()["positions"][0]["source"] == "synthetic"
