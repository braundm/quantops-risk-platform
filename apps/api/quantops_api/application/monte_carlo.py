"""Hypothetical correlated buy-and-hold simulation of a validated imported allocation."""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import Field
from quantops_risk.covariance import sample_covariance_matrix

from quantops_api.application.portfolio_risk import RiskRequest, analyze_imported_risk
from quantops_api.application.xtb_models import ReportContract
from quantops_api.infrastructure.monte_carlo import simulate


class MonteCarloRequest(ReportContract):
    portfolio: RiskRequest
    days: int = Field(default=252, ge=1, le=1260, strict=True)
    simulations: int = Field(default=5000, ge=1000, le=50000, strict=True)
    seed: int = Field(default=42, ge=0, le=2**32 - 1, strict=True)
    annual_drift: Annotated[float, Field(ge=-0.2, le=0.2, allow_inf_nan=False)] = 0.0
    allocation: Literal["before", "after"] = "before"


class MonteCarloPoint(ReportContract):
    day: int
    low: Decimal
    median: Decimal
    high: Decimal


class MonteCarloBin(ReportContract):
    low: Decimal
    high: Decimal
    count: int


class MonteCarloResult(ReportContract):
    methodology: str = "correlated-gbm-cpp@1.0.0"
    engine: str = "C++17"
    hypothetical: bool = True
    synthetic_input: bool
    scope: str
    asset_scope: str
    base_currency: str
    valuation_date: date | None
    calibration_start: date
    calibration_end: date
    observations: int
    skipped_pairs: int
    symbols: list[str]
    annual_covariance: list[list[float]]
    days: int
    simulations: int
    seed: int
    annual_drift: float
    confidence: float
    initial_value: Decimal
    probability_of_loss: float
    var_amount: Decimal
    es_amount: Decimal
    mean_terminal: Decimal
    bands: list[MonteCarloPoint]
    sample_paths: list[list[Decimal]]
    histogram: list[MonteCarloBin]
    warnings: list[str]


def money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def analyze_monte_carlo(request: MonteCarloRequest) -> MonteCarloResult:
    portfolio = request.portfolio
    report = analyze_imported_risk(portfolio)
    allocation = report.before if request.allocation == "before" else report.after
    if report.status != "complete" or allocation is None:
        raise ValueError("A complete valued allocation is required; calculate portfolio risk first")
    if "stale_valuation_date" in report.warnings and not all(
        h.origin == "synthetic" for h in portfolio.histories
    ):
        raise ValueError("Refresh the stale portfolio valuation before simulation")
    symbols = sorted(s for s, w in allocation.weights.items() if w > 0)
    if len(symbols) > 20:
        raise ValueError("Monte Carlo supports at most 20 positive-weight positions")
    active = {h.symbol: h for h in portfolio.histories}
    indexed = {
        s: {
            r.date: r
            for r in h.rows
            if (portfolio.start is None or r.date >= portfolio.start)
            and (portfolio.end is None or r.date <= portfolio.end)
        }
        for s, h in active.items()
    }
    cash = f"CASH:{portfolio.base_currency}"
    required = set(symbols) - {cash}
    if not required <= indexed.keys():
        raise ValueError("Dated history for the selected non-cash positions is required")
    calendar_symbols = (
        required or {s for s, w in report.before.weights.items() if w > 0 and s != cash}
        if report.before
        else required
    )
    if not calendar_symbols:
        raise ValueError("Dated history for the selected non-cash positions is required")
    calendars = [set(indexed[s]) for s in sorted(calendar_symbols)]
    common = sorted(set.intersection(*calendars))
    union = sorted(set.union(*calendars))
    union_index = {d: i for i, d in enumerate(union)}
    rows: list[list[float]] = []
    skipped = 0
    for left, right in pairwise(common):
        if union_index[right] != union_index[left] + 1 or (right - left).days > 4:
            skipped += 1
            continue
        values = []
        for symbol in symbols:
            if symbol == cash:
                values.append(0.0)
            else:
                a, b = indexed[symbol][left], indexed[symbol][right]
                values.append(
                    math.log(
                        float(b.adjusted_close * b.fx_to_base / (a.adjusted_close * a.fx_to_base))
                    )
                )
        rows.append(values)
    if len(rows) < 252:
        raise ValueError("At least 252 aligned return observations are required")
    estimate = sample_covariance_matrix(rows)
    if estimate.matrix is None:
        raise ValueError("Cannot estimate a finite covariance matrix")
    covariance = [[float(v) * 252 for v in row] for row in estimate.matrix]
    drifts = [0.0 if s == cash else request.annual_drift for s in symbols]
    summary, bands, paths, terminal = simulate(
        [float(allocation.value * allocation.weights[s]) for s in symbols],
        covariance,
        drifts,
        request.days,
        request.simulations,
        request.seed,
        float(portfolio.confidence),
    )
    lower, upper = terminal[0], terminal[-1]
    width = (upper - lower) / 30 if upper > lower else 1.0
    counts = [0] * 30
    for value in terminal:
        counts[min(29, int((value - lower) / width))] += 1
    warnings = [
        "hypothetical_not_a_forecast",
        "constant_covariance_and_assumed_drift",
        "normal_log_returns_no_jumps_or_volatility_regimes",
        "buy_and_hold_no_rebalancing",
        "costs_taxes_liquidity_inflation_excluded",
        "fx_embedded_in_base_currency_returns_not_separately_simulated",
        "historical_total_return_adjustments_dividends_reinvested_once",
        "pointwise_90_percent_band_not_a_pathwise_interval",
        "signed_losses_negative_values_mean_gains",
        "var_is_not_maximum_loss",
        "monte_carlo_sampling_error_not_parameter_uncertainty",
    ]
    synthetic = any(active[s].origin == "synthetic" for s in calendar_symbols)
    if "stale_valuation_date" in report.warnings:
        warnings.append("stale_synthetic_example_valuation")
    if synthetic:
        warnings.append("synthetic_history")
    return MonteCarloResult(
        synthetic_input=synthetic,
        scope=report.scope,
        asset_scope=report.asset_scope,
        base_currency=report.base_currency,
        valuation_date=report.valuation_date,
        calibration_start=common[0],
        calibration_end=common[-1],
        observations=len(rows),
        skipped_pairs=skipped,
        symbols=symbols,
        annual_covariance=covariance,
        days=request.days,
        simulations=request.simulations,
        seed=request.seed,
        annual_drift=request.annual_drift,
        confidence=float(portfolio.confidence),
        initial_value=money(summary[4]),
        probability_of_loss=summary[0],
        var_amount=money(summary[1]),
        es_amount=money(summary[2]),
        mean_terminal=money(summary[3]),
        bands=[
            MonteCarloPoint(
                day=k * request.days // (len(bands) - 1),
                low=money(b[0]),
                median=money(b[1]),
                high=money(b[2]),
            )
            for k, b in enumerate(bands)
        ],
        sample_paths=[[money(v) for v in path] for path in paths],
        histogram=[
            MonteCarloBin(
                low=money(lower + i * width), high=money(lower + (i + 1) * width), count=count
            )
            for i, count in enumerate(counts)
        ],
        warnings=warnings,
    )
