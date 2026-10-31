"""Offline stock onboarding, provider-boundary and native-currency accounting invariants."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from quantops_api.api import stocks
from quantops_api.application import stock_quotes
from quantops_api.application.stock_catalog import BY_SYMBOL, STOCKS
from quantops_api.application.stock_quotes import StockQuote
from quantops_api.main import create_app


def synthetic_quote(symbol: str = "AAPL") -> StockQuote:
    """Synthetic test prices, never a market fixture or production response."""
    return StockQuote(
        stock=BY_SYMBOL[symbol],
        requested_date=date(2025, 4, 5),
        purchase_reference_date=date(2025, 4, 4),
        purchase_reference_close=Decimal(100),
        latest_date=date(2026, 10, 1),
        latest_close=Decimal(120),
        fetched_at=datetime(2026, 10, 2, tzinfo=UTC),
        source_url=f"https://finance.yahoo.com/quote/{symbol}/history/",
        provider="Synthetic test fixture",
        warnings=["previous_session_reference"],
    )


def position(symbol: str = "AAPL") -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "symbol": symbol,
        "quantity": "2",
        "purchased": "2025-04-05",
        "purchase_price": "90",
        "price_basis": "actual",
        "quote": synthetic_quote(symbol).model_dump(mode="json"),
    }


def test_catalog_has_twenty_us_and_twenty_polish_stocks_only() -> None:
    assert len(STOCKS) == len(BY_SYMBOL) == 40
    assert sum(s.market == "US" and s.currency == "USD" for s in STOCKS) == 20
    assert sum(s.market == "PL" and s.currency == "PLN" for s in STOCKS) == 20
    with TestClient(create_app()) as client:
        assert len(client.get("/api/v1/stocks/catalog").json()) == 40
        for symbol in ("EURUSD=X", "SPY", "http://localhost/", "UNKNOWN"):
            assert (
                client.post(
                    "/api/v1/stocks/quote",
                    json={
                        "symbol": symbol,
                        "purchased": "2025-04-05",
                    },
                ).status_code
                == 422
            )


def test_profile_tailors_learning_and_flags_capacity_without_recommending_stocks() -> None:
    answers = dict(
        goal="Understand owned stocks",
        horizon_months=6,
        willingness_pct=30,
        capacity_pct=10,
        needs_cash_soon=True,
        stocks="none",
        bonds="none",
        etfs="basic",
        options="experienced",
        futures="none",
        knows_loss=False,
        knows_diversification=False,
        knows_leverage=False,
    )
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/stocks/profile", json=answers)
        assert response.status_code == 200
        result = response.json()
        assert result["learning_level"] == "introductory"
        assert set(result["flags"]) == {
            "willingness_exceeds_capacity",
            "short_horizon_or_liquidity_need",
        }
        assert "options" in result["deferred_instruments"]
        assert not any(s.symbol in response.text for s in STOCKS)
        assert (
            client.post(
                "/api/v1/stocks/profile",
                json={
                    **answers,
                    "capacity_pct": 101,
                },
            ).status_code
            == 422
        )


def test_values_do_not_sum_usd_and_pln_and_do_not_invent_missing_costs() -> None:
    apple, pko = position(), position("PKO.WA")
    with TestClient(create_app()) as client:
        result = client.post("/api/v1/stocks/value", json={"positions": [apple, pko]}).json()
        assert len(result["totals"]) == 2
        for total in result["totals"]:
            assert Decimal(total["value"]) == 240
            assert Decimal(total["cost"]) == 180
            assert Decimal(total["unrealized_change"]) == 60
        apple["purchase_price"], apple["price_basis"] = None, "unknown"
        result = client.post("/api/v1/stocks/value", json={"positions": [apple]}).json()
        assert result["totals"][0]["cost"] is None
        apple["purchase_price"], apple["price_basis"] = "100", "reference"
        apple["quote"]["corporate_action_review"] = True
        result = client.post("/api/v1/stocks/value", json={"positions": [apple]}).json()
        assert result["totals"][0]["unrealized_change"] is None
        assert result["positions"][0]["mark"]["status"] == "corporate_action_review"


@pytest.mark.parametrize("case", ["currency", "date", "duplicate", "nan", "source"])
def test_local_marks_reject_mismatched_or_invalid_inputs(case: str) -> None:
    row = position()
    if case == "currency":
        row["quote"]["stock"]["currency"] = "PLN"
    elif case == "date":
        row["quote"]["latest_date"] = "2099-01-01"
    elif case == "nan":
        row["quantity"] = "NaN"
    elif case == "source":
        row["quote"]["source_url"] = "javascript:alert(1)"
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/stocks/value",
            json={
                "positions": [row, row] if case == "duplicate" else [row],
            },
        )
        assert response.status_code == 422


def test_provider_failure_has_no_fabricated_replacement(monkeypatch: pytest.MonkeyPatch) -> None:
    def failure(*_: object) -> StockQuote:
        raise ValueError("Missing market data")

    monkeypatch.setattr(stocks, "fetch_stock_quote", failure)
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/stocks/quote",
            json={
                "symbol": "AAPL",
                "purchased": "2025-04-05",
            },
        )
        assert response.status_code == 503
        assert response.headers["content-type"].startswith("application/problem+json")


def test_provider_parses_previous_session_and_validates_currency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload: dict[str, Any] = {
        "chart": {
            "result": [
                {
                    "meta": {"currency": "USD"},
                    "timestamp": [1743724800, 1790812800],
                    "indicators": {"quote": [{"close": [100, 120]}]},
                }
            ]
        }
    }
    calls: list[str] = []
    original_client = httpx.Client

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            **kwargs,
            transport=httpx.MockTransport(handle),
        ),
    )
    result = stock_quotes.fetch_stock_quote("AAPL", date(2025, 4, 5))
    assert result.purchase_reference_date == date(2025, 4, 4)
    assert "previous_session_reference" in result.warnings
    assert all(
        url.startswith("https://query1.finance.yahoo.com/v8/finance/chart/AAPL?") for url in calls
    )
    payload["chart"]["result"][0]["meta"]["currency"] = "EUR"
    with pytest.raises(ValueError, match="currency"):
        stock_quotes.fetch_stock_quote("AAPL", date(2025, 4, 5))
