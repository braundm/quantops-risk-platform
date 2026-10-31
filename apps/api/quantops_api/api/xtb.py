"""Stateless XTB report import, account-isolated merging and public reference prices."""

import base64
import binascii
import math
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator

from quantops_api.api.dependencies import require_expensive_capacity
from quantops_api.application.portfolio_history_provider import fetch_risk_histories
from quantops_api.application.portfolio_risk import (
    CashBalance,
    ExposureMetadata,
    RiskHistory,
    RiskPrice,
    RiskRequest,
    RiskResult,
    RiskScenario,
    analyze_imported_risk,
)
from quantops_api.application.stock_quotes import StockQuote
from quantops_api.application.xtb_book import XtbAnalysis, analyze_book, merge_book
from quantops_api.application.xtb_models import (
    ReportContract,
    XtbBook,
    XtbPreview,
    XtbRecord,
    iso_currency,
    record_id,
    utc_time,
)
from quantops_api.application.xtb_quotes import fetch_xtb_quote
from quantops_api.application.xtb_reports import parse_report
from quantops_api.application.xtb_valuation import ImportedQuote, ImportedValuation, value_book

router = APIRouter(prefix="/api/v1/xtb", tags=["Imported XTB reports"])


class PreviewRequest(ReportContract):
    account_number: str = Field(pattern=r"^[0-9]{1,20}$")
    currency: str
    observed_at: datetime
    filename: str = Field(min_length=1, max_length=240)
    content_base64: str = Field(max_length=11200000)

    _currency = field_validator("currency")(iso_currency)
    _observed = field_validator("observed_at")(utc_time)


@router.post(
    "/preview", response_model=XtbPreview, dependencies=[Depends(require_expensive_capacity)]
)
def preview_report(request: PreviewRequest) -> XtbPreview:
    try:
        data = base64.b64decode(request.content_base64, validate=True)
        return parse_report(
            request.filename, data, request.account_number, request.currency, request.observed_at
        )
    except (ValueError, binascii.Error) as error:
        raise HTTPException(422, str(error).splitlines()[0]) from error


class MergeRequest(ReportContract):
    current: XtbBook
    preview: XtbPreview
    complete_snapshot: bool = False
    complete_ledger: bool = False


class MergeResult(ReportContract):
    book: XtbBook
    duplicates: int
    analysis: XtbAnalysis


@router.post("/merge", response_model=MergeResult)
def merge_report(request: MergeRequest) -> MergeResult:
    try:
        book, duplicates = merge_book(
            request.current,
            request.preview,
            complete_snapshot=request.complete_snapshot,
            complete_ledger=request.complete_ledger,
        )
        return MergeResult(book=book, duplicates=duplicates, analysis=analyze_book(book))
    except ValueError as error:
        raise HTTPException(422, str(error).splitlines()[0]) from error


@router.post("/analyze", response_model=XtbAnalysis)
def analyze_report(book: XtbBook) -> XtbAnalysis:
    try:
        return analyze_book(book)
    except ValueError as error:
        raise HTTPException(422, str(error).splitlines()[0]) from error


class QuoteRequest(ReportContract):
    book: XtbBook
    symbol: str = Field(min_length=1, max_length=80)


@router.post(
    "/quote", response_model=StockQuote, dependencies=[Depends(require_expensive_capacity)]
)
def quote_imported(request: QuoteRequest) -> StockQuote:
    try:
        analysis = analyze_book(request.book)
        holdings = [
            row
            for row in analysis.holdings
            if row.symbol == request.symbol and row.status == "spot"
        ]
        if not holdings or analysis.holdings_status in ("unknown", "incomplete"):
            raise ValueError("A complete imported physical holding is required")
        purchased = min(row.opened_at.date() for row in holdings)
        return fetch_xtb_quote(request.symbol, purchased)
    except Exception as error:
        raise HTTPException(
            503,
            "Nie udało się zweryfikować ceny i waluty tego instrumentu; zachowano ostatni zapis.",
        ) from error


class ValueRequest(ReportContract):
    book: XtbBook
    marks: list[ImportedQuote] = Field(default_factory=list, max_length=1000)


@router.post("/value", response_model=ImportedValuation)
def value_imported(request: ValueRequest) -> ImportedValuation:
    try:
        return value_book(request.book, request.marks)
    except ValueError as error:
        raise HTTPException(422, str(error).splitlines()[0]) from error


@router.post("/risk", response_model=RiskResult, dependencies=[Depends(require_expensive_capacity)])
def risk_imported(request: RiskRequest) -> RiskResult:
    try:
        return analyze_imported_risk(request)
    except ValueError as error:
        raise HTTPException(422, str(error).splitlines()[0]) from error


class HistoryFetch(ReportContract):
    symbols: list[str] = Field(min_length=1, max_length=20)
    base_currency: str = "PLN"
    start: date
    end: date

    _currency = field_validator("base_currency")(iso_currency)


class HistoryFetchResult(ReportContract):
    histories: list[RiskHistory]
    failures: dict[str, str]


@router.post(
    "/risk-history",
    response_model=HistoryFetchResult,
    dependencies=[Depends(require_expensive_capacity)],
)
def history_imported(request: HistoryFetch) -> HistoryFetchResult:
    if (
        not date(1990, 1, 1) <= request.start < request.end < datetime.now(UTC).date()
        or (request.end - request.start).days > 1827
    ):
        raise HTTPException(422, "Choose completed dates covering at most five years")
    histories, failures = fetch_risk_histories(
        list(dict.fromkeys(request.symbols)), request.base_currency, request.start, request.end
    )
    return HistoryFetchResult(histories=histories, failures=failures)


@router.get("/risk-example", response_model=RiskRequest)
def risk_example(
    asset_scope: Literal["all_supported", "equities_only"] = "all_supported",
) -> RiskRequest:
    """A visibly synthetic analysis sandbox; it never alters imported accounts."""
    days: list[date] = []
    day = date(2024, 1, 2)
    while len(days) < 340:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    observed = datetime.combine(days[-1], datetime.min.time(), UTC)
    histories: list[RiskHistory] = []
    records: list[XtbRecord] = []
    instruments = (
        (
            ("AAPL.US", "equity", "20", 100, 1.2),
            ("MSFT.US", "equity", "15", 150, 1.0),
            ("CSPX.UK", "etf", "10", 200, 0.7),
        )
        if asset_scope == "all_supported"
        else (
            ("AAPL.US", "equity", "20", 100, 1.2),
            ("MSFT.US", "equity", "15", 150, 1.0),
            ("JNJ.US", "equity", "12", 140, 0.5),
            ("JPM.US", "equity", "14", 120, 0.8),
            ("XOM.US", "equity", "18", 90, 1.4),
        )
    )
    for symbol, kind, quantity, anchor, sensitivity in instruments:
        rows = []
        for i, timestamp in enumerate(days):
            move = (
                0.09 * math.sin(i / 13) + 0.025 * math.sin(i * 0.7) - (0.2 if 160 <= i < 220 else 0)
            )
            if asset_scope == "equities_only":
                move += 0.035 * math.sin(i / (7 + sensitivity * 9) + sensitivity * 3)
            price = Decimal(f"{anchor * (1 + move * sensitivity + i * 0.0001):.6f}")
            fx = Decimal(f"{4 + 0.1 * math.sin(i / 17):.6f}")
            rows.append(RiskPrice(date=timestamp, close=price, adjusted_close=price, fx_to_base=fx))
        histories.append(
            RiskHistory(
                symbol=symbol,
                currency="USD",
                base_currency="PLN",
                source="Explicit synthetic research fixture",
                source_url="https://example.com/synthetic-quantops",
                fx_source="Synthetic USD/PLN",
                fetched_at=observed,
                origin="synthetic",
                rows=rows,
            )
        )
        records.append(
            XtbRecord(
                id=record_id("999000", "open", symbol, None),
                account_number="999000",
                kind="open",
                source_id=symbol,
                symbol=symbol,
                name=f"Synthetic {symbol}",
                asset_type="etf" if kind == "etf" else "equity",
                side="BUY",
                quantity=Decimal(quantity),
                price=Decimal(anchor),
                event_at=observed,
                observed_at=observed,
            )
        )
    return RiskRequest(
        book=XtbBook(
            account_number="999000", currency="PLN", records=records, open_snapshot_at=observed
        ),
        scope="securities_only" if asset_scope == "equities_only" else "full_account",
        asset_scope=asset_scope,
        histories=histories,
        cash=[]
        if asset_scope == "equities_only"
        else [CashBalance(symbol="CASH:PLN", currency="PLN", amount=Decimal(5000), as_of=days[-1])],
        cash_confirmed=asset_scope == "all_supported",
        benchmark=None if asset_scope == "equities_only" else "CSPX.UK",
        metadata=[
            ExposureMetadata(
                symbol=symbol,
                sector=sector,
                issuer_id=f"synthetic-{symbol}",
                issuer_country="US",
                source_url="https://example.com/synthetic-quantops",
                as_of=days[-1],
            )
            for symbol, sector in (
                ("AAPL.US", "Technology"),
                ("MSFT.US", "Technology"),
                ("JNJ.US", "Healthcare"),
                ("JPM.US", "Financials"),
                ("XOM.US", "Energy"),
            )
        ]
        if asset_scope == "equities_only"
        else [],
        tolerance_fraction=Decimal("0.1"),
        scenarios=[
            RiskScenario(
                name="Hypothetical equities -20%, PLN appreciation",
                class_shocks={"equity": Decimal("-0.2"), "etf": Decimal("-0.2")},
                fx_shocks={"USD": Decimal("-0.1")},
            ),
            RiskScenario(
                name="Hypothetical equities -10%, USD appreciation",
                class_shocks={"equity": Decimal("-0.1"), "etf": Decimal("-0.1")},
                fx_shocks={"USD": Decimal("0.1")},
            ),
        ],
    )
