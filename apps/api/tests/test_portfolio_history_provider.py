from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from quantops_api.application.portfolio_history_provider import fetch_risk_histories
from quantops_api.application.stock_quotes import fetch_adjusted_history


def test_cross_fx_uses_shared_usd_legs_and_retains_only_observed_dates() -> None:
    days = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
    calls: list[str] = []

    def fetch(
        symbol: str, currency: str, start: date, end: date
    ) -> tuple[list[tuple[date, Decimal, Decimal]], datetime, list[date]]:
        calls.append(symbol)
        values = {"AAPL": "100", "EUR=X": "0.9", "PLN=X": "4.2"}
        selected = days[1:] if symbol == "EUR=X" else days
        return (
            [(day, Decimal(values[symbol]), Decimal(values[symbol])) for day in selected],
            datetime(2024, 1, 5, tzinfo=UTC),
            [],
        )

    with patch(
        "quantops_api.application.portfolio_history_provider.fetch_adjusted_history",
        side_effect=fetch,
    ):
        histories, failures = fetch_risk_histories(
            ["AAPL.US", "CASH:PLN"], "EUR", days[0], days[-1]
        )
    assert not failures
    assert len(histories[0].rows) == 2
    assert histories[0].rows[0].fx_to_base == Decimal("0.9")
    assert histories[1].rows[0].fx_to_base == Decimal("0.214285714286")
    assert calls.count("EUR=X") == 1
    assert calls.count("PLN=X") == 1


def test_adjusted_adapter_retains_raw_close_and_split_dates_without_gap_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload: dict[str, Any] = {
        "chart": {
            "result": [
                {
                    "meta": {"currency": "USD", "symbol": "AAPL"},
                    "timestamp": [1704153600, 1704240000, 1704326400],
                    "indicators": {
                        "quote": [{"close": [100, 50, 50]}],
                        "adjclose": [{"adjclose": [50, None, 50]}],
                    },
                    "events": {"splits": {"split": {"date": 1704240000}}},
                }
            ]
        }
    }
    original_client = httpx.Client

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "query1.finance.yahoo.com"
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(handle)),
    )
    rows, _, splits = fetch_adjusted_history("AAPL", "USD", date(2024, 1, 1), date(2024, 1, 5))
    assert rows == [
        (date(2024, 1, 2), Decimal(100), Decimal(50)),
        (date(2024, 1, 4), Decimal(50), Decimal(50)),
    ]
    assert splits == [date(2024, 1, 3)]
    payload["chart"]["result"][0]["meta"]["currency"] = "GBp"
    with pytest.raises(ValueError, match="currency"):
        fetch_adjusted_history("AAPL", "USD", date(2024, 1, 1), date(2024, 1, 5))
