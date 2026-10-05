"""Bounded public quote ingestion; prices and simulated ownership have separate provenance."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

CATALOG: list[dict[str, str]] = [
    {
        "symbol": "AAPL",
        "name": "Apple",
        "kind": "equity",
        "sector": "Technologia",
        "currency": "USD",
        "multiplier": "1",
        "margin_rate": "1",
    },
    {
        "symbol": "MSFT",
        "name": "Microsoft",
        "kind": "equity",
        "sector": "Technologia",
        "currency": "USD",
        "multiplier": "1",
        "margin_rate": "1",
    },
    {
        "symbol": "SPY",
        "name": "SPDR S&P 500 ETF",
        "kind": "etf",
        "sector": "Szeroki rynek USA",
        "currency": "USD",
        "multiplier": "1",
        "margin_rate": "1",
    },
    {
        "symbol": "TLT",
        "name": "iShares 20+ Year Treasury Bond ETF",
        "kind": "etf",
        "sector": "Obligacje skarbowe USA",
        "currency": "USD",
        "multiplier": "1",
        "margin_rate": "1",
    },
    {
        "symbol": "EURUSD=X",
        "name": "EUR/USD · model pozycji walutowej",
        "kind": "forex",
        "sector": "Waluty",
        "currency": "USD",
        "multiplier": "1",
        "margin_rate": "0.05",
    },
    {
        "symbol": "CLZ26.NYM",
        "name": "WTI Crude Oil · grudzień 2026",
        "kind": "future",
        "sector": "Energia",
        "currency": "USD",
        "multiplier": "1000",
        "margin_rate": "0.10",
        "expiry": "2026-11-20",
        "spec_url": "https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.contractSpecs.html",
    },
]
SNAPSHOT_PATH = Path(__file__).parents[1] / "data" / "market_snapshot.json"


def fetch_market_snapshot(as_of: date | None = None) -> dict[str, Any]:
    """Fetch only allowlisted daily series; never substitute fabricated prices on failure."""
    end = as_of or (datetime.now(UTC).date() - timedelta(days=1))
    start = end - timedelta(days=740)
    output: dict[str, Any] = {
        "version": 1,
        "provider": "Yahoo Finance",
        "fetched_at": datetime.now(UTC).isoformat(),
        "price_basis": "unadjusted_daily_close",
        "catalog": CATALOG,
        "series": {},
    }
    with httpx.Client(timeout=20, headers={"User-Agent": "QuantOps-local-research/1.0"}) as client:
        for symbol in [item["symbol"] for item in CATALOG] + ["PLN=X"]:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}"
            response = client.get(
                url,
                params={
                    "period1": int(datetime.combine(start, datetime.min.time(), UTC).timestamp()),
                    "period2": int(
                        datetime.combine(
                            end + timedelta(days=1), datetime.min.time(), UTC
                        ).timestamp()
                    ),
                    "interval": "1d",
                    "events": "splits",
                },
            )
            response.raise_for_status()
            result = response.json()["chart"]["result"][0]
            rows = []
            closes = result["indicators"]["quote"][0]["close"]
            for timestamp, close in zip(result["timestamp"], closes, strict=True):
                day = datetime.fromtimestamp(timestamp, UTC).date()
                if close is not None and math.isfinite(close) and close > 0 and day <= end:
                    rows.append({"date": day.isoformat(), "close": f"{close:.6f}"})
            if len(rows) < 60 or len({row["date"] for row in rows}) != len(rows):
                raise ValueError(f"Insufficient or duplicate observations: {symbol}")
            # Unadjusted units need explicit split events; reject rather than silently misprice.
            if result.get("events", {}).get("splits"):
                raise ValueError(f"Split events require explicit ledger adjustment: {symbol}")
            output["series"][symbol] = {
                "url": url,
                "history_url": f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/history/",
                "rows": rows,
            }
    output["as_of"] = min(series["rows"][-1]["date"] for series in output["series"].values())
    return output
