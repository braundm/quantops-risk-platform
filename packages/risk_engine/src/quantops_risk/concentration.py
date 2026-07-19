"""Absolute-exposure Herfindahl-Hirschman concentration."""

from __future__ import annotations

from collections.abc import Mapping

from ._validation import finite_float
from .types import CalculationStatus, ConcentrationEstimate


def herfindahl_hirschman(exposures: Mapping[str, object]) -> ConcentrationEstimate:
    """Calculate HHI from absolute gross exposure weights.

    Using absolute exposure avoids a misleading low denominator for offsetting long and
    short positions. The result lies in ``[1/n, 1]`` for nonzero portfolios.
    """

    instrument_ids = tuple(sorted(exposures))
    absolute = tuple(
        abs(finite_float(exposures[instrument_id], name=f"exposures[{instrument_id}]"))
        for instrument_id in instrument_ids
    )
    gross = sum(absolute)
    if gross == 0.0:
        return ConcentrationEstimate(
            instrument_ids,
            tuple(0.0 for _ in absolute),
            None,
            None,
            None,
            CalculationStatus.INSUFFICIENT_DATA,
        )
    weights = tuple(value / gross for value in absolute)
    hhi = sum(weight**2 for weight in weights)
    return ConcentrationEstimate(
        instrument_ids,
        weights,
        hhi,
        1.0 / hhi,
        max(weights),
        CalculationStatus.OK,
    )


concentration = herfindahl_hirschman
