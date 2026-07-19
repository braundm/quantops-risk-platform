"""Immutable public input and output types for the risk engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from .exceptions import InsufficientDataError
from .methodology import METHODOLOGY_VERSION

type DateLike = date | datetime | str


class CalculationStatus(StrEnum):
    OK = "ok"
    INSUFFICIENT_DATA = "insufficient_data"
    UNSTABLE = "unstable"


class ReturnMethod(StrEnum):
    ARITHMETIC = "arithmetic"
    LOG = "log"


class MissingDataPolicy(StrEnum):
    RAISE = "raise"
    DROP_PAIR = "drop_pair"


class AlignmentPolicy(StrEnum):
    INTERSECTION = "intersection"
    UNION_STRICT = "union_strict"


@dataclass(frozen=True, slots=True)
class ReturnSeries:
    values: tuple[float, ...]
    interval_end_dates: tuple[DateLike, ...]
    method: ReturnMethod
    observation_count: int
    status: CalculationStatus
    skipped_pair_count: int = 0
    methodology_version: str = METHODOLOGY_VERSION


@dataclass(frozen=True, slots=True)
class VolatilityEstimate:
    sample_volatility: float | None
    annualized_volatility: float | None
    observation_count: int
    periods_per_year: int
    status: CalculationStatus
    methodology_version: str = METHODOLOGY_VERSION

    def require_value(self) -> float:
        if self.sample_volatility is None:
            raise InsufficientDataError(
                "sample volatility", required=2, actual=self.observation_count
            )
        return self.sample_volatility


@dataclass(frozen=True, slots=True)
class CovarianceEstimate:
    matrix: tuple[tuple[float, ...], ...] | None
    means: tuple[float, ...] | None
    observation_count: int
    dimension: int
    status: CalculationStatus
    singular_policy: str = "allow_singular_positive_semidefinite_without_inversion"
    methodology_version: str = METHODOLOGY_VERSION


@dataclass(frozen=True, slots=True)
class RiskEstimate:
    value: float | None
    confidence_level: float
    observation_count: int
    method: str
    status: CalculationStatus
    assumptions: tuple[str, ...]
    methodology_version: str = METHODOLOGY_VERSION

    def require_value(self) -> float:
        if self.value is None:
            raise InsufficientDataError(self.method, required=2, actual=self.observation_count)
        return self.value


@dataclass(frozen=True, slots=True)
class ExpectedShortfallEstimate:
    value: float | None
    var_threshold: float | None
    confidence_level: float
    observation_count: int
    tail_observation_count: int
    method: str
    status: CalculationStatus
    assumptions: tuple[str, ...]
    methodology_version: str = METHODOLOGY_VERSION

    def require_value(self) -> float:
        if self.value is None:
            raise InsufficientDataError(self.method, required=2, actual=self.observation_count)
        return self.value


@dataclass(frozen=True, slots=True)
class DrawdownEstimate:
    maximum_drawdown: float | None
    peak_date: DateLike | None
    trough_date: DateLike | None
    recovery_date: DateLike | None
    drawdowns: tuple[float, ...]
    observation_count: int
    status: CalculationStatus
    methodology_version: str = METHODOLOGY_VERSION


@dataclass(frozen=True, slots=True)
class CorrelationEstimate:
    instrument_ids: tuple[str, ...]
    matrix: tuple[tuple[float | None, ...], ...]
    observation_counts: tuple[tuple[int, ...], ...]
    minimum_observations: int
    unstable_below: int
    status: CalculationStatus
    methodology_version: str = METHODOLOGY_VERSION


@dataclass(frozen=True, slots=True)
class ConcentrationEstimate:
    instrument_ids: tuple[str, ...]
    absolute_weights: tuple[float, ...]
    hhi: float | None
    effective_number: float | None
    largest_weight: float | None
    status: CalculationStatus
    methodology_version: str = METHODOLOGY_VERSION


@dataclass(frozen=True, slots=True)
class VolatilityContribution:
    instrument_id: str
    exposure: float
    marginal_contribution: float
    component_contribution: float
    percentage_contribution: float


@dataclass(frozen=True, slots=True)
class ContributionEstimate:
    portfolio_volatility: float
    contributions: tuple[VolatilityContribution, ...]
    component_sum: float
    reconciliation_difference: float
    reconciled: bool
    status: CalculationStatus
    methodology_version: str = METHODOLOGY_VERSION


@dataclass(frozen=True, slots=True)
class PositionInput:
    instrument_id: str
    quantity: Decimal
    price: Decimal
    price_currency: str
    base_currency: str
    fx_rate_to_base: Decimal | None = None
    cost_basis_per_unit: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PositionValuation:
    instrument_id: str
    quantity: Decimal
    local_market_value: Decimal
    market_value: Decimal
    base_currency: str
    fx_rate_to_base: Decimal
    unrealized_pnl: Decimal | None
    methodology_version: str = METHODOLOGY_VERSION


@dataclass(frozen=True, slots=True)
class PortfolioValuation:
    components: tuple[PositionValuation, ...]
    total_market_value: Decimal
    total_unrealized_pnl: Decimal | None
    base_currency: str
    reconciled: bool
    methodology_version: str = METHODOLOGY_VERSION
