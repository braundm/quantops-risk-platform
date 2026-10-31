"""Stock-only onboarding tools and stateless marks; no accounts or investment selection."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from quantops_risk.stock_holdings import StockMark, StockValue, value_stock

from quantops_api.api.dependencies import require_expensive_capacity
from quantops_api.api.retail import Contract, Positive
from quantops_api.application.stock_catalog import BY_SYMBOL, STOCKS, Stock
from quantops_api.application.stock_quotes import StockQuote, fetch_stock_quote

router = APIRouter(prefix="/api/v1/stocks", tags=["Stock-only workspace"])
Knowledge = Literal["none", "basic", "experienced"]


class ProfileAnswers(Contract):
    goal: str = Field(min_length=1, max_length=200)
    horizon_months: int = Field(ge=1, le=1200)
    willingness_pct: int = Field(ge=0, le=100)
    capacity_pct: int = Field(ge=0, le=100)
    needs_cash_soon: bool
    stocks: Knowledge
    bonds: Knowledge
    etfs: Knowledge
    options: Knowledge
    futures: Knowledge
    knows_loss: bool
    knows_diversification: bool
    knows_leverage: bool


class ProfileResult(Contract):
    learning_level: Literal["introductory", "standard", "detailed"]
    flags: list[str]
    learning_topics: list[str]
    available_tools: list[str]
    deferred_instruments: list[str] = Field(
        default_factory=lambda: ["bonds", "etfs", "options", "futures", "forex"]
    )


@router.post("/profile", response_model=ProfileResult)
def assess_profile(answers: ProfileAnswers) -> ProfileResult:
    flags = []
    if answers.willingness_pct > answers.capacity_pct:
        flags.append("willingness_exceeds_capacity")
    if answers.needs_cash_soon or answers.horizon_months < 12:
        flags.append("short_horizon_or_liquidity_need")
    topics = ["stock_ownership_and_losses", "concentration", "currency_and_reference_prices"]
    if not answers.knows_diversification:
        topics.append("diversification_basics")
    if not answers.knows_leverage or answers.options != "none" or answers.futures != "none":
        topics.append("derivatives_and_leverage_later")
    level: Literal["introductory", "standard", "detailed"] = (
        "introductory"
        if answers.stocks == "none" or not answers.knows_loss
        else "detailed"
        if answers.stocks == "experienced"
        else "standard"
    )
    return ProfileResult(
        learning_level=level,
        flags=flags,
        learning_topics=topics,
        available_tools=[
            "xtb_report_import",
            "isolated_broker_accounts",
            "historical_close_lookup",
            "native_currency_valuation",
        ],
    )


@router.get("/catalog", response_model=list[Stock])
def stock_catalog() -> tuple[Stock, ...]:
    return STOCKS


class QuoteRequest(Contract):
    symbol: str = Field(max_length=20)
    purchased: date

    @model_validator(mode="after")
    def allowlisted(self) -> Self:
        if self.symbol not in BY_SYMBOL:
            raise ValueError("Choose a stock from the supported catalog")
        if not date(1990, 1, 1) <= self.purchased < datetime.now(UTC).date():
            raise ValueError("Choose a historical purchase date, from 1990 to yesterday")
        return self


@router.post(
    "/quote", response_model=StockQuote, dependencies=[Depends(require_expensive_capacity)]
)
def stock_quote(request: QuoteRequest) -> StockQuote:
    try:
        return fetch_stock_quote(request.symbol, request.purchased)
    except Exception as error:
        raise HTTPException(
            503,
            "Nie udało się pobrać poprawnych cen. Spróbuj ponownie; "
            "dane portfela pozostają bez zmian.",
        ) from error


class OwnedStock(Contract):
    id: UUID
    symbol: str = Field(max_length=20)
    quantity: Positive
    purchased: date
    purchase_price: Positive | None = None
    price_basis: Literal["actual", "reference", "unknown"]
    quote: StockQuote

    @model_validator(mode="after")
    def matching_quote(self) -> Self:
        stock = BY_SYMBOL.get(self.symbol)
        if (
            stock is None
            or self.quote.stock != stock
            or self.quote.requested_date != self.purchased
        ):
            raise ValueError("Position and catalog quote must agree")
        if self.purchased > self.quote.latest_date:
            raise ValueError("Valuation must not precede purchase")
        if (self.price_basis == "unknown") != (self.purchase_price is None):
            raise ValueError("Cost price and basis must agree")
        if (
            self.price_basis == "reference"
            and self.purchase_price != self.quote.purchase_reference_close
        ):
            raise ValueError("Reference cost must match the disclosed reference")
        return self


class ValueRequest(Contract):
    positions: list[OwnedStock] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        if len({p.id for p in self.positions}) != len(self.positions):
            raise ValueError("Duplicate position IDs")
        return self


class PositionValue(Contract):
    id: UUID
    mark: StockValue


class CurrencyValue(Contract):
    currency: Literal["USD", "PLN"]
    value: Decimal
    cost: Decimal | None
    unrealized_change: Decimal | None
    estimated_cost: bool


class ValueResult(Contract):
    positions: list[PositionValue]
    totals: list[CurrencyValue]
    model_version: str = "stock-holdings@1.0.0"
    quote_provenance: Literal["client_supplied_snapshot"] = "client_supplied_snapshot"


@router.post("/value", response_model=ValueResult)
def value_holdings(request: ValueRequest) -> ValueResult:
    positions = [
        PositionValue(
            id=p.id,
            mark=value_stock(
                StockMark(
                    p.quote.stock.currency,
                    p.quantity,
                    p.quote.latest_close,
                    p.purchase_price,
                    not p.quote.corporate_action_review,
                )
            ),
        )
        for p in request.positions
    ]
    totals = []
    for currency in ("USD", "PLN"):
        indices = [i for i, p in enumerate(request.positions) if p.quote.stock.currency == currency]
        if not indices:
            continue
        marks = [positions[i].mark for i in indices]
        comparable = all(m.cost is not None for m in marks)
        totals.append(
            CurrencyValue(
                currency=currency,
                value=sum((m.value for m in marks), Decimal(0)),
                cost=sum((m.cost for m in marks if m.cost is not None), Decimal(0))
                if comparable
                else None,
                unrealized_change=sum(
                    (m.unrealized_change for m in marks if m.unrealized_change is not None),
                    Decimal(0),
                )
                if comparable
                else None,
                estimated_cost=any(
                    request.positions[i].price_basis == "reference" for i in indices
                ),
            )
        )
    return ValueResult(positions=positions, totals=totals)
