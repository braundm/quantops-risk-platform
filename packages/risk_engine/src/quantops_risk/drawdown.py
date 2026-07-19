"""Portfolio-value drawdown depth and episode dates."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

from ._validation import date_key, finite_values
from .exceptions import InvalidInputError
from .types import CalculationStatus, DateLike, DrawdownEstimate


def maximum_drawdown(
    portfolio_values: Sequence[object], dates: Sequence[DateLike]
) -> DrawdownEstimate:
    """Return maximum drawdown as a nonnegative fraction of its running peak.

    ``drawdowns`` retain the conventional nonpositive time-series sign. Recovery is
    the first later observation at or above the episode's peak; ``None`` means the
    drawdown remained unrecovered in the supplied history.
    """

    values = finite_values(portfolio_values, name="portfolio_values")
    if len(values) != len(dates):
        raise InvalidInputError("dates and portfolio_values must have equal length")
    if any(value <= 0.0 for value in values):
        raise InvalidInputError("portfolio values must be positive")
    keys = tuple(date_key(item) for item in dates)
    if any(current <= previous for previous, current in pairwise(keys)):
        raise InvalidInputError("dates must be strictly increasing")
    if len(values) < 2:
        return DrawdownEstimate(
            None,
            None,
            None,
            None,
            () if not values else (0.0,),
            len(values),
            CalculationStatus.INSUFFICIENT_DATA,
        )

    peak_value = values[0]
    peak_index = 0
    deepest = 0.0
    deepest_peak_index = 0
    trough_index = 0
    drawdowns: list[float] = []
    for index, value in enumerate(values):
        if value > peak_value:
            peak_value = value
            peak_index = index
        drawdown = value / peak_value - 1.0
        drawdowns.append(drawdown)
        depth = -drawdown
        if depth > deepest:
            deepest = depth
            deepest_peak_index = peak_index
            trough_index = index

    recovery_index: int | None
    if deepest == 0.0:
        recovery_index = 0
    else:
        episode_peak = values[deepest_peak_index]
        recovery_index = next(
            (
                index
                for index in range(trough_index + 1, len(values))
                if values[index] >= episode_peak
            ),
            None,
        )
    return DrawdownEstimate(
        maximum_drawdown=deepest,
        peak_date=dates[deepest_peak_index],
        trough_date=dates[trough_index],
        recovery_date=dates[recovery_index] if recovery_index is not None else None,
        drawdowns=tuple(drawdowns),
        observation_count=len(values),
        status=CalculationStatus.OK,
    )
