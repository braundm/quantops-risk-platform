"""Explicit calendar alignment without implicit forward filling."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ._validation import date_key, finite_float
from .exceptions import InvalidInputError, MissingDataError
from .methodology import METHODOLOGY_VERSION
from .types import AlignmentPolicy, CalculationStatus, DateLike


@dataclass(frozen=True, slots=True)
class AlignedSeries:
    instrument_ids: tuple[str, ...]
    dates: tuple[DateLike, ...]
    rows: tuple[tuple[float, ...], ...]
    policy: AlignmentPolicy
    status: CalculationStatus
    methodology_version: str = METHODOLOGY_VERSION


def align_series(
    series: Mapping[str, Mapping[DateLike, object | None]],
    *,
    policy: AlignmentPolicy | str = AlignmentPolicy.INTERSECTION,
) -> AlignedSeries:
    """Align named series on an explicit intersection or strict union calendar.

    ``INTERSECTION`` retains only dates with a present value for every instrument.
    ``UNION_STRICT`` requires every instrument on every union date and raises otherwise.
    Neither policy forward-fills values.
    """

    try:
        selected_policy = AlignmentPolicy(policy)
    except ValueError as exc:
        raise InvalidInputError(f"unsupported alignment policy: {policy!r}") from exc
    if not series:
        return AlignedSeries((), (), (), selected_policy, CalculationStatus.INSUFFICIENT_DATA)

    instrument_ids = tuple(sorted(series))
    if any(not instrument_id.strip() for instrument_id in instrument_ids):
        raise InvalidInputError("instrument identifiers must be non-empty")

    date_objects: dict[str, DateLike] = {}
    normalized: dict[str, dict[str, float | None]] = {}
    for instrument_id in instrument_ids:
        normalized[instrument_id] = {}
        for date, value in series[instrument_id].items():
            key = date_key(date)
            if key in normalized[instrument_id]:
                raise InvalidInputError(f"duplicate normalized date {key!r} for {instrument_id}")
            normalized[instrument_id][key] = (
                None if value is None else finite_float(value, name=f"{instrument_id}[{key}]")
            )
            date_objects.setdefault(key, date)

    calendars = [set(normalized[instrument_id]) for instrument_id in instrument_ids]
    if selected_policy is AlignmentPolicy.INTERSECTION:
        candidate_dates = set.intersection(*calendars)
        candidate_dates = {
            key
            for key in candidate_dates
            if all(normalized[instrument_id][key] is not None for instrument_id in instrument_ids)
        }
    else:
        candidate_dates = set.union(*calendars)

    rows: list[tuple[float, ...]] = []
    retained_dates: list[DateLike] = []
    for row_index, key in enumerate(sorted(candidate_dates)):
        row: list[float] = []
        for instrument_id in instrument_ids:
            value = normalized[instrument_id].get(key)
            if value is None:
                raise MissingDataError(row_index)
            row.append(finite_float(value, name=f"{instrument_id}[{key}]"))
        rows.append(tuple(row))
        retained_dates.append(date_objects[key])

    status = CalculationStatus.OK if rows else CalculationStatus.INSUFFICIENT_DATA
    return AlignedSeries(
        instrument_ids, tuple(retained_dates), tuple(rows), selected_policy, status
    )
