"""One-day VaR exception counting and Kupiec proportion-of-failures test."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from ._validation import confidence_level as validate_confidence_level
from ._validation import finite_float, finite_values, positive_float
from .exceptions import InvalidInputError
from .methodology import METHODOLOGY_VERSION
from .types import CalculationStatus, DateLike, RiskEstimate
from .var import QuantileInterpolation, historical_var


@dataclass(frozen=True, slots=True)
class VaRBacktestObservation:
    date: DateLike
    forecast_var: float
    realized_loss: float
    exception: bool
    regime_label: str | None = None


@dataclass(frozen=True, slots=True)
class VaRBacktestResult:
    confidence_level: float
    expected_exception_rate: float
    observation_count: int
    exception_count: int
    exception_rate: float | None
    kupiec_pof_statistic: float | None
    kupiec_p_value: float | None
    observations: tuple[VaRBacktestObservation, ...]
    status: CalculationStatus
    limitations: tuple[str, ...]
    methodology_version: str = METHODOLOGY_VERSION


def kupiec_proportion_of_failures(
    exception_count: int, observation_count: int, *, expected_exception_rate: object
) -> tuple[float, float]:
    """Return Kupiec LR statistic and exact chi-square(1) survival probability."""

    if (
        isinstance(observation_count, bool)
        or not isinstance(observation_count, int)
        or observation_count <= 0
    ):
        raise InvalidInputError("observation_count must be a positive integer")
    if (
        isinstance(exception_count, bool)
        or not isinstance(exception_count, int)
        or not 0 <= exception_count <= observation_count
    ):
        raise InvalidInputError("exception_count must be between 0 and observation_count")
    expected = positive_float(
        expected_exception_rate, name="expected_exception_rate", allow_zero=True
    )
    if not 0.0 < expected < 1.0:
        raise InvalidInputError("expected_exception_rate must be strictly between 0 and 1")

    failures = exception_count
    successes = observation_count - exception_count
    observed = failures / observation_count

    def count_log_probability(count: int, probability: float) -> float:
        return 0.0 if count == 0 else count * math.log(probability)

    null_log_likelihood = count_log_probability(failures, expected) + count_log_probability(
        successes, 1.0 - expected
    )
    alternative_log_likelihood = 0.0
    if failures:
        alternative_log_likelihood += count_log_probability(failures, observed)
    if successes:
        alternative_log_likelihood += count_log_probability(successes, 1.0 - observed)
    statistic = max(0.0, 2.0 * (alternative_log_likelihood - null_log_likelihood))
    p_value = math.erfc(math.sqrt(statistic / 2.0))
    return statistic, p_value


def var_exception_backtest(
    forecast_vars: Sequence[object | RiskEstimate],
    realized_returns: Sequence[object],
    *,
    confidence_level: object,
    portfolio_value: object = 1.0,
    dates: Sequence[DateLike] | None = None,
    regime_labels: Sequence[str | None] | None = None,
    small_sample_threshold: int = 250,
) -> VaRBacktestResult:
    """Compare ex-ante one-day VaR forecasts with next-day realized losses."""

    confidence = validate_confidence_level(confidence_level)
    scale = positive_float(portfolio_value, name="portfolio_value", allow_zero=True)
    if len(forecast_vars) != len(realized_returns):
        raise InvalidInputError("forecast_vars and realized_returns must have equal length")
    if dates is not None and len(dates) != len(forecast_vars):
        raise InvalidInputError("dates and forecasts must have equal length")
    if regime_labels is not None and len(regime_labels) != len(forecast_vars):
        raise InvalidInputError("regime_labels and forecasts must have equal length")
    if (
        isinstance(small_sample_threshold, bool)
        or not isinstance(small_sample_threshold, int)
        or small_sample_threshold <= 0
    ):
        raise InvalidInputError("small_sample_threshold must be a positive integer")

    returns = finite_values(realized_returns, name="realized_returns")
    observations: list[VaRBacktestObservation] = []
    for index, (forecast, realized_return) in enumerate(zip(forecast_vars, returns, strict=True)):
        if isinstance(forecast, RiskEstimate):
            forecast_value = forecast.require_value()
            if abs(forecast.confidence_level - confidence) > 1e-12:
                raise InvalidInputError("forecast confidence does not match backtest confidence")
        else:
            forecast_value = finite_float(forecast, name=f"forecast_vars[{index}]")
        if forecast_value < 0.0:
            raise InvalidInputError("VaR forecasts must be nonnegative")
        realized_loss = -realized_return * scale
        observations.append(
            VaRBacktestObservation(
                date=dates[index] if dates is not None else str(index),
                forecast_var=forecast_value,
                realized_loss=realized_loss,
                exception=realized_loss > forecast_value,
                regime_label=regime_labels[index] if regime_labels is not None else None,
            )
        )

    count = len(observations)
    limitations = (
        "kupiec_test_has_low_power_in_small_samples",
        "exception_independence_is_not_tested",
        "overlapping_or_revised_data_can_invalidate_backtest",
    )
    if count == 0:
        return VaRBacktestResult(
            confidence,
            1.0 - confidence,
            0,
            0,
            None,
            None,
            None,
            (),
            CalculationStatus.INSUFFICIENT_DATA,
            limitations,
        )
    exceptions = sum(item.exception for item in observations)
    statistic, p_value = kupiec_proportion_of_failures(
        exceptions, count, expected_exception_rate=1.0 - confidence
    )
    return VaRBacktestResult(
        confidence,
        1.0 - confidence,
        count,
        exceptions,
        exceptions / count,
        statistic,
        p_value,
        tuple(observations),
        CalculationStatus.OK if count >= small_sample_threshold else CalculationStatus.UNSTABLE,
        limitations,
    )


def rolling_historical_var_backtest(
    returns: Sequence[object],
    *,
    window: int,
    confidence_level: object = 0.95,
    portfolio_value: object = 1.0,
    interpolation: QuantileInterpolation = "linear",
    dates: Sequence[DateLike] | None = None,
    regime_labels: Sequence[str | None] | None = None,
) -> VaRBacktestResult:
    """Forecast from the trailing window only, then compare with the next return."""

    confidence = validate_confidence_level(confidence_level)
    if isinstance(window, bool) or not isinstance(window, int) or window < 2:
        raise InvalidInputError("window must be an integer of at least 2")
    values = finite_values(returns, name="returns")
    if dates is not None and len(dates) != len(values):
        raise InvalidInputError("dates and returns must have equal length")
    if regime_labels is not None and len(regime_labels) != len(values):
        raise InvalidInputError("regime_labels and returns must have equal length")
    if len(values) <= window:
        return var_exception_backtest(
            (),
            (),
            confidence_level=confidence,
            portfolio_value=portfolio_value,
        )

    forecasts = tuple(
        historical_var(
            values[index - window : index],
            confidence_level=confidence,
            portfolio_value=portfolio_value,
            interpolation=interpolation,
        )
        for index in range(window, len(values))
    )
    return var_exception_backtest(
        forecasts,
        values[window:],
        confidence_level=confidence,
        portfolio_value=portfolio_value,
        dates=dates[window:] if dates is not None else None,
        regime_labels=regime_labels[window:] if regime_labels is not None else None,
    )


backtest_var = var_exception_backtest
