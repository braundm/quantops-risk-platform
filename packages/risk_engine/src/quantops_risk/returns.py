"""Close-to-close arithmetic and logarithmic return calculations."""

from __future__ import annotations

import math
from collections.abc import Sequence

from ._validation import finite_float
from .exceptions import InvalidInputError, MissingDataError, NonPositivePriceError
from .types import (
    CalculationStatus,
    DateLike,
    MissingDataPolicy,
    ReturnMethod,
    ReturnSeries,
)


def calculate_returns(
    prices: Sequence[object | None],
    *,
    method: ReturnMethod | str = ReturnMethod.ARITHMETIC,
    dates: Sequence[DateLike] | None = None,
    missing_policy: MissingDataPolicy | str = MissingDataPolicy.RAISE,
) -> ReturnSeries:
    """Calculate adjacent close-to-close returns without bridging missing observations.

    Under ``DROP_PAIR``, an interval is omitted when either endpoint is missing. The
    function never joins the observations on either side of a gap, which prevents an
    unbounded implicit forward fill.
    """

    try:
        selected_method = ReturnMethod(method)
    except ValueError as exc:
        raise InvalidInputError(f"unsupported return method: {method!r}") from exc
    try:
        selected_policy = MissingDataPolicy(missing_policy)
    except ValueError as exc:
        raise InvalidInputError(f"unsupported missing-data policy: {missing_policy!r}") from exc

    if dates is not None and len(dates) != len(prices):
        raise InvalidInputError("dates and prices must have equal length")

    if dates is None:
        output_dates: tuple[DateLike, ...] = tuple(str(index) for index in range(len(prices)))
    else:
        output_dates = tuple(dates)

    validated: list[float | None] = []
    for index, value in enumerate(prices):
        if value is None:
            if selected_policy is MissingDataPolicy.RAISE:
                raise MissingDataError(index)
            validated.append(None)
            continue
        price = finite_float(value, name=f"prices[{index}]")
        if price <= 0.0:
            raise NonPositivePriceError(index, value)
        validated.append(price)

    values: list[float] = []
    interval_dates: list[DateLike] = []
    skipped = 0
    for index in range(1, len(validated)):
        previous, current = validated[index - 1], validated[index]
        if previous is None or current is None:
            skipped += 1
            continue
        if selected_method is ReturnMethod.ARITHMETIC:
            result = current / previous - 1.0
        else:
            result = math.log(current / previous)
        values.append(result)
        interval_dates.append(output_dates[index])

    status = CalculationStatus.OK if values else CalculationStatus.INSUFFICIENT_DATA
    return ReturnSeries(
        values=tuple(values),
        interval_end_dates=tuple(interval_dates),
        method=selected_method,
        observation_count=len(values),
        status=status,
        skipped_pair_count=skipped,
    )


def arithmetic_returns(
    prices: Sequence[object | None],
    *,
    dates: Sequence[DateLike] | None = None,
    missing_policy: MissingDataPolicy | str = MissingDataPolicy.RAISE,
) -> ReturnSeries:
    """Convenience wrapper for arithmetic close-to-close returns."""

    return calculate_returns(
        prices, method=ReturnMethod.ARITHMETIC, dates=dates, missing_policy=missing_policy
    )


def log_returns(
    prices: Sequence[object | None],
    *,
    dates: Sequence[DateLike] | None = None,
    missing_policy: MissingDataPolicy | str = MissingDataPolicy.RAISE,
) -> ReturnSeries:
    """Convenience wrapper for continuously compounded close-to-close returns."""

    return calculate_returns(
        prices, method=ReturnMethod.LOG, dates=dates, missing_policy=missing_policy
    )
