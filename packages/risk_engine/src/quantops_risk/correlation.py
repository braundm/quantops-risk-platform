"""Pairwise-complete historical correlation with overlap counts."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from ._validation import finite_float
from .exceptions import InvalidInputError
from .types import CalculationStatus, CorrelationEstimate


def _pairwise_correlation(
    left: Sequence[object | None], right: Sequence[object | None]
) -> tuple[float | None, int]:
    if len(left) != len(right):
        raise InvalidInputError("all correlation series must have equal calendar length")
    pairs: list[tuple[float, float]] = []
    for index, (left_value, right_value) in enumerate(zip(left, right, strict=True)):
        if left_value is None or right_value is None:
            continue
        pairs.append(
            (
                finite_float(left_value, name=f"left[{index}]"),
                finite_float(right_value, name=f"right[{index}]"),
            )
        )
    count = len(pairs)
    if count < 2:
        return None, count
    left_mean = math.fsum(pair[0] for pair in pairs) / count
    right_mean = math.fsum(pair[1] for pair in pairs) / count
    cross = math.fsum((x - left_mean) * (y - right_mean) for x, y in pairs)
    left_ss = math.fsum((x - left_mean) ** 2 for x, _ in pairs)
    right_ss = math.fsum((y - right_mean) ** 2 for _, y in pairs)
    if left_ss == 0.0 or right_ss == 0.0:
        return None, count
    correlation = cross / math.sqrt(left_ss * right_ss)
    return max(-1.0, min(1.0, correlation)), count


def correlation_matrix(
    series_by_instrument: Mapping[str, Sequence[object | None]],
    *,
    minimum_observations: int = 2,
    unstable_below: int = 20,
) -> CorrelationEstimate:
    """Calculate deterministic pairwise correlations and overlap counts.

    Historical correlation is descriptive and unstable; the overall status is
    ``UNSTABLE`` whenever a defined pair has fewer than ``unstable_below`` overlaps.
    Undefined pairs are represented as ``None``, never NaN.
    """

    if (
        isinstance(minimum_observations, bool)
        or not isinstance(minimum_observations, int)
        or minimum_observations < 2
    ):
        raise InvalidInputError("minimum_observations must be an integer of at least 2")
    if (
        isinstance(unstable_below, bool)
        or not isinstance(unstable_below, int)
        or unstable_below < minimum_observations
    ):
        raise InvalidInputError("unstable_below must be at least minimum_observations")
    instrument_ids = tuple(sorted(series_by_instrument))
    if not instrument_ids:
        return CorrelationEstimate(
            (), (), (), minimum_observations, unstable_below, CalculationStatus.INSUFFICIENT_DATA
        )
    lengths = {len(series_by_instrument[item]) for item in instrument_ids}
    if len(lengths) > 1:
        raise InvalidInputError("all correlation series must have equal calendar length")
    validated_series = {
        instrument_id: tuple(
            None if value is None else finite_float(value, name=f"{instrument_id}[{index}]")
            for index, value in enumerate(series_by_instrument[instrument_id])
        )
        for instrument_id in instrument_ids
    }

    matrix: list[list[float | None]] = [[None] * len(instrument_ids) for _ in instrument_ids]
    counts: list[list[int]] = [[0] * len(instrument_ids) for _ in instrument_ids]
    has_insufficient = False
    has_unstable = False
    for i, left_id in enumerate(instrument_ids):
        for j in range(i, len(instrument_ids)):
            value, count = _pairwise_correlation(
                validated_series[left_id], validated_series[instrument_ids[j]]
            )
            if count < minimum_observations:
                value = None
            matrix[i][j] = matrix[j][i] = value
            counts[i][j] = counts[j][i] = count
            if value is None:
                has_insufficient = True
            elif count < unstable_below:
                has_unstable = True
    status = (
        CalculationStatus.INSUFFICIENT_DATA
        if has_insufficient
        else CalculationStatus.UNSTABLE
        if has_unstable
        else CalculationStatus.OK
    )
    return CorrelationEstimate(
        instrument_ids,
        tuple(tuple(row) for row in matrix),
        tuple(tuple(row) for row in counts),
        minimum_observations,
        unstable_below,
        status,
    )
