"""Dated price/FX histories through the existing public reference-price adapter."""

from datetime import UTC, date, datetime
from decimal import Decimal
from urllib.parse import quote

from quantops_api.application.portfolio_risk import RiskHistory, RiskPrice
from quantops_api.application.stock_quotes import fetch_adjusted_history
from quantops_api.application.xtb_quotes import mapped_stock

FX_CURRENCIES = {"USD", "PLN", "EUR", "GBP", "CHF"}


def fetch_risk_histories(
    symbols: list[str], base: str, start: date, end: date
) -> tuple[list[RiskHistory], dict[str, str]]:
    """Keep successful instrument histories and disclose each failed input explicitly.

    Cross rates use the same USD reference legs. No weekend/session gap is filled.
    Failure does not turn a partial sample into portfolio-wide risk.
    """
    cache: dict[str, dict[date, Decimal]] = {}

    def usd_rate(currency: str) -> dict[date, Decimal]:
        if currency not in FX_CURRENCIES:
            raise ValueError("Unsupported FX reference currency")
        if currency not in cache:
            identifier = f"{currency}=X"
            rows, _, _ = fetch_adjusted_history(identifier, currency, start, end)
            cache[currency] = {day: close for day, close, _ in rows}
        return cache[currency]

    histories: list[RiskHistory] = []
    failures: dict[str, str] = {}
    for symbol in symbols:
        try:
            is_cash = symbol.startswith("CASH:")
            if is_cash:
                currency = symbol.removeprefix("CASH:")
                if currency == base:
                    continue
                reference = currency if currency != "USD" else base
                usd_rate(reference)
                raw_rows = [(day, Decimal(1), Decimal(1)) for day in sorted(cache[reference])]
                # Timestamp is the actual retrieval time even for cash's constant unit price.
                fetched = datetime.now(UTC)
                splits: list[date] = []
                source_url = (
                    f"https://finance.yahoo.com/quote/{quote(reference + '=X', safe='')}/history/"
                )
            else:
                stock = mapped_stock(symbol)
                currency = stock.currency
                raw_rows, fetched, splits = fetch_adjusted_history(
                    stock.symbol, currency, start, end
                )
                source_url = (
                    f"https://finance.yahoo.com/quote/{quote(stock.symbol, safe='')}/history/"
                )
            if currency != base:
                from_usd = usd_rate(base) if base != "USD" else None
                to_usd = usd_rate(currency) if currency != "USD" else None
            else:
                from_usd = to_usd = None
            rows: list[RiskPrice] = []
            for day, close, adjusted in raw_rows:
                if (from_usd is not None and day not in from_usd) or (
                    to_usd is not None and day not in to_usd
                ):
                    continue
                rate = (from_usd[day] if from_usd else Decimal(1)) / (
                    to_usd[day] if to_usd else Decimal(1)
                )
                rate = rate.quantize(Decimal("0.000000000001"))
                rows.append(
                    RiskPrice(date=day, close=close, adjusted_close=adjusted, fx_to_base=rate)
                )
            histories.append(
                RiskHistory(
                    symbol=symbol,
                    currency=currency,
                    base_currency=base,
                    source="Yahoo Finance daily reference",
                    source_url=source_url,
                    fx_source="Yahoo Finance USD cross legs: "
                    + " | ".join(
                        f"https://finance.yahoo.com/quote/{quote(c + '=X', safe='')}/history/"
                        for c in (currency, base)
                        if c != "USD"
                    )
                    if currency != base
                    else "same currency identity",
                    fetched_at=fetched,
                    origin="provider",
                    rows=rows,
                    split_dates=splits,
                )
            )
        except Exception:
            failures[symbol] = (
                "Adjusted price or dated FX unavailable; previous input is retained in the UI"
            )
    return histories, failures
