"""Allowlisted historical close lookup with exact dates and bounded provider requests."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Self
from urllib.parse import quote

import httpx
from pydantic import Field, model_validator

from quantops_api.api.retail import Contract, Positive
from quantops_api.application.stock_catalog import BY_SYMBOL, Stock


class StockQuote(Contract):
    stock: Stock
    requested_date: date
    purchase_reference_date: date | None
    purchase_reference_close: Positive | None
    latest_date: date
    latest_close: Positive
    fetched_at: datetime
    source_url: str
    provider: str = "Yahoo Finance"
    corporate_action_review: bool = False
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_dates(self) -> Self:
        today = datetime.now(UTC).date()
        if self.fetched_at.tzinfo is None or self.fetched_at > datetime.now(UTC):
            raise ValueError("Retrieval timestamp must be timezone-aware and not future")
        if not date(1990, 1, 1) <= self.requested_date <= self.latest_date < today:
            raise ValueError("Quotes require completed historical dates")
        if (self.purchase_reference_date is None) != (self.purchase_reference_close is None):
            raise ValueError("Reference date and price must both exist or both be absent")
        if self.purchase_reference_date is not None and not (
            self.requested_date - timedelta(days=7)
            <= self.purchase_reference_date
            <= self.requested_date
        ):
            raise ValueError("Reference date is outside the disclosed purchase window")
        expected_url = (
            f"https://finance.yahoo.com/quote/{quote(self.stock.symbol, safe='')}/history/"
        )
        if self.source_url != expected_url:
            raise ValueError("Quote source URL must match the catalog symbol")
        return self


def _rows(payload: dict[str, Any], currency: str, end: date) -> list[tuple[date, Decimal]]:
    result = payload["chart"]["result"][0]
    if result["meta"]["currency"] != currency:
        raise ValueError("Provider currency differs from the catalog")
    timestamps = result.get("timestamp") or []
    closes = result["indicators"]["quote"][0].get("close") or []
    if len(timestamps) > 10000:
        raise ValueError("Provider history exceeds the observation bound")
    rows: list[tuple[date, Decimal]] = []
    for timestamp, close in zip(timestamps, closes, strict=True):
        day = datetime.fromtimestamp(timestamp, UTC).date()
        if close is None or day > end:
            continue
        value = Decimal(str(close)).quantize(Decimal("0.000001"))
        if not value.is_finite() or value <= 0:
            raise ValueError("Provider close must be finite and positive")
        rows.append((day, value))
    if not rows or [d for d, _ in rows] != sorted({d for d, _ in rows}):
        raise ValueError("Missing, duplicate or unordered provider dates")
    return rows


def fetch_stock_quote(symbol: str, purchased: date) -> StockQuote:
    """Fetch a completed daily close and a purchase-date reference; never invent missing prices."""
    return fetch_reference_quote(BY_SYMBOL[symbol], purchased)


def fetch_reference_quote(stock: Stock, purchased: date) -> StockQuote:
    """Fetch a source-mapped spot instrument; the caller owns identifier and currency validation."""
    symbol = stock.symbol
    end = datetime.now(UTC).date() - timedelta(days=1)
    if not date(1990, 1, 1) <= purchased <= end:
        raise ValueError("Purchase date must be between 1990 and the last completed day")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}"
    start = purchased - timedelta(days=7)
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        response = client.get(
            url,
            params={
                "period1": int(datetime.combine(start, datetime.min.time(), UTC).timestamp()),
                "period2": int(
                    datetime.combine(end + timedelta(days=1), datetime.min.time(), UTC).timestamp()
                ),
                "interval": "1d",
                "events": "splits",
            },
            headers={"User-Agent": "QuantOps-risk-research/1.0"},
        )
        response.raise_for_status()
        payload = response.json()
    provider_symbol = payload["chart"]["result"][0]["meta"].get("symbol")
    if provider_symbol is not None and provider_symbol != symbol:
        raise ValueError("Provider symbol differs from the requested listing")
    rows = _rows(payload, stock.currency, end)
    references = [(d, p) for d, p in rows if purchased - timedelta(days=7) <= d <= purchased]
    reference = references[-1] if references else None
    splits = payload["chart"]["result"][0].get("events", {}).get("splits", {})
    review = any(
        purchased <= datetime.fromtimestamp(event["date"], UTC).date() <= end
        for event in splits.values()
    )
    warnings = ["daily_reference_not_execution", "dividends_fees_fx_excluded"]
    if reference is None:
        warnings.append("purchase_reference_unavailable")
    elif reference[0] != purchased:
        warnings.append("previous_session_reference")
    if review:
        warnings.append("split_requires_cost_and_quantity_review")
    if (end - rows[-1][0]).days > 7:
        warnings.append("stale_provider_close")
    return StockQuote(
        stock=stock,
        requested_date=purchased,
        purchase_reference_date=reference[0] if reference else None,
        purchase_reference_close=reference[1] if reference else None,
        latest_date=rows[-1][0],
        latest_close=rows[-1][1],
        fetched_at=datetime.now(UTC),
        source_url=f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/history/",
        corporate_action_review=review,
        warnings=warnings,
    )
