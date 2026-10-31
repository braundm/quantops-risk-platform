"""Versioned, descriptive diagnostics for fully funded long equity allocations.

The score is an explicit research heuristic, not a calibrated loss probability,
suitability assessment, credit rating, or guarantee of capital preservation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise
from statistics import stdev
from typing import Literal

from .exceptions import InvalidInputError
from .portfolio_history import AllocationRisk, PerformanceSummary

DIAGNOSTICS_VERSION = "equity-diagnostics@1.0.0"
MINIMUM_SCORE_OBSERVATIONS = 252


@dataclass(frozen=True)
class ConcentrationDiagnostics:
    positions: int
    groups: int
    largest: Decimal
    top_three: Decimal
    top_five: Decimal
    hhi: Decimal
    effective_positions: Decimal
    issuer_identity_coverage: Decimal


@dataclass(frozen=True)
class ScoreComponent:
    key: str
    value: float | None
    score: float | None
    weight: float
    lower_anchor: float
    upper_anchor: float


@dataclass(frozen=True)
class EquityRiskScore:
    status: Literal["available", "insufficient_data", "stale_valuation", "outside_equity_scope"]
    value: int | None
    band: Literal["lower", "moderate", "elevated", "high"] | None
    minimum_observations: int
    components: list[ScoreComponent]


@dataclass(frozen=True)
class CorrelationPair:
    left: str
    right: str
    correlation: float
    combined_weight: Decimal


@dataclass(frozen=True)
class PositionStress:
    symbol: str
    shock: Decimal
    pnl: Decimal
    portfolio_fraction: Decimal
    value_after: Decimal


@dataclass(frozen=True)
class EquityDiagnostics:
    methodology: str
    concentration: ConcentrationDiagnostics
    score: EquityRiskScore
    weighted_correlation: float | None
    strongest_pairs: list[CorrelationPair]
    diversification_ratio: float | None
    position_volatilities: dict[str, float | None]
    single_position_stress: list[PositionStress]
    drawdown_curve: list[tuple[date, float]]


def concentration_diagnostics(
    weights: Mapping[str, Decimal], issuer_ids: Mapping[str, str | None]
) -> ConcentrationDiagnostics:
    """Aggregate documented issuer identities; never infer identities from ticker names."""
    if not weights or any(not w.is_finite() or w < 0 for w in weights.values()):
        raise InvalidInputError("Finite nonnegative weights are required")
    if abs(sum(weights.values(), Decimal(0)) - 1) > Decimal("1e-24"):
        raise InvalidInputError("Diagnostic weights must sum to one")
    groups: dict[tuple[str, str], Decimal] = {}
    coverage = Decimal(0)
    positive = {s: w for s, w in weights.items() if w > 0}
    for symbol, weight in positive.items():
        issuer = issuer_ids.get(symbol)
        key = ("issuer", issuer) if issuer else ("listing", symbol)
        groups[key] = groups.get(key, Decimal(0)) + weight
        if issuer:
            coverage += weight
    ordered = sorted(groups.values(), reverse=True)
    hhi = sum((w * w for w in ordered), Decimal(0))
    return ConcentrationDiagnostics(
        len(positive),
        len(groups),
        ordered[0],
        sum(ordered[:3], Decimal(0)),
        sum(ordered[:5], Decimal(0)),
        hhi,
        Decimal(1) / hhi,
        coverage,
    )


def equity_diagnostics(
    *,
    symbols: list[str],
    weights: dict[str, Decimal],
    issuer_ids: dict[str, str | None],
    daily_rows: list[list[float]],
    risk: AllocationRisk,
    performance: PerformanceSummary,
    curve: list[tuple[date, Decimal]],
    capital: Decimal,
    equity_symbols: set[str],
    stale_valuation: bool,
) -> EquityDiagnostics:
    """Compose concentration, covariance diagnostics, fixed shocks and a bounded score."""
    if set(symbols) != set(weights) or len(symbols) != len(set(symbols)):
        raise InvalidInputError("Unique diagnostic symbols must match the weights")
    if any(
        len(row) != len(symbols) or any(not math.isfinite(x) for x in row) for row in daily_rows
    ):
        raise InvalidInputError("Diagnostic returns must be finite with matching columns")
    if not capital.is_finite() or capital <= 0:
        raise InvalidInputError("Diagnostic capital must be positive and finite")
    if any(not value.is_finite() or value <= 0 for _, value in curve):
        raise InvalidInputError("Diagnostic curve values must be positive and finite")
    if any(a[0] >= b[0] for a, b in pairwise(curve)):
        raise InvalidInputError("Diagnostic curve dates must be strictly increasing")
    concentration = concentration_diagnostics(weights, issuer_ids)
    active = {s for s in symbols if weights[s] > 0}
    eligible = active <= equity_symbols
    measures = (
        ("largest_position", float(concentration.largest), 0.05, 0.50),
        ("hhi", float(concentration.hhi), 0.05, 0.50),
        ("annual_volatility", risk.annual_volatility, 0.10, 0.60),
        ("maximum_drawdown", performance.maximum_drawdown, 0.05, 0.60),
    )
    if any(v is not None and (not math.isfinite(v) or v < 0) for _, v, _, _ in measures):
        raise InvalidInputError("Diagnostic risk measures must be finite and nonnegative")
    components = [
        ScoreComponent(
            key,
            value,
            max(0.0, min(100.0, (value - lo) / (hi - lo) * 100)) if value is not None else None,
            0.25,
            lo,
            hi,
        )
        for key, value, lo, hi in measures
    ]
    status: Literal["available", "insufficient_data", "stale_valuation", "outside_equity_scope"]
    status = (
        "outside_equity_scope"
        if not eligible
        else "stale_valuation"
        if stale_valuation
        else "insufficient_data"
        if len(daily_rows) < MINIMUM_SCORE_OBSERVATIONS or any(c.score is None for c in components)
        else "available"
    )
    score = (
        int(
            sum(
                (Decimal(str(c.score)) * Decimal(str(c.weight)) for c in components), Decimal(0)
            ).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        )
        if status == "available"
        else None
    )
    band: Literal["lower", "moderate", "elevated", "high"] | None = (
        None
        if score is None
        else "lower"
        if score < 25
        else "moderate"
        if score < 50
        else "elevated"
        if score < 75
        else "high"
    )
    volatilities = {
        symbol: stdev(row[i] for row in daily_rows) * math.sqrt(252)
        if len(daily_rows) >= 2
        else None
        for i, symbol in enumerate(symbols)
    }
    pairs: list[CorrelationPair] = []
    for i, left in enumerate(symbols):
        for j in range(i + 1, len(symbols)):
            right = symbols[j]
            correlation = risk.correlations[i][j] if risk.correlations else None
            if left in active and right in active and correlation is not None:
                pairs.append(
                    CorrelationPair(left, right, correlation, weights[left] + weights[right])
                )
    denominator = sum((weights[p.left] * weights[p.right] for p in pairs), Decimal(0))
    weighted_correlation = (
        sum(float(weights[p.left] * weights[p.right]) * p.correlation for p in pairs)
        / float(denominator)
        if denominator
        else None
    )
    diversification_ratio = (
        sum(float(weights[s]) * (volatilities[s] or 0) for s in symbols) / risk.annual_volatility
        if risk.annual_volatility and all(v is not None for v in volatilities.values())
        else None
    )
    stresses = [
        PositionStress(
            s,
            Decimal("-0.5"),
            -capital * weights[s] / 2,
            -weights[s] / 2,
            capital * (1 - weights[s] / 2),
        )
        for s in symbols
        if s in active and s in equity_symbols
    ]
    drawdowns: list[tuple[date, float]] = []
    peak = Decimal(0)
    for day, value in curve:
        peak = max(peak, value)
        drawdowns.append((day, float(value / peak - 1)))
    return EquityDiagnostics(
        DIAGNOSTICS_VERSION,
        concentration,
        EquityRiskScore(status, score, band, MINIMUM_SCORE_OBSERVATIONS, components),
        weighted_correlation,
        sorted(pairs, key=lambda p: p.correlation, reverse=True)[:10],
        diversification_ratio,
        volatilities,
        sorted(stresses, key=lambda s: s.pnl),
        drawdowns,
    )
