"""Sourced market snapshots and bounded, stateless analysis of a local transaction book."""

from __future__ import annotations

import csv
import hashlib
import io
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, ValidationError, model_validator
from quantops_risk.investor_book import (
    Action,
    BookResult,
    Entry,
    Instrument,
    Kind,
    StressResult,
    analyze_book,
    stress_book,
)

from quantops_api.api.dependencies import require_expensive_capacity
from quantops_api.api.retail import Amount, Contract, CsvIssue, Nonnegative, Positive
from quantops_api.application.market_snapshot import CATALOG, SNAPSHOT_PATH, fetch_market_snapshot


class InstrumentModel(Contract):
    symbol: str = Field(max_length=40)
    name: str = Field(max_length=100)
    kind: Kind
    sector: str = Field(max_length=100)
    currency: Literal["USD"] = "USD"
    multiplier: Positive
    margin_rate: Annotated[Decimal, Field(ge=0, le=1)]
    expiry: date | None = None
    spec_url: str | None = Field(default=None, max_length=300)


class PriceRow(Contract):
    date: date
    close: Amount


class Series(Contract):
    url: str = Field(max_length=400)
    history_url: str = Field(max_length=400)
    rows: list[PriceRow] = Field(min_length=1, max_length=800)


class Market(Contract):
    version: Literal[1] = 1
    provider: str = Field(max_length=80)
    fetched_at: datetime
    as_of: date
    price_basis: Literal["unadjusted_daily_close"]
    catalog: list[InstrumentModel] = Field(min_length=1, max_length=6)
    series: dict[str, Series]

    @model_validator(mode="after")
    def bounded_market(self) -> Self:
        expected = {item["symbol"] for item in CATALOG} | {"PLN=X"}
        if set(self.series) != expected or {i.symbol for i in self.catalog} != expected - {"PLN=X"}:
            raise ValueError("The supported instrument catalog and all FX series are required")
        if self.as_of > datetime.now(UTC).date() or self.fetched_at.tzinfo is None:
            raise ValueError("Quotes require past dates and a timezone-aware retrieval timestamp")
        fixed = {item["symbol"]: item for item in CATALOG}
        for instrument in self.catalog:
            spec = fixed[instrument.symbol]
            if instrument.kind != spec["kind"] or instrument.multiplier != Decimal(
                spec["multiplier"]
            ):
                raise ValueError("Instrument kind and contract multiplier cannot be changed")
            if instrument.expiry != (
                date.fromisoformat(spec["expiry"]) if "expiry" in spec else None
            ):
                raise ValueError("Contract expiry cannot be changed")
        for symbol, series in self.series.items():
            dates = [row.date for row in series.rows]
            if dates != sorted(set(dates)) or any(day > datetime.now(UTC).date() for day in dates):
                raise ValueError("Quote dates must be unique, ordered and not future")
            if symbol != "CLZ26.NYM" and any(row.close <= 0 for row in series.rows):
                raise ValueError("Spot and FX prices must be positive")
        return self


class Transaction(Contract):
    id: UUID
    date: date
    action: Action
    symbol: str = Field(default="", max_length=40)
    quantity: Nonnegative = Decimal(0)
    price: Amount = Decimal(0)
    amount_pln: Nonnegative = Decimal(0)
    fee_pln: Nonnegative = Decimal(0)
    source: Literal["synthetic", "user"] = "user"

    @model_validator(mode="after")
    def action_fields(self) -> Self:
        if self.action in {"buy", "sell"}:
            if self.quantity <= 0 or not self.symbol or self.amount_pln != 0:
                raise ValueError("Trades require symbol and quantity; cash amount is derived")
        elif self.quantity != 0 or self.price != 0 or self.amount_pln <= 0:
            raise ValueError("Cash entries require a positive PLN amount and no quantity or price")
        return self


class Scenario(Contract):
    id: UUID
    name: str = Field(min_length=1, max_length=80)
    price_shock: Amount = Field(default=Decimal("-0.15"), gt=-1, le=5)
    fx_shock: Amount = Field(default=Decimal("0.1"), gt=-1, le=5)
    oil_shock: Amount = Field(default=Decimal("-0.25"), gt=-1, le=5)
    forex_shock: Amount = Field(default=Decimal("-0.05"), gt=-1, le=5)


class Workspace(Contract):
    version: Literal[1] = 1
    name: str = Field(default="Mój portfel", max_length=80)
    market: Market
    transactions: list[Transaction] = Field(max_length=2000)
    scenarios: list[Scenario] = Field(max_length=20)


class ScenarioOutput(Contract):
    scenario: Scenario
    result: StressResult


class WorkspaceResult(Contract):
    result: BookResult
    scenarios: list[ScenarioOutput]
    price_provenance: Literal["provider_snapshot", "user_supplied"]
    transaction_provenance: Literal["synthetic", "user", "mixed"]


class CsvRequest(Contract):
    text: str = Field(max_length=600_000)


class TransactionPreview(Contract):
    rows: list[Transaction]
    errors: list[CsvIssue]
    importable: bool


router = APIRouter(prefix="/api/v1/investor", tags=["Local investor workspace"])
_verified: set[str] = set()


def fingerprint(market: Market) -> str:
    return hashlib.sha256(market.model_dump_json().encode()).hexdigest()


def stored_market() -> Market:
    market = Market.model_validate_json(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    _verified.add(fingerprint(market))
    return market


@router.get("/demo", response_model=Workspace)
def investor_demo() -> Workspace:
    market = stored_market()
    rows: list[Transaction] = [
        Transaction(
            id=uuid5(NAMESPACE_URL, "investor-deposit"),
            date=date(2025, 4, 1),
            action="deposit",
            amount_pln=Decimal(500000),
            source="synthetic",
        )
    ]
    for symbol, day, quantity in [
        ("AAPL", "2025-04-01", "100"),
        ("MSFT", "2025-06-02", "60"),
        ("SPY", "2025-06-02", "30"),
        ("TLT", "2025-06-02", "120"),
        ("EURUSD=X", "2026-07-01", "10000"),
        ("CLZ26.NYM", "2026-08-03", "1"),
    ]:
        execution_date = date.fromisoformat(day)
        price = next(row.close for row in market.series[symbol].rows if row.date == execution_date)
        rows.append(
            Transaction(
                id=uuid5(NAMESPACE_URL, f"investor-{symbol}"),
                date=execution_date,
                action="buy",
                symbol=symbol,
                quantity=Decimal(quantity),
                price=price,
                fee_pln=Decimal(15),
                source="synthetic",
            )
        )
    scenarios = [
        Scenario(id=uuid5(NAMESPACE_URL, "investor-stress"), name="Spadki i mocniejszy dolar"),
        Scenario(
            id=uuid5(NAMESPACE_URL, "investor-oil"),
            name="Ropa -30%, pozostałe bez zmian",
            price_shock=Decimal(0),
            fx_shock=Decimal(0),
            oil_shock=Decimal("-0.3"),
            forex_shock=Decimal(0),
        ),
    ]
    return Workspace(
        market=market, transactions=rows, scenarios=scenarios, name="Portfel demonstracyjny"
    )


@router.post(
    "/analyze", response_model=WorkspaceResult, dependencies=[Depends(require_expensive_capacity)]
)
def analyze_workspace(workspace: Workspace) -> WorkspaceResult:
    instruments = [
        Instrument(i.symbol, i.name, i.kind, i.sector, i.multiplier, i.margin_rate, i.expiry)
        for i in workspace.market.catalog
    ]
    entries = [
        Entry(str(t.id), t.date, t.action, t.symbol, t.quantity, t.price, t.amount_pln, t.fee_pln)
        for t in workspace.transactions
    ]
    series = {
        symbol: {row.date: row.close for row in s.rows}
        for symbol, s in workspace.market.series.items()
    }
    result = analyze_book(instruments, entries, series, series["PLN=X"], workspace.market.as_of)
    scenarios = [
        ScenarioOutput(
            scenario=s,
            result=stress_book(
                result,
                instruments,
                series["PLN=X"][workspace.market.as_of],
                s.price_shock,
                s.fx_shock,
                s.oil_shock,
                s.forex_shock,
            ),
        )
        for s in workspace.scenarios
    ]
    origins = {t.source for t in workspace.transactions}
    stored_market()
    return WorkspaceResult(
        result=result,
        scenarios=scenarios,
        price_provenance="provider_snapshot"
        if fingerprint(workspace.market) in _verified
        else "user_supplied",
        transaction_provenance="mixed"
        if len(origins) > 1
        else "synthetic"
        if "synthetic" in origins
        else "user",
    )


@router.post("/refresh", response_model=Market, dependencies=[Depends(require_expensive_capacity)])
def refresh_market() -> Market:
    try:
        market = Market.model_validate(fetch_market_snapshot())
    except Exception as error:
        raise HTTPException(
            503, "Market provider unavailable or data failed validation; keep the dated snapshot"
        ) from error
    if len(_verified) > 16:
        _verified.clear()
    _verified.add(fingerprint(market))
    return market


@router.post("/csv-preview", response_model=TransactionPreview)
def transaction_csv(request: CsvRequest) -> TransactionPreview:
    reader = csv.DictReader(io.StringIO(request.text.lstrip("\ufeff")), strict=True)
    rows: list[Transaction] = []
    errors: list[CsvIssue] = []
    seen: set[UUID] = set()
    try:
        if reader.fieldnames != [
            "id",
            "date",
            "action",
            "symbol",
            "quantity",
            "price",
            "amount_pln",
            "fee_pln",
            "source",
        ]:
            return TransactionPreview(
                rows=[],
                errors=[
                    CsvIssue(
                        row=1,
                        message=(
                            "Expected columns: id,date,action,symbol,quantity,price,"
                            "amount_pln,fee_pln,source"
                        ),
                    )
                ],
                importable=False,
            )
        for number, raw in enumerate(reader, 2):
            if number > 2001:
                errors.append(CsvIssue(row=number, message="Maximum 2000 transactions"))
                break
            try:
                row = Transaction.model_validate(raw)
                if row.id in seen:
                    raise ValueError("Duplicate transaction ID")
                seen.add(row.id)
                rows.append(row)
            except (ValueError, ValidationError):
                errors.append(CsvIssue(row=number, message="Invalid transaction or duplicate ID"))
    except csv.Error:
        errors.append(CsvIssue(row=reader.line_num, message="Malformed CSV"))
    return TransactionPreview(rows=rows, errors=errors, importable=bool(rows) and not errors)
