"""Current-allocation history, drawdown episodes and reconciled risk attribution.

This module consumes already aligned base-currency returns. It neither fetches data
nor reconstructs transactions; callers must distinguish simulation from ledger TWR.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise
from typing import Literal

from .contributions import volatility_contributions
from .correlation import correlation_matrix
from .covariance import sample_covariance_matrix
from .drawdown import maximum_drawdown
from .exceptions import InvalidInputError
from .expected_shortfall import historical_expected_shortfall
from .var import historical_var


@dataclass(frozen=True)
class PerformanceSummary:
    period_return: float | None
    maximum_drawdown: float | None
    current_drawdown: float | None
    peak: date | None
    trough: date | None
    recovery: date | None
    peak_to_trough_days: int | None
    recovery_days: int | None
    worst_month: str | None
    worst_month_return: float | None
    worst_year: str | None
    worst_year_return: float | None
    partial_months: tuple[str, ...]
    partial_years: tuple[str, ...]


def performance_summary(days: list[date], values: list[float]) -> PerformanceSummary:
    """Summarize an investment index, never raw equity distorted by external flows.

    Calendar returns chain observed subperiod returns. Edge months/years are marked
    partial; they are not represented as complete calendar-period observations.
    """
    drawdown = maximum_drawdown(values, days)
    months: dict[str, float] = {}
    years: dict[str, float] = {}
    incomplete_months: set[str] = set()
    incomplete_years: set[str] = set()
    for (previous_day, previous), (day, value) in pairwise(zip(days, values, strict=True)):
        change = value / previous
        month, year = day.isoformat()[:7], str(day.year)
        months[month] = months.get(month, 1.0) * change
        years[year] = years.get(year, 1.0) * change
        if (day - previous_day).days > 7:
            if month != previous_day.isoformat()[:7]:
                incomplete_months.update((month, previous_day.isoformat()[:7]))
            if year != str(previous_day.year):
                incomplete_years.update((year, str(previous_day.year)))
    # A multi-month gap cannot be assigned to its ending calendar month or year.
    for month in incomplete_months:
        months.pop(month, None)
    for year in incomplete_years:
        years.pop(year, None)
    worst_month = min(months, key=lambda key: months[key]) if months else None
    worst_year = min(years, key=lambda key: years[key]) if years else None
    peak = date.fromisoformat(str(drawdown.peak_date)) if drawdown.peak_date else None
    trough = date.fromisoformat(str(drawdown.trough_date)) if drawdown.trough_date else None
    recovery = date.fromisoformat(str(drawdown.recovery_date)) if drawdown.recovery_date else None
    return PerformanceSummary(
        values[-1] / values[0] - 1 if len(values) >= 2 else None,
        drawdown.maximum_drawdown,
        drawdown.drawdowns[-1] if len(values) >= 2 else None,
        peak,
        trough,
        recovery,
        (trough - peak).days if peak and trough else None,
        (recovery - trough).days if recovery and trough else None,
        worst_month,
        months[worst_month] - 1 if worst_month else None,
        worst_year,
        years[worst_year] - 1 if worst_year else None,
        tuple(sorted({days[0].isoformat()[:7], days[-1].isoformat()[:7]} | incomplete_months))
        if days
        else (),
        tuple(sorted({str(days[0].year), str(days[-1].year)} | incomplete_years)) if days else (),
    )


@dataclass(frozen=True)
class AllocationRisk:
    status: Literal["ok", "insufficient_data", "unstable"]
    observations: int
    required_observations: int
    annual_volatility: float | None
    var_fraction: float | None
    es_fraction: float | None
    tail_count: int
    components: dict[str, float]
    risk_shares: dict[str, float | None]
    reconciliation_error: float | None
    correlations: list[list[float | None]]


def allocation_risk(
    symbols: list[str], weights: list[Decimal], rows: list[list[float]], confidence: float
) -> AllocationRisk:
    """Use one common sample for covariance, correlations, VaR and ES.

    Daily current-weight exposures describe present risk. Annualization assumes 252
    common observed sessions. Small samples suppress VaR/ES instead of extrapolating.
    """
    if len(symbols) != len(weights) or len(set(symbols)) != len(symbols):
        raise InvalidInputError("Unique symbols and matching weights are required")
    if any(not weight.is_finite() or weight < 0 for weight in weights) or sum(weights) != 1:
        raise InvalidInputError("Long-only allocation weights must sum exactly to one")
    required = max(252, math.ceil(5 / (1 - confidence)))
    covariance = sample_covariance_matrix(rows)
    if covariance.matrix is None:
        return AllocationRisk(
            "insufficient_data", len(rows), required, None, None, None, 0, {}, {}, None, []
        )
    estimate = volatility_contributions(weights, covariance.matrix, instrument_ids=symbols)
    if not estimate.reconciled:
        raise InvalidInputError("Volatility contributions do not reconcile")
    series = {symbol: [row[i] for row in rows] for i, symbol in enumerate(symbols)}
    correlation = correlation_matrix(series, minimum_observations=2, unstable_below=252)
    returns = [
        sum(float(weight) * value for weight, value in zip(weights, row, strict=True))
        for row in rows
    ]
    enough = len(rows) >= required
    var = historical_var(returns, confidence_level=confidence) if enough else None
    es = historical_expected_shortfall(returns, confidence_level=confidence) if enough else None
    scale = math.sqrt(252)
    return AllocationRisk(
        "insufficient_data"
        if not enough
        else "unstable"
        if es and es.tail_observation_count < 5
        else "ok",
        len(rows),
        required,
        estimate.portfolio_volatility * scale,
        var.value if var else None,
        es.value if es else None,
        es.tail_observation_count if es else 0,
        {
            item.instrument_id: item.component_contribution * scale
            for item in estimate.contributions
        },
        {
            item.instrument_id: item.percentage_contribution
            if estimate.portfolio_volatility
            else None
            for item in estimate.contributions
        },
        estimate.reconciliation_difference * scale,
        # Correlation utility sorts identifiers; preserve the requested position order.
        [
            [
                correlation.matrix[correlation.instrument_ids.index(a)][
                    correlation.instrument_ids.index(b)
                ]
                for b in symbols
            ]
            for a in symbols
        ],
    )


def compound_shock(value: Decimal, price_shock: Decimal, fx_shock: Decimal) -> Decimal:
    """Price and FX changes multiply; the cross term is retained exactly."""
    if any(not x.is_finite() or x <= -1 or x > 5 for x in (price_shock, fx_shock)):
        raise InvalidInputError("Shocks must lie in (-1, 5]")
    return value * ((1 + price_shock) * (1 + fx_shock) - 1)
