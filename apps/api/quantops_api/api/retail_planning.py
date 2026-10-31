"""User-defined cost budgets and explanation preferences, without suitability advice."""

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import Field

from quantops_api.api.retail import Contract, Nonnegative


class CostItem(Contract):
    id: UUID
    category: Literal[
        "commission",
        "spread",
        "conversion",
        "financing",
        "product",
        "slippage",
        "hedge",
        "rebalance",
    ]
    amount: Nonnegative
    frequency: Literal["one_off", "monthly", "annual"]
    source: Literal["actual", "estimated", "user"]
    included_in_prices: bool = False


class CostBudget(Contract):
    items: list[CostItem] = Field(max_length=200)


class CostSummary(Contract):
    one_off: Decimal
    recurring_annual: Decimal
    excluded_from_total: list[UUID]
    model_version: str = "cost-budget@1.0.0"


class Preferences(Contract):
    equity: Nonnegative
    cash: Annotated[Decimal, Field(allow_inf_nan=False)]
    horizon_months: int = Field(ge=1, le=1200)
    goal: str = Field(max_length=300)
    monthly_inflow: Nonnegative
    monthly_outflow: Nonnegative
    liquidity_reserve: Nonnegative
    willingness_fraction: Annotated[Decimal, Field(ge=0, le=1)]
    willingness_amount: Nonnegative
    loss_capacity: Nonnegative
    concentration_limit: Annotated[Decimal, Field(ge=0, le=1)]
    asset_experience: dict[
        Literal["equity", "etf", "bonds", "forex", "options"],
        Literal["none", "basic", "experienced"],
    ]
    understands_leverage: bool
    understands_margin: bool
    constraints: str = Field(max_length=2000)


class PreferenceReview(Contract):
    willingness_amount_from_fraction: Decimal
    capacity_fraction: Decimal | None
    flags: list[str]
    model_version: str = "explanation-preferences@1.0.0"


router = APIRouter(prefix="/api/v1/retail", tags=["User assumptions and cost budgets"])


@router.post("/cost-budget", response_model=CostSummary)
def cost_budget(request: CostBudget) -> CostSummary:
    if len({item.id for item in request.items}) != len(request.items):
        from quantops_risk.exceptions import InvalidInputError

        raise InvalidInputError("cost item IDs must be unique")
    included = [item for item in request.items if not item.included_in_prices]
    return CostSummary(
        one_off=sum((item.amount for item in included if item.frequency == "one_off"), Decimal(0)),
        recurring_annual=sum(
            (
                item.amount * (12 if item.frequency == "monthly" else 1)
                for item in included
                if item.frequency != "one_off"
            ),
            Decimal(0),
        ),
        excluded_from_total=[item.id for item in request.items if item.included_in_prices],
    )


@router.post("/preferences", response_model=PreferenceReview)
def review_preferences(request: Preferences) -> PreferenceReview:
    amount = request.equity * request.willingness_fraction
    flags: list[str] = []
    if abs(amount - request.willingness_amount) > max(Decimal(1), amount * Decimal("0.01")):
        flags.append("inconsistent_loss_answers")
    if max(amount, request.willingness_amount) > request.loss_capacity:
        flags.append("willingness_exceeds_capacity")
    if request.liquidity_reserve > request.cash:
        flags.append("cash_below_liquidity_reserve")
    if request.monthly_outflow > request.monthly_inflow and request.horizon_months <= 12:
        flags.append("near_term_net_withdrawals")
    if not request.understands_leverage or not request.understands_margin:
        flags.append("explain_leverage_and_margin")
    return PreferenceReview(
        willingness_amount_from_fraction=amount,
        capacity_fraction=request.loss_capacity / request.equity if request.equity > 0 else None,
        flags=flags,
    )
