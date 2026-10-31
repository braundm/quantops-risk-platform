"""Aligned historical spot repricing of current units; never investor performance."""

from __future__ import annotations

import csv
import io
import math
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from itertools import pairwise
from typing import Annotated, Literal, Self

from fastapi import APIRouter, Depends
from pydantic import Field, ValidationError, model_validator
from quantops_risk.correlation import correlation_matrix
from quantops_risk.drawdown import maximum_drawdown
from quantops_risk.expected_shortfall import historical_expected_shortfall
from quantops_risk.var import historical_var
from quantops_risk.volatility import sample_volatility

from quantops_api.api.dependencies import require_expensive_capacity
from quantops_api.api.retail import Contract, CsvIssue, Portfolio, Positive


class HistoryRow(Contract):
    date: date
    symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9._/-]{0,31}$")
    price: Positive
    fx_to_base: Positive
    source: Literal["synthetic", "user"]

    @model_validator(mode="after")
    def no_future(self) -> Self:
        if self.date > datetime.now(UTC).date():
            raise ValueError("history must not contain future observations")
        return self


class HistoryPreview(Contract):
    rows: list[HistoryRow]
    errors: list[CsvIssue]
    importable: bool


class HistoryCsv(Contract):
    text: str = Field(max_length=1_500_000)


class HistoryRequest(Contract):
    portfolio: Portfolio
    rows: list[HistoryRow] = Field(max_length=20_000)
    confidence: Annotated[Decimal, Field(ge=Decimal("0.90"), le=Decimal("0.99"))] = Decimal("0.95")


class HistoryPoint(Contract):
    date: date
    value: Decimal


class HistoricalRisk(Contract):
    model_version: str = "current-units-history@1.0.0"
    status: Literal["ok", "insufficient_data", "invalid_data", "unstable"]
    source: Literal["synthetic", "user", "mixed"]
    base_currency: str
    confidence: Decimal
    observation_count: int
    required_observations: int
    tail_count: int = 0
    var_amount: Decimal | None = None
    es_amount: Decimal | None = None
    var_fraction: float | None = None
    es_fraction: float | None = None
    daily_volatility: float | None = None
    maximum_drawdown: float | None = None
    period_start: date | None = None
    period_end: date | None = None
    points: list[HistoryPoint]
    correlation_symbols: list[str] = Field(default_factory=list)
    correlations: list[list[float | None]] = Field(default_factory=list)
    warnings: list[str]


router = APIRouter(prefix="/api/v1/retail", tags=["Historical portfolio simulation"])


@router.post(
    "/history-preview",
    response_model=HistoryPreview,
    dependencies=[Depends(require_expensive_capacity)],
)
def preview_history(request: HistoryCsv) -> HistoryPreview:
    reader = csv.DictReader(io.StringIO(request.text.lstrip("\ufeff")), strict=True)
    rows: list[HistoryRow] = []
    errors: list[CsvIssue] = []
    seen: set[tuple[date, str]] = set()
    try:
        if reader.fieldnames != ["date", "symbol", "price", "fx_to_base", "source"]:
            return HistoryPreview(
                rows=[],
                importable=False,
                errors=[
                    CsvIssue(
                        row=1,
                        message="Expected columns: date,symbol,price,fx_to_base,source",
                    )
                ],
            )
        for number, raw in enumerate(reader, 2):
            if number > 20_001:
                errors.append(CsvIssue(row=number, message="Maximum 20000 observations"))
                break
            try:
                item = HistoryRow.model_validate(raw)
                key = (item.date, item.symbol)
                if key in seen:
                    raise ValueError("Duplicate date/symbol observation")
                seen.add(key)
                rows.append(item)
            except (ValueError, ValidationError):
                errors.append(CsvIssue(row=number, message="Invalid or duplicate observation"))
    except csv.Error:
        errors.append(CsvIssue(row=reader.line_num, message="Malformed CSV quoting"))
    if not rows and not errors:
        errors.append(CsvIssue(row=2, message="No history observations"))
    return HistoryPreview(rows=rows, errors=errors, importable=bool(rows) and not errors)


@router.get("/history-demo", response_model=list[HistoryRow])
def demo_history() -> list[HistoryRow]:
    """Return a fixed synthetic fixture, not retrospectively selected market winners."""
    rows: list[HistoryRow] = []
    dates: list[date] = []
    day = date(2024, 7, 1)
    while len(dates) < 340:
        if day.weekday() < 5:
            dates.append(day)
        day += timedelta(days=1)
    for index, timestamp in enumerate(dates):
        market = math.sin(index * 0.73) * 0.04 + math.sin(index * 0.17) * 0.07
        shock = -0.13 if 170 <= index < 190 else 0
        for symbol, anchor, sensitivity, fx in (
            ("QGLOBAL", 100, 1.0, 4.0),
            ("QEURO", 50, 0.8, 4.3),
            ("QPOL", 100, 0.65, 1.0),
        ):
            price = anchor * (1 + market * sensitivity + shock + index * 0.00015)
            rate = fx if fx == 1 else fx * (1 + math.sin(index * 0.11) * 0.025)
            rows.append(
                HistoryRow(
                    date=timestamp,
                    symbol=symbol,
                    price=Decimal(f"{price:.6f}"),
                    fx_to_base=Decimal(f"{rate:.6f}"),
                    source="synthetic",
                )
            )
    return rows


@router.post(
    "/history-risk",
    response_model=HistoricalRisk,
    dependencies=[Depends(require_expensive_capacity)],
)
def historical_risk(request: HistoryRequest) -> HistoricalRisk:
    """Reprice fixed current units on fully aligned prices and dated FX; no gap filling."""
    portfolio = request.portfolio
    needed = {
        p.symbol
        for p in portfolio.positions
        if p.asset_class != "cash" or p.currency != portfolio.base_currency
    }
    rows = [r for r in request.rows if r.symbol in needed]
    origins = (
        {r.source for r in rows} | {p.source for p in portfolio.positions} | {portfolio.fx_source}
    )
    source: Literal["synthetic", "user", "mixed"] = (
        "mixed" if len(origins) > 1 else "synthetic" if "synthetic" in origins else "user"
    )
    required = max(
        252, int((Decimal(5) / (1 - request.confidence)).to_integral_value(rounding=ROUND_CEILING))
    )
    warnings = [
        "fixed_current_units",
        "not_investor_performance",
        "var_not_maximum_loss",
        "no_history_gap_filling",
        "unadjusted_prices_require_corporate_action_review",
    ]
    indexed = {(r.date, r.symbol): r for r in rows}
    calendars = {symbol: {r.date for r in rows if r.symbol == symbol} for symbol in needed}
    dates = sorted({r.date for r in rows})
    invalid = (
        not needed
        or any(
            len({(p.currency, p.asset_class) for p in portfolio.positions if p.symbol == symbol})
            > 1
            for symbol in needed
        )
        or len(indexed) != len(rows)
        or any(calendar != set(dates) for calendar in calendars.values())
        or any(not calendar for calendar in calendars.values())
    )
    values: list[HistoryPoint] = []
    series: dict[str, list[float]] = {symbol: [] for symbol in needed}
    if not invalid:
        for day in dates:
            total = Decimal(0)
            rates: dict[str, Decimal] = {}
            for p in portfolio.positions:
                if p.asset_class == "cash" and p.currency == portfolio.base_currency:
                    total += p.quantity
                    continue
                row = indexed[day, p.symbol]
                if p.currency == portfolio.base_currency and row.fx_to_base != 1:
                    invalid = True
                if p.asset_class == "cash" and row.price != 1:
                    invalid = True
                if p.currency in rates and rates[p.currency] != row.fx_to_base:
                    invalid = True
                rates[p.currency] = row.fx_to_base
                total += p.quantity * row.price * row.fx_to_base
            if total <= 0:
                invalid = True
            values.append(HistoryPoint(date=day, value=total))
        for symbol in needed:
            prices = [indexed[day, symbol].price * indexed[day, symbol].fx_to_base for day in dates]
            series[symbol] = [float(b / a - 1) for a, b in pairwise(prices)]
    count = max(0, len(values) - 1)
    response = HistoricalRisk(
        status="invalid_data" if invalid else "insufficient_data",
        source=source,
        base_currency=portfolio.base_currency,
        confidence=request.confidence,
        observation_count=count,
        required_observations=required,
        points=[] if invalid else values,
        period_start=dates[0] if dates else None,
        period_end=dates[-1] if dates else None,
        warnings=warnings,
    )
    if invalid:
        response.warnings.append("incomplete_or_inconsistent_history")
        return response
    if any((b - a).days > 3 for a, b in pairwise(dates)):
        response.warnings.append("calendar_gaps_one_observation_horizon")
    if count < required:
        response.warnings.append("too_short_history")
        return response
    returns = [float(b.value / a.value - 1) for a, b in pairwise(values)]
    confidence = float(request.confidence)
    var = historical_var(returns, confidence_level=confidence)
    es = historical_expected_shortfall(returns, confidence_level=confidence)
    current_value = sum(
        (p.quantity * p.price * portfolio.fx[p.currency] for p in portfolio.positions), Decimal(0)
    )
    if current_value <= 0:
        response.status = "invalid_data"
        response.warnings.append("nonpositive_current_equity")
        return response
    response.status = "ok" if es.tail_observation_count >= 5 else "unstable"
    response.tail_count = es.tail_observation_count
    response.var_fraction = var.require_value()
    response.es_fraction = es.require_value()
    response.var_amount = current_value * Decimal(str(var.require_value()))
    response.es_amount = current_value * Decimal(str(es.require_value()))
    response.daily_volatility = sample_volatility(returns).require_value()
    response.maximum_drawdown = maximum_drawdown(
        [float(p.value) for p in values],
        dates,
    ).maximum_drawdown
    correlations = correlation_matrix(series, minimum_observations=252, unstable_below=252)
    response.correlation_symbols = list(correlations.instrument_ids)
    response.correlations = [list(row) for row in correlations.matrix]
    if source != "user":
        response.warnings.append("synthetic_history")
    if dates[-1] < datetime.now(UTC).date() - timedelta(days=7):
        response.warnings.append("history_is_not_recent")
    return response
