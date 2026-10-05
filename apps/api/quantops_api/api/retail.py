"""Stateless local portfolio analysis and strict current-position CSV preview."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from quantops_domain import Currency
from quantops_risk.hedging import ForwardComparison, compare_forward
from quantops_risk.scenarios import (
    FXShock,
    InstrumentPriceShock,
    ScenarioDefinition,
    ScenarioPosition,
    ScenarioShock,
    run_scenario,
)
from quantops_risk.types import PositionInput
from quantops_risk.valuation import value_position

from quantops_api.api.dependencies import require_expensive_capacity

Amount = Annotated[Decimal, Field(allow_inf_nan=False, max_digits=24, decimal_places=10)]
Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False, max_digits=24, decimal_places=10)]
Nonnegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False, max_digits=24, decimal_places=10)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Holding(Contract):
    id: UUID
    account: str = Field(min_length=1, max_length=64)
    symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9._/-]{0,31}$")
    asset_class: Literal["equity", "etf", "cash"]
    currency: str
    quantity: Amount
    price: Nonnegative
    multiplier: Positive = Decimal(1)
    as_of: datetime
    source: Literal["synthetic", "user"] = "user"

    @field_validator("currency")
    @classmethod
    def iso_currency(cls, value: str) -> str:
        return str(Currency(value))

    @field_validator("account")
    @classmethod
    def account_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("account must not be blank")
        return value.strip()

    @field_validator("as_of")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        if value > datetime.now(UTC):
            raise ValueError("as_of cannot be in the future")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def linear_spot_only(self) -> Self:
        if self.multiplier != 1:
            raise ValueError(
                "this slice supports spot equity, ETF and cash only; multiplier must be 1"
            )
        if self.quantity == 0:
            raise ValueError(
                "quantity must be nonzero; use a negative quantity for a short or liability"
            )
        if self.asset_class == "cash" and self.price != 1:
            raise ValueError("cash requires a unit price of 1")
        if self.asset_class != "cash" and self.price <= 0:
            raise ValueError("a security price must be positive")
        return self


class Portfolio(Contract):
    base_currency: str = "PLN"
    positions: list[Holding] = Field(max_length=200)
    fx: dict[str, Positive]
    fx_as_of: datetime
    fx_source: Literal["synthetic", "user"] = "user"

    @field_validator("base_currency")
    @classmethod
    def iso_currency(cls, value: str) -> str:
        return Holding.iso_currency(value)

    @field_validator("fx_as_of")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return Holding.utc_timestamp(value)

    @model_validator(mode="after")
    def consistent_inputs(self) -> Self:
        for code in self.fx:
            if str(Currency(code)) != code:
                raise ValueError("FX keys must be canonical ISO currency codes")
        if self.fx.get(self.base_currency) != 1:
            raise ValueError("base-currency FX rate must equal 1")
        if any(p.currency not in self.fx for p in self.positions):
            raise ValueError("each position currency requires a positive FX rate")
        identities = [(p.account, p.symbol, p.currency) for p in self.positions]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate account/symbol/currency; aggregate current positions first")
        if len({p.id for p in self.positions}) != len(self.positions):
            raise ValueError("position IDs must be unique")
        return self


class AnalysisRequest(Contract):
    portfolio: Portfolio
    currency: str = "USD"
    fx_shock: Amount = Field(default=Decimal("-0.1"), gt=-1, le=5)
    asset_shock: Amount = Field(default=Decimal(0), ge=-1, le=5)
    hedge_ratio: Amount = Field(default=Decimal("0.5"), ge=0, le=1)
    days: int = Field(default=90, ge=1, le=3650)
    base_rate: Amount = Field(default=Decimal("0.04"), ge=Decimal("-0.1"), le=1)
    foreign_rate: Amount = Field(default=Decimal("0.03"), ge=Decimal("-0.1"), le=1)
    entry_bps: Nonnegative = Field(default=Decimal(10), le=10000)
    annual_holding_bps: Nonnegative = Field(default=Decimal(0), le=10000)

    @field_validator("currency")
    @classmethod
    def iso_currency(cls, value: str) -> str:
        return Holding.iso_currency(value)

    @model_validator(mode="after")
    def foreign_rate_available(self) -> Self:
        if self.currency == self.portfolio.base_currency or self.currency not in self.portfolio.fx:
            raise ValueError("select a foreign currency with a supplied FX rate")
        return self


class PositionResult(Contract):
    id: UUID
    symbol: str
    currency: str
    value: Decimal
    stressed_value: Decimal
    impact: Decimal
    gross_weight: Decimal | None


class Exposure(Contract):
    currency: str
    foreign_amount: Decimal
    net_base: Decimal
    gross_base: Decimal


class HedgeResult(Contract):
    ratio: Decimal
    signed_foreign_notional: Decimal
    base_notional: Decimal
    remaining_foreign_exposure: Decimal
    theoretical_forward: Decimal
    terminal_spot: Decimal
    payoff: Decimal
    entry_cost: Decimal
    holding_cost: Decimal
    net_payoff: Decimal
    portfolio_impact: Decimal
    terminal_value: Decimal
    overhedged_after_shock: bool


class AnalysisResponse(Contract):
    model_version: str = "retail-fx-forward@1.0.0"
    calculated_at: datetime
    run_id: str | None
    base_currency: str
    source: Literal["synthetic", "user", "mixed"]
    net_value: Decimal
    cash_value: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    gross_to_equity: Decimal | None
    concentration: Decimal | None
    unhedged_impact: Decimal
    impact_fraction: Decimal | None
    positions: list[PositionResult]
    exposures: list[Exposure]
    hedges: list[HedgeResult]
    warnings: list[str]
    historical_risk_status: Literal["insufficient_data"] = "insufficient_data"


router = APIRouter(prefix="/api/v1/retail", tags=["Local portfolio sensitivity"])


@router.get("/demo", response_model=Portfolio)
def demo_portfolio() -> Portfolio:
    """Return visibly fictional spot positions; these are not investment recommendations."""
    timestamp = datetime(2026, 1, 2, 16, tzinfo=UTC)
    rows = [
        ("QGLOBAL", "etf", "USD", "100", "100"),
        ("QEURO", "equity", "EUR", "100", "50"),
        ("QPOL", "equity", "PLN", "100", "100"),
        ("CASH-PLN", "cash", "PLN", "10000", "1"),
    ]
    return Portfolio.model_validate(
        {
            "base_currency": "PLN",
            "fx": {"PLN": "1", "USD": "4", "EUR": "4.3"},
            "fx_as_of": timestamp,
            "fx_source": "synthetic",
            "positions": [
                {
                    "id": uuid5(NAMESPACE_URL, symbol),
                    "account": "Demo",
                    "symbol": symbol,
                    "asset_class": kind,
                    "currency": currency,
                    "quantity": quantity,
                    "price": price,
                    "as_of": timestamp,
                    "source": "synthetic",
                }
                for symbol, kind, currency, quantity, price in rows
            ],
        }
    )


def hedge_result(
    result: ForwardComparison, impact: Decimal, value: Decimal, stressed_exposure: Decimal
) -> HedgeResult:
    return HedgeResult(
        **{name: getattr(result, name) for name in ForwardComparison.__dataclass_fields__},
        portfolio_impact=impact + result.net_payoff,
        terminal_value=value + impact + result.net_payoff,
        overhedged_after_shock=abs(result.signed_foreign_notional) > abs(stressed_exposure),
    )


@router.post(
    "/analyze", response_model=AnalysisResponse, dependencies=[Depends(require_expensive_capacity)]
)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    """Calculate without persisting portfolios, credentials, prices or personal data."""
    portfolio = request.portfolio
    values = {
        p.id: value_position(
            PositionInput(
                str(p.id),
                p.quantity * p.multiplier,
                p.price,
                p.currency,
                portfolio.base_currency,
                portfolio.fx[p.currency],
            )
        ).market_value
        for p in portfolio.positions
    }
    securities = [p for p in portfolio.positions if p.asset_class != "cash"]
    gross = sum((abs(values[p.id]) for p in securities), Decimal(0))
    net = sum(values.values(), Decimal(0))
    exposures = [
        Exposure(
            currency=code,
            foreign_amount=sum(
                (
                    p.quantity * p.price * p.multiplier
                    for p in portfolio.positions
                    if p.currency == code
                ),
                Decimal(0),
            ),
            net_base=sum(
                (values[p.id] for p in portfolio.positions if p.currency == code), Decimal(0)
            ),
            gross_base=sum(
                (abs(values[p.id]) for p in portfolio.positions if p.currency == code), Decimal(0)
            ),
        )
        for code in sorted({p.currency for p in portfolio.positions})
    ]
    run = None
    if portfolio.positions:
        shocks: tuple[ScenarioShock, ...] = (
            FXShock(request.currency, request.fx_shock),
            *(InstrumentPriceShock(str(p.id), request.asset_shock) for p in securities),
        )
        # The scenario core rejects shocks for absent currencies. Retain security
        # shocks, or use a neutral price shock for a cash-only portfolio.
        if not any(p.currency == request.currency for p in portfolio.positions):
            shocks = tuple(shocks[1:]) or (
                InstrumentPriceShock(str(portfolio.positions[0].id), Decimal(0)),
            )
        run = run_scenario(
            ScenarioDefinition(
                "retail-combined",
                "Hypothetical asset and FX shock",
                "1.0.0",
                shocks,
                ("Constant positions; terminal sensitivity; no historical investor performance",),
            ),
            tuple(
                ScenarioPosition(
                    str(p.id),
                    p.asset_class,
                    p.quantity * p.multiplier,
                    p.price,
                    p.currency,
                    portfolio.base_currency,
                    portfolio.fx[p.currency],
                )
                for p in portfolio.positions
            ),
        )
    impacts = {UUID(p.instrument_id): p for p in run.positions} if run else {}
    impact = run.pnl if run else Decimal(0)
    selected_exposure = next(
        (e.foreign_amount for e in exposures if e.currency == request.currency), Decimal(0)
    )
    stressed_exposure = sum(
        (
            p.quantity
            * p.price
            * p.multiplier
            * (1 if p.asset_class == "cash" else 1 + request.asset_shock)
            for p in portfolio.positions
            if p.currency == request.currency
        ),
        Decimal(0),
    )
    ratios = [Decimal(0), request.hedge_ratio, Decimal(1)]
    sources = {p.source for p in portfolio.positions} | {portfolio.fx_source}
    now = datetime.now(UTC)
    warnings = [
        "quotation_currency_only",
        "no_historical_returns",
        "terminal_forward_model",
        "user_cost_estimates",
        "no_broker_quote",
        "cash_entered_once",
    ]
    if any((now - p.as_of).total_seconds() > 86400 for p in portfolio.positions):
        warnings.append("stale_prices")
    if (now - portfolio.fx_as_of).total_seconds() > 86400:
        warnings.append("stale_fx")
    if net <= 0:
        warnings.append("nonpositive_equity")
    if any(p.quantity < 0 for p in securities):
        warnings.append("short_collateral_excluded")
    return AnalysisResponse(
        calculated_at=now,
        run_id=run.deterministic_run_id if run else None,
        base_currency=portfolio.base_currency,
        source="mixed" if len(sources) > 1 else next(iter(sources)),
        net_value=net,
        cash_value=sum(
            (values[p.id] for p in portfolio.positions if p.asset_class == "cash"), Decimal(0)
        ),
        gross_exposure=gross,
        net_exposure=sum((values[p.id] for p in securities), Decimal(0)),
        gross_to_equity=gross / net if net > 0 else None,
        concentration=max((abs(values[p.id]) / gross for p in securities), default=None)
        if gross
        else None,
        unhedged_impact=impact,
        impact_fraction=impact / net if net > 0 else None,
        positions=[
            PositionResult(
                id=p.id,
                symbol=p.symbol,
                currency=p.currency,
                value=values[p.id],
                stressed_value=impacts[p.id].stressed_market_value,
                impact=impacts[p.id].pnl,
                gross_weight=abs(values[p.id]) / gross
                if gross and p.asset_class != "cash"
                else None,
            )
            for p in portfolio.positions
        ],
        exposures=exposures,
        hedges=[
            hedge_result(
                compare_forward(
                    foreign_exposure=selected_exposure,
                    spot=portfolio.fx[request.currency],
                    fx_shock=request.fx_shock,
                    ratio=ratio,
                    days=request.days,
                    base_rate=request.base_rate,
                    foreign_rate=request.foreign_rate,
                    entry_bps=request.entry_bps,
                    annual_holding_bps=request.annual_holding_bps,
                ),
                impact,
                net,
                stressed_exposure,
            )
            for ratio in ratios
        ],
        warnings=warnings,
    )


CSV_COLUMNS = (
    "account",
    "symbol",
    "asset_class",
    "currency",
    "quantity",
    "price",
    "multiplier",
    "as_of",
    "source",
)


class CsvRequest(Contract):
    text: str = Field(max_length=200_000)


class CsvIssue(Contract):
    row: int
    message: str


class CsvPreview(Contract):
    positions: list[Holding]
    errors: list[CsvIssue]
    importable: bool
    import_kind: Literal["current_positions"] = "current_positions"


@router.post(
    "/csv-preview", response_model=CsvPreview, dependencies=[Depends(require_expensive_capacity)]
)
def csv_preview(request: CsvRequest) -> CsvPreview:
    """Validate every row before confirmation; never infer transactions from holdings."""
    reader = csv.DictReader(io.StringIO(request.text.lstrip("\ufeff")), strict=True)
    positions: list[Holding] = []
    errors: list[CsvIssue] = []
    try:
        if reader.fieldnames != list(CSV_COLUMNS):
            return CsvPreview(
                positions=[],
                errors=[
                    CsvIssue(
                        row=1,
                        message="Expected columns in order: " + ",".join(CSV_COLUMNS),
                    )
                ],
                importable=False,
            )
        identities: set[tuple[str, str, str]] = set()
        for row_number, row in enumerate(reader, start=2):
            if row_number > 201:
                errors.append(CsvIssue(row=row_number, message="Maximum 200 positions per import"))
                break
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("Column count does not match the header")
                identity = (row["account"].strip(), row["symbol"], row["currency"].strip().upper())
                position = Holding.model_validate(
                    {
                        **row,
                        "id": uuid5(NAMESPACE_URL, "|".join(identity)),
                    }
                )
                if identity in identities:
                    raise ValueError("Duplicate account/symbol/currency")
                identities.add(identity)
                positions.append(position)
            except (ValidationError, ValueError) as error:
                message = (
                    "; ".join(
                        f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
                        for issue in error.errors()
                    )
                    if isinstance(error, ValidationError)
                    else str(error)
                )
                errors.append(CsvIssue(row=row_number, message=message))
    except csv.Error:
        errors.append(CsvIssue(row=reader.line_num, message="Malformed CSV quoting"))
    if not positions and not errors:
        errors.append(CsvIssue(row=2, message="The file has no positions"))
    return CsvPreview(positions=positions, errors=errors, importable=bool(positions) and not errors)
