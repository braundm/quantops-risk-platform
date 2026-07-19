"""Sample and annualized volatility estimators."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

from ._validation import finite_values
from .exceptions import InvalidInputError
from .types import CalculationStatus, VolatilityEstimate


def sample_volatility(
    returns: Sequence[object], *, periods_per_year: int = 252
) -> VolatilityEstimate:
    """Estimate ddof=1 sample volatility and square-root-of-time annualization."""

    if isinstance(periods_per_year, bool) or not isinstance(periods_per_year, int):
        raise InvalidInputError("periods_per_year must be an integer")
    if periods_per_year <= 0:
        raise InvalidInputError("periods_per_year must be positive")
    values = finite_values(returns, name="returns")
    if len(values) < 2:
        return VolatilityEstimate(
            sample_volatility=None,
            annualized_volatility=None,
            observation_count=len(values),
            periods_per_year=periods_per_year,
            status=CalculationStatus.INSUFFICIENT_DATA,
        )
    daily = statistics.stdev(values)
    return VolatilityEstimate(
        sample_volatility=daily,
        annualized_volatility=daily * math.sqrt(periods_per_year),
        observation_count=len(values),
        periods_per_year=periods_per_year,
        status=CalculationStatus.OK,
    )


def rolling_sample_volatility(
    returns: Sequence[object], *, window: int, periods_per_year: int = 252
) -> tuple[VolatilityEstimate, ...]:
    """Return estimates for every trailing window; no partial windows are invented."""

    if isinstance(window, bool) or not isinstance(window, int) or window < 2:
        raise InvalidInputError("window must be an integer of at least 2")
    values = finite_values(returns, name="returns")
    return tuple(
        sample_volatility(values[end - window : end], periods_per_year=periods_per_year)
        for end in range(window, len(values) + 1)
    )
