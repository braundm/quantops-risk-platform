"""Bounded, stateless Treasury research and simplified liquidity analysis."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import Field, field_validator, model_validator
from quantops_domain import Currency
from quantops_risk.liquidity import LiquidityEstimate, estimate_liquidity
from quantops_risk.treasury import (
    VERSION,
    BondSensitivity,
    BondTerms,
    bond_sensitivity,
    shocked_bond_price,
)

from quantops_api.api.dependencies import require_expensive_capacity
from quantops_api.api.retail import Contract, Nonnegative, Positive

router = APIRouter(prefix="/api/v1/treasury", tags=["Treasury research"])
Rate = Annotated[Decimal, Field(ge="-0.1", le=1, allow_inf_nan=False, decimal_places=8)]
Quantity = Annotated[
    Decimal, Field(ge="-1000000000", le="1000000000", allow_inf_nan=False, decimal_places=8)
]


class TreasuryBond(Contract):
    id: UUID
    name: str = Field(min_length=1, max_length=80)
    face: Annotated[Decimal, Field(gt=0, le="1000000000000", allow_inf_nan=False, decimal_places=8)]
    quantity: Quantity
    coupon_rate: Annotated[Decimal, Field(ge=0, le="0.5", allow_inf_nan=False, decimal_places=8)]
    yield_rate: Rate
    years: int = Field(ge=1, le=50, strict=True)
    frequency: Literal[1, 2, 4, 12]

    @field_validator("quantity")
    @classmethod
    def nonzero(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError(
                "Quantity must be nonzero; negative quantity represents a short position"
            )
        return value

    def terms(self) -> BondTerms:
        return BondTerms(self.face, self.coupon_rate, self.yield_rate, self.years, self.frequency)


class VolumeSession(Contract):
    date: date
    volume: Nonnegative


class LiquidityPosition(Contract):
    id: UUID
    name: str = Field(min_length=1, max_length=80)
    quantity: Positive
    reference_price: Positive
    price_date: date
    sessions: list[VolumeSession] = Field(max_length=252)


class TreasuryRequest(Contract):
    currency: str
    valuation_date: date
    origin: Literal["synthetic", "user_supplied"]
    source_note: str = Field(min_length=1, max_length=500)
    bonds: list[TreasuryBond] = Field(min_length=1, max_length=30)
    liquidity_positions: list[LiquidityPosition] = Field(default_factory=list, max_length=30)
    participation: Annotated[
        Decimal, Field(ge="0.01", le="0.2", allow_inf_nan=False, decimal_places=4)
    ] = Decimal("0.1")
    max_abs_dv01: Nonnegative | None = None
    max_liquidation_days: int = Field(default=5, ge=1, le=252)

    @field_validator("currency")
    @classmethod
    def iso_currency(cls, value: str) -> str:
        return Currency(value).code

    @model_validator(mode="after")
    def valid_history(self) -> Self:
        if self.valuation_date > datetime.now(UTC).date():
            raise ValueError("Valuation date cannot be in the future")
        ids = [b.id for b in self.bonds] + [p.id for p in self.liquidity_positions]
        if len(ids) != len(set(ids)):
            raise ValueError("Position identifiers must be unique")
        for position in self.liquidity_positions:
            dates = [session.date for session in position.sessions]
            if dates != sorted(set(dates)):
                raise ValueError("Volume sessions must be unique and chronological")
            if (
                any(d > self.valuation_date for d in dates)
                or position.price_date > self.valuation_date
            ):
                raise ValueError("Price and volume dates must not follow valuation")
        return self


class BondResult(Contract):
    id: UUID
    name: str
    quantity: Decimal
    metrics: BondSensitivity
    value: Decimal
    signed_dv01: Decimal


class RateScenario(Contract):
    shock_bp: int
    before: Decimal
    after: Decimal
    pnl: Decimal
    pnl_by_position: dict[UUID, Decimal]


class LiquidityResult(Contract):
    id: UUID
    name: str
    estimate: LiquidityEstimate
    status: Literal["valid", "stale", "insufficient"]
    limit_status: Literal["OK", "WARNING", "BREACH", "INSUFFICIENT"]
    first_date: date | None
    last_date: date | None


class TreasuryResult(Contract):
    methodology_version: str = VERSION
    generated_at: datetime
    currency: str
    valuation_date: date
    origin: Literal["synthetic", "user_supplied"]
    source_note: str
    bonds: list[BondResult]
    net_value: Decimal
    gross_value: Decimal
    signed_dv01: Decimal
    gross_dv01: Decimal
    dv01_limit_status: Literal["OK", "WARNING", "BREACH", "NOT_SET"]
    scenarios: list[RateScenario]
    liquidity: list[LiquidityResult]
    liquidity_coverage_pct: Decimal | None
    liquidatable_one_day_pct: Decimal | None
    liquidatable_five_days_pct: Decimal | None
    assumptions: list[str]
    inputs: TreasuryRequest


ASSUMPTIONS = [
    "All inputs are synthetic or user supplied and have not been verified against a provider.",
    "Single-currency, regular bullet bonds at a coupon boundary; "
    "nominal annual yield compounded at coupon frequency.",
    "Whole remaining years; price is per face amount. No accrued interest, calendar/day-count "
    "conventions, credit/default, embedded options or curve shape.",
    "DV01 is the analytic first-order loss magnitude for +1bp; portfolio DV01 is signed by "
    "quantity. Rate scenarios use full repricing.",
    "Liquidity is a separate long-only book, not included in bond value or DV01. "
    "At least 20 supplied volume sessions are required.",
    "ADV uses all supplied sessions including zeros; completeness of the trading calendar "
    "is not verified. Seven-calendar-day age threshold is relative to valuation date.",
    "Liquidation assumes constant ADV and participation, with no market impact, spreads "
    "or changing prices. Stale/insufficient rows are excluded from coverage.",
    "This is educational Treasury sensitivity research, not regulatory IRRBB, LCR or NSFR "
    "compliance. No NII or bank-wide EVE is calculated.",
]


def analyze(request: TreasuryRequest) -> TreasuryResult:
    bonds = []
    for bond in request.bonds:
        metrics = bond_sensitivity(bond.terms())
        bonds.append(
            BondResult(
                id=bond.id,
                name=bond.name,
                quantity=bond.quantity,
                metrics=metrics,
                value=metrics.price * bond.quantity,
                signed_dv01=metrics.dv01 * bond.quantity,
            )
        )
    net = sum((b.value for b in bonds), Decimal(0))
    dv01 = sum((b.signed_dv01 for b in bonds), Decimal(0))
    limit = request.max_abs_dv01
    limit_status: Literal["OK", "WARNING", "BREACH", "NOT_SET"] = "NOT_SET"
    if limit is not None:
        limit_status = (
            "BREACH"
            if abs(dv01) > limit
            else "WARNING"
            if abs(dv01) >= limit * Decimal("0.8")
            else "OK"
        )
    scenarios = []
    for shock in (-100, -50, 50, 100, 200):
        changes = {
            b.id: shocked_bond_price(b.terms(), shock) * b.quantity - r.value
            for b, r in zip(request.bonds, bonds, strict=True)
        }
        pnl = sum(changes.values(), Decimal(0))
        scenarios.append(
            RateScenario(
                shock_bp=shock, before=net, after=net + pnl, pnl=pnl, pnl_by_position=changes
            )
        )
    liquidity = []
    total = covered = one_day = five_days = Decimal(0)
    for position in request.liquidity_positions:
        estimate = estimate_liquidity(
            position.quantity, tuple(s.volume for s in position.sessions), request.participation
        )
        first = position.sessions[0].date if position.sessions else None
        last = position.sessions[-1].date if position.sessions else None
        stale = (request.valuation_date - position.price_date).days > 7 or (
            last is not None and (request.valuation_date - last).days > 7
        )
        status: Literal["valid", "stale", "insufficient"] = (
            "insufficient" if estimate.status == "insufficient" else "stale" if stale else "valid"
        )
        state: Literal["OK", "WARNING", "BREACH", "INSUFFICIENT"] = "INSUFFICIENT"
        value = position.quantity * position.reference_price
        total += value
        if status == "valid" and estimate.days is not None:
            state = (
                "BREACH"
                if estimate.days > request.max_liquidation_days
                else "WARNING"
                if estimate.days == request.max_liquidation_days
                else "OK"
            )
            covered += value
            one_day += value * (estimate.fraction_one_day or Decimal(0))
            five_days += value * (estimate.fraction_five_days or Decimal(0))
        liquidity.append(
            LiquidityResult(
                id=position.id,
                name=position.name,
                estimate=estimate,
                status=status,
                limit_status=state,
                first_date=first,
                last_date=last,
            )
        )
    # Whole-book estimates are withheld when even one position has unusable data.
    complete = total > 0 and covered == total
    return TreasuryResult(
        generated_at=datetime.now(UTC),
        currency=request.currency,
        valuation_date=request.valuation_date,
        origin=request.origin,
        source_note=request.source_note,
        bonds=bonds,
        net_value=net,
        gross_value=sum((abs(b.value) for b in bonds), Decimal(0)),
        signed_dv01=dv01,
        gross_dv01=sum((abs(b.signed_dv01) for b in bonds), Decimal(0)),
        dv01_limit_status=limit_status,
        scenarios=scenarios,
        liquidity=liquidity,
        liquidity_coverage_pct=covered / total * 100 if total else None,
        liquidatable_one_day_pct=one_day / total * 100 if complete else None,
        liquidatable_five_days_pct=five_days / total * 100 if complete else None,
        assumptions=ASSUMPTIONS,
        inputs=request,
    )


@router.post(
    "/analyze", response_model=TreasuryResult, dependencies=[Depends(require_expensive_capacity)]
)
def analyze_treasury(request: TreasuryRequest) -> TreasuryResult:
    return analyze(request)


@router.post(
    "/report", response_class=HTMLResponse, dependencies=[Depends(require_expensive_capacity)]
)
def treasury_report(request: TreasuryRequest) -> HTMLResponse:
    from quantops_api.application.treasury_report import render_report

    return HTMLResponse(
        render_report(analyze(request)),
        headers={
            "Content-Disposition": 'attachment; filename="quantops-treasury-report.html"',
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )
