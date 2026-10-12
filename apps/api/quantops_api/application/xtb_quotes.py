"""Public quote mapping for imported physical instruments; never quote CFDs as owned shares."""

import re
from datetime import date
from functools import lru_cache

from quantops_api.application.broker_catalog import CatalogInstrument, load_catalog
from quantops_api.application.stock_catalog import Stock
from quantops_api.application.stock_quotes import StockQuote, fetch_reference_quote

SUFFIXES = {
    "US": "",
    "PL": ".WA",
    "DE": ".DE",
    "FR": ".PA",
    "NL": ".AS",
    "ES": ".MC",
    "IT": ".MI",
    "BE": ".BR",
    "CH": ".SW",
    "PT": ".LS",
}


@lru_cache(maxsize=1)
def physical_catalog() -> dict[str, CatalogInstrument]:
    return {
        row.symbol: row
        for row in load_catalog().instruments
        if row.broker == "xtb" and row.instrument_type in ("equity", "etf", "etc", "etn")
    }


def mapped_stock(symbol: str) -> Stock:
    instrument = physical_catalog().get(symbol)
    if instrument is None or instrument.currency is None:
        raise ValueError("No verified physical instrument/currency mapping for this XTB symbol")
    if not re.fullmatch(r"[A-Z0-9-]{1,20}\.[A-Z]{2}", symbol):
        raise ValueError("Unsupported public provider identifier")
    ticker, suffix = symbol.rsplit(".", 1)
    if suffix not in SUFFIXES:
        raise ValueError("This listing market requires a reviewed quote mapping")
    provider_symbol = ticker + SUFFIXES[suffix]
    return Stock(
        symbol=provider_symbol,
        name=instrument.name,
        market=instrument.market,
        currency=instrument.currency,
    )


def fetch_xtb_quote(symbol: str, purchased: date) -> StockQuote:
    return fetch_reference_quote(mapped_stock(symbol), purchased)
