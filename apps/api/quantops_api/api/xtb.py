"""Stateless XTB report import, account-isolated merging and public reference prices."""

import base64
import binascii
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator

from quantops_api.api.dependencies import require_expensive_capacity
from quantops_api.application.stock_quotes import StockQuote
from quantops_api.application.xtb_book import XtbAnalysis, analyze_book, merge_book
from quantops_api.application.xtb_models import (
    ReportContract,
    XtbBook,
    XtbPreview,
    iso_currency,
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
