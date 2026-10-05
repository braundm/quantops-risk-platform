"""Deterministic PLN ledger, fixed-position risk and transparent linear derivative models."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise
from statistics import covariance, stdev, variance
from typing import Literal

from .correlation import correlation_matrix
from .exceptions import InvalidInputError
from .expected_shortfall import historical_expected_shortfall
from .var import historical_var

D = Decimal
ZERO = Decimal(0)
Kind = Literal["equity", "etf", "forex", "future"]
Action = Literal["buy", "sell", "deposit", "withdrawal", "dividend", "fee"]


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    kind: Kind
    sector: str
    multiplier: Decimal
    margin_rate: Decimal
    expiry: date | None = None


@dataclass(frozen=True)
class Entry:
    id: str
    day: date
    action: Action
    symbol: str = ""
    quantity: Decimal = ZERO
    price: Decimal = ZERO
    amount_pln: Decimal = ZERO
    fee_pln: Decimal = ZERO


@dataclass
class Lot:
    quantity: Decimal = ZERO
    average: Decimal = ZERO
    invested_pln: Decimal = ZERO
    opened: date | None = None


@dataclass(frozen=True)
class Position:
    symbol: str
    name: str
    kind: Kind
    sector: str
    quantity: Decimal
    average_price: Decimal
    price: Decimal
    opened: date
    holding_days: int
    value: Decimal
    notional: Decimal
    unrealized_pnl: Decimal
    margin: Decimal
    weight: float
    expiry: date | None


@dataclass(frozen=True)
class CurvePoint:
    day: date
    equity: Decimal
    net_deposits: Decimal
    profit: Decimal
    return_index: float | None
    drawdown: float | None


@dataclass(frozen=True)
class MarketPoint:
    symbol: str
    name: str
    period_return: float
    annual_volatility: float
    risk_contribution: float | None


@dataclass(frozen=True)
class BookResult:
    model_version: str
    as_of: date
    equity: Decimal
    cash: Decimal
    net_deposits: Decimal
    profit: Decimal
    fees: Decimal
    dividends: Decimal
    realized_pnl: Decimal
    gross_exposure: Decimal
    leverage: float | None
    margin_estimate: Decimal
    cash_after_margin: Decimal
    twr: float | None
    max_drawdown: float | None
    effective_positions: float | None
    top_weight: float | None
    risk_status: Literal["ok", "insufficient_data", "invalid_data"]
    var95: float | None
    es95: float | None
    annual_volatility: float | None
    observations: int
    positions: list[Position]
    curve: list[CurvePoint]
    market_points: list[MarketPoint]
    correlation_symbols: list[str]
    correlations: list[list[float | None]]
    warnings: list[str]


def analyze_book(
    instruments: Sequence[Instrument],
    entries: Sequence[Entry],
    prices: Mapping[str, Mapping[date, Decimal]],
    fx: Mapping[date, Decimal],
    as_of: date,
) -> BookResult:
    """Replay close-of-day entries; cash is PLN and conversions use the dated USD/PLN reference.

    Spot purchases reduce cash. Derivative opening notional never reduces NAV; cumulative P&L
    is converted at the valuation FX. Closing realizes it once into PLN cash. Margin is reserved
    cash, not a second NAV deduction. Funding, daily variation cashflows and tax are excluded.
    """
    catalog = {i.symbol: i for i in instruments}
    if len({e.id for e in entries}) != len(entries):
        raise InvalidInputError("Duplicate transaction ID; imports must be idempotent")
    for instrument in instruments:
        if instrument.multiplier <= 0 or not 0 <= instrument.margin_rate <= 1:
            raise InvalidInputError("Invalid multiplier or margin assumption")
    symbols = sorted({e.symbol for e in entries if e.action in {"buy", "sell"}})
    if any(symbol not in catalog or symbol not in prices for symbol in symbols):
        raise InvalidInputError("Unknown instrument or missing prices")
    if any(v <= 0 or not v.is_finite() for v in fx.values()):
        raise InvalidInputError("FX must be finite and positive")
    calendars = [set(fx)] + [set(prices[s]) for s in symbols]
    days = sorted(day for day in set.intersection(*calendars) if day <= as_of)
    if not days or days[-1] != as_of:
        raise InvalidInputError("No aligned price/FX data on the valuation date")
    allowed = set(days)
    for entry in entries:
        if entry.day not in allowed:
            raise InvalidInputError(f"No common market close for transaction date {entry.day}")
        if entry.fee_pln < 0 or entry.amount_pln < 0:
            raise InvalidInputError("Use positive fee and cash amounts")
        if entry.action in {"buy", "sell"}:
            instrument = catalog[entry.symbol]
            if entry.quantity <= 0 or (entry.price <= 0 and instrument.kind != "future"):
                raise InvalidInputError("Invalid execution quantity or price")
            if instrument.kind == "future" and entry.quantity != entry.quantity.to_integral_value():
                raise InvalidInputError("Futures require whole contracts")
            if instrument.expiry is not None and entry.day >= instrument.expiry:
                raise InvalidInputError("Expired futures cannot receive new ledger trades")
    grouped: dict[date, list[Entry]] = {}
    for entry in entries:
        grouped.setdefault(entry.day, []).append(entry)
    lots = {symbol: Lot() for symbol in symbols}
    cash, deposits, fees, dividends, realized = (D(0) for _ in range(5))
    curve: list[CurvePoint] = []
    previous: Decimal | None = None
    index, peak = 1.0, 1.0
    valid_twr = True
    first = min((e.day for e in entries), default=as_of)
    for day in days:
        if day < first:
            continue
        flow = D(0)
        rate = fx[day]
        for entry in grouped.get(day, []):
            fees += entry.fee_pln
            cash -= entry.fee_pln
            if entry.action == "deposit":
                cash += entry.amount_pln
                deposits += entry.amount_pln
                flow += entry.amount_pln
            elif entry.action == "withdrawal":
                cash -= entry.amount_pln
                deposits -= entry.amount_pln
                flow -= entry.amount_pln
            elif entry.action == "fee":
                cash -= entry.amount_pln
                fees += entry.amount_pln
            elif entry.action == "dividend":
                if entry.symbol not in lots or lots[entry.symbol].quantity <= 0:
                    raise InvalidInputError("A dividend requires an existing long position")
                cash += entry.amount_pln
                dividends += entry.amount_pln
            else:
                instrument, lot = catalog[entry.symbol], lots[entry.symbol]
                delta = entry.quantity * (1 if entry.action == "buy" else -1)
                old = lot.quantity
                spot = instrument.kind in {"equity", "etf"}
                if spot and old + delta < 0:
                    raise InvalidInputError(
                        "Spot sale exceeds holdings; cash-account shorting is unsupported"
                    )
                if spot:
                    cost = entry.quantity * entry.price * rate
                    cash -= delta * entry.price * rate
                    if delta > 0:
                        lot.invested_pln += cost
                    else:
                        removed_cost = lot.invested_pln * entry.quantity / old
                        realized += cost - removed_cost
                        lot.invested_pln -= removed_cost
                elif old * delta < 0:
                    closed = min(abs(old), abs(delta))
                    pnl = (
                        closed
                        * (1 if old > 0 else -1)
                        * instrument.multiplier
                        * (entry.price - lot.average)
                        * rate
                    )
                    cash += pnl
                    realized += pnl
                if old == 0 or old * delta > 0:
                    lot.average = (abs(old) * lot.average + abs(delta) * entry.price) / (
                        abs(old) + abs(delta)
                    )
                    if old == 0:
                        lot.opened = day
                elif abs(delta) > abs(old):
                    lot.average, lot.opened = entry.price, day
                lot.quantity += delta
                if lot.quantity == 0:
                    lot.average, lot.invested_pln, lot.opened = D(0), D(0), None
        equity = cash
        for symbol, lot in lots.items():
            instrument = catalog[symbol]
            if instrument.kind in {"equity", "etf"}:
                equity += lot.quantity * prices[symbol][day] * rate
            else:
                equity += (
                    lot.quantity
                    * instrument.multiplier
                    * (prices[symbol][day] - lot.average)
                    * rate
                )
        if previous is None:
            if flow > 0 and equity > 0:
                index = float(equity / flow)
            elif entries:
                valid_twr = False
        elif previous > 0 and equity - flow > 0:
            index *= float((equity - flow) / previous)
        else:
            valid_twr = False
        peak = max(peak, index)
        curve.append(
            CurvePoint(
                day,
                equity,
                deposits,
                equity - deposits,
                index if valid_twr else None,
                index / peak - 1 if valid_twr else None,
            )
        )
        previous = equity
    equity = curve[-1].equity
    current_fx = fx[as_of]
    notionals = {
        s: abs(lot.quantity * catalog[s].multiplier * prices[s][as_of] * current_fx)
        for s, lot in lots.items()
        if lot.quantity
    }
    gross = sum(notionals.values(), D(0))
    positions = []
    for symbol, notional in notionals.items():
        instrument, lot = catalog[symbol], lots[symbol]
        spot = instrument.kind in {"equity", "etf"}
        value = (
            lot.quantity
            * (
                prices[symbol][as_of]
                if spot
                else instrument.multiplier * (prices[symbol][as_of] - lot.average)
            )
            * current_fx
        )
        assert lot.opened is not None
        positions.append(
            Position(
                symbol,
                instrument.name,
                instrument.kind,
                instrument.sector,
                lot.quantity,
                lot.average,
                prices[symbol][as_of],
                lot.opened,
                (as_of - lot.opened).days,
                value,
                notional,
                value - lot.invested_pln if spot else value,
                D(0) if spot else notional * instrument.margin_rate,
                float(notional / gross) if gross else 0,
                instrument.expiry,
            )
        )
    active = sorted(notionals)
    risk_days = days[-253:]
    pnl_series: dict[str, list[float]] = {}
    price_returns: dict[str, list[float]] = {}
    for symbol in active:
        instrument, lot = catalog[symbol], lots[symbol]
        spot = instrument.kind in {"equity", "etf"}
        pnl_series[symbol] = [
            float(
                lot.quantity
                * instrument.multiplier
                * (
                    (prices[symbol][b] * fx[b] - prices[symbol][a] * fx[a])
                    if spot
                    else (prices[symbol][b] - prices[symbol][a]) * fx[b]
                )
            )
            for a, b in pairwise(risk_days)
        ]
        if all(prices[symbol][day] > 0 for day in risk_days):
            price_returns[symbol] = [
                float(
                    (prices[symbol][b] * (fx[b] if spot else 1))
                    / (prices[symbol][a] * (fx[a] if spot else 1))
                    - 1
                )
                for a, b in pairwise(risk_days)
            ]
    count = len(risk_days) - 1 if active else 0
    total_pnl = [sum(pnl_series[s][i] for s in active) for i in range(count)]
    status: Literal["ok", "insufficient_data", "invalid_data"] = (
        "invalid_data" if equity <= 0 else "ok" if count >= 252 else "insufficient_data"
    )
    var95 = es95 = volatility = None
    market_points: list[MarketPoint] = []
    if status == "ok":
        returns = [p / float(equity) for p in total_pnl]
        var95 = historical_var(returns, portfolio_value=float(equity)).require_value()
        es95 = historical_expected_shortfall(returns, portfolio_value=float(equity)).require_value()
        volatility = stdev(returns) * math.sqrt(252)
    total_variance = variance(total_pnl) if count > 1 else 0
    for symbol, returns in price_returns.items():
        if len(returns) < 60:
            continue
        market_points.append(
            MarketPoint(
                symbol,
                catalog[symbol].name,
                math.prod(1 + r for r in returns) - 1,
                stdev(returns) * math.sqrt(252),
                covariance(pnl_series[symbol], total_pnl) / total_variance
                if total_variance > 0
                else None,
            )
        )
    correlation = (
        correlation_matrix(price_returns, minimum_observations=60, unstable_below=252)
        if price_returns
        else None
    )
    margin = sum((p.margin for p in positions), D(0))
    warnings = [
        "fictional_or_user_ledger",
        "reference_closes_not_execution_quotes",
        "daily_fx_not_synchronous",
        "unadjusted_prices_dividends_only_if_entered",
        "no_etf_lookthrough",
        "historical_risk_not_forecast",
        "margin_is_user_assumption",
        "derivative_funding_and_daily_settlement_excluded",
    ]
    if cash < 0:
        warnings.append("negative_cash_unmodelled_financing")
    if cash - margin < 0:
        warnings.append("cash_below_margin_assumption")
    if any(i.expiry is not None and as_of >= i.expiry for i in instruments if i.symbol in active):
        raise InvalidInputError(
            "An open futures position has expired; record its close before valuation"
        )
    if len(days) < len({day for calendar in calendars for day in calendar if day <= as_of}):
        warnings.append("only_common_dates_no_fill")
    return BookResult(
        "investor-book@1.0.0",
        as_of,
        equity,
        cash,
        deposits,
        equity - deposits,
        fees,
        dividends,
        realized,
        gross,
        float(gross / equity) if equity > 0 else None,
        margin,
        cash - margin,
        index - 1 if valid_twr else None,
        min((p.drawdown for p in curve if p.drawdown is not None), default=None)
        if valid_twr
        else None,
        1 / sum(p.weight**2 for p in positions) if gross else None,
        max((p.weight for p in positions), default=None),
        status,
        var95,
        es95,
        volatility,
        count,
        positions,
        curve,
        market_points,
        list(correlation.instrument_ids) if correlation else [],
        [list(row) for row in correlation.matrix] if correlation else [],
        warnings,
    )


@dataclass(frozen=True)
class StressResult:
    pnl: Decimal
    equity_after: Decimal
    loss_fraction: float | None
    impacts: dict[str, Decimal]


def stress_book(
    result: BookResult,
    instruments: Sequence[Instrument],
    usd_pln: Decimal,
    price_shock: Decimal,
    fx_shock: Decimal,
    oil_shock: Decimal,
    forex_shock: Decimal,
) -> StressResult:
    """Terminal mark changes; cash is PLN, no execution, funding or probability claim."""
    if any(
        not x.is_finite() or x <= -1 or x > 5
        for x in (price_shock, fx_shock, oil_shock, forex_shock)
    ):
        raise InvalidInputError("Scenario shocks must be finite and between -100% and +500%")
    catalog = {i.symbol: i for i in instruments}
    impacts = {}
    for p in result.positions:
        shock = (
            oil_shock if p.kind == "future" else forex_shock if p.kind == "forex" else price_shock
        )
        terminal = p.price * (1 + shock)
        if p.kind in {"equity", "etf"}:
            stressed = p.quantity * terminal * usd_pln * (1 + fx_shock)
        else:
            stressed = (
                p.quantity
                * catalog[p.symbol].multiplier
                * (terminal - p.average_price)
                * usd_pln
                * (1 + fx_shock)
            )
        impacts[p.symbol] = stressed - p.value
    pnl = sum(impacts.values(), D(0))
    return StressResult(
        pnl,
        result.equity + pnl,
        float(-pnl / result.equity) if result.equity > 0 else None,
        impacts,
    )
