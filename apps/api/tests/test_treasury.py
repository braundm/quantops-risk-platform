"""Stateless Treasury boundary, quality gating and safe HTML export."""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from quantops_api.main import create_app


def synthetic_request() -> dict[str, Any]:
    return {
        "currency": "USD",
        "valuation_date": "2026-10-02",
        "origin": "synthetic",
        "source_note": "Synthetic test case; invented inputs.",
        "bonds": [
            {
                "id": str(uuid4()),
                "name": "Synthetic bond",
                "face": "1000",
                "quantity": "100",
                "coupon_rate": "0.04",
                "yield_rate": "0.04",
                "years": 5,
                "frequency": 2,
            }
        ],
        "liquidity_positions": [
            {
                "id": str(uuid4()),
                "name": "Synthetic equity",
                "quantity": "8000",
                "reference_price": "25",
                "price_date": "2026-10-02",
                "sessions": [
                    {"date": (date(2026, 9, 7) + timedelta(days=i)).isoformat(), "volume": "10000"}
                    for i in range(20)
                ],
            }
        ],
        "participation": "0.1",
        "max_abs_dv01": "40",
        "max_liquidation_days": 5,
    }


def test_analysis_reconciles_and_limits_use_signed_dv01() -> None:
    payload = synthetic_request()
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/treasury/analyze", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert Decimal(result["net_value"]) == Decimal(100000)
        assert result["dv01_limit_status"] == "BREACH"
        # Latest volume is six calendar days old and inside the disclosed threshold.
        assert result["liquidity"][0]["status"] == "valid"
        assert result["liquidity"][0]["estimate"]["days"] == 8
        assert Decimal(result["liquidatable_one_day_pct"]) == Decimal("12.5")
        for scenario in result["scenarios"]:
            assert Decimal(scenario["after"]) - Decimal(scenario["before"]) == Decimal(
                scenario["pnl"]
            )
            assert sum(map(Decimal, scenario["pnl_by_position"].values())) == Decimal(
                scenario["pnl"]
            )
        offset = deepcopy(payload["bonds"][0])
        offset.update(id=str(uuid4()), quantity="-100")
        payload["bonds"].append(offset)
        result = client.post("/api/v1/treasury/analyze", json=payload).json()
        assert Decimal(result["signed_dv01"]) == 0
        assert Decimal(result["gross_dv01"]) > 0
        assert result["dv01_limit_status"] == "OK"
        assert all(Decimal(s["pnl"]) == 0 for s in result["scenarios"])


@pytest.mark.parametrize("mode", ["missing", "stale_volume", "stale_price", "zero"])
def test_unusable_history_withholds_whole_book_liquidation(mode: str) -> None:
    payload = synthetic_request()
    position = payload["liquidity_positions"][0]
    if mode == "missing":
        position["sessions"] = []
    elif mode == "stale_volume":
        for session in position["sessions"]:
            session["date"] = (date.fromisoformat(session["date"]) - timedelta(days=10)).isoformat()
    elif mode == "stale_price":
        position["price_date"] = "2026-09-01"
    else:
        for session in position["sessions"]:
            session["volume"] = "0"
    with TestClient(create_app()) as client:
        result = client.post("/api/v1/treasury/analyze", json=payload).json()
    assert result["liquidatable_one_day_pct"] is None
    assert result["liquidatable_five_days_pct"] is None
    assert result["liquidity"][0]["limit_status"] == "INSUFFICIENT"


@pytest.mark.parametrize(
    "mode", ["duplicate", "future", "unordered", "nan", "currency", "zero_quantity"]
)
def test_bad_inputs_return_problem_details(mode: str) -> None:
    payload = synthetic_request()
    sessions = payload["liquidity_positions"][0]["sessions"]
    if mode == "duplicate":
        sessions.append(sessions[-1])
    elif mode == "future":
        sessions[-1]["date"] = "2099-01-01"
    elif mode == "unordered":
        sessions.reverse()
    elif mode == "nan":
        payload["bonds"][0]["yield_rate"] = "NaN"
    elif mode == "currency":
        payload["currency"] = "ZZZ"
    else:
        payload["bonds"][0]["quantity"] = "0"
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/treasury/analyze", json=payload)
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


def test_html_report_escapes_inputs_and_contains_reproduction_evidence() -> None:
    payload = synthetic_request()
    payload["bonds"][0]["name"] = "<script>alert('x')</script>"
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/treasury/report", json=payload)
    assert response.status_code == 200
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text
    assert "SYNTHETIC · UNVERIFIED INPUTS" in response.text
    assert "Reproduction inputs" in response.text
    assert "treasury@1.0.0" in response.text
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
