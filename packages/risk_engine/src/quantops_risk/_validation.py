"""Shared validation helpers; numerical modules never propagate NaN silently."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from decimal import Decimal

from .exceptions import InvalidInputError


def finite_float(value: object, *, name: str) -> float:
    """Coerce a real numeric value to finite float, rejecting bool and non-finite data."""

    if isinstance(value, bool):
        raise InvalidInputError(f"{name} must be numeric, not bool")
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidInputError(f"{name} must be a finite real number") from exc
    if not math.isfinite(result):
        raise InvalidInputError(f"{name} must be finite")
    return result


def finite_values(values: Iterable[object], *, name: str) -> tuple[float, ...]:
    return tuple(finite_float(value, name=f"{name}[{index}]") for index, value in enumerate(values))


def confidence_level(value: object) -> float:
    result = finite_float(value, name="confidence_level")
    if not 0.5 < result < 1.0:
        raise InvalidInputError("confidence_level must be strictly between 0.5 and 1")
    return result


def positive_float(value: object, *, name: str, allow_zero: bool = False) -> float:
    result = finite_float(value, name=name)
    valid = result >= 0.0 if allow_zero else result > 0.0
    if not valid:
        relation = "nonnegative" if allow_zero else "positive"
        raise InvalidInputError(f"{name} must be {relation}")
    return result


def strict_decimal(value: object, *, name: str) -> Decimal:
    """Require Decimal to prevent accidental binary-float money construction."""

    if not isinstance(value, Decimal):
        raise InvalidInputError(f"{name} must be Decimal")
    if not value.is_finite():
        raise InvalidInputError(f"{name} must be finite")
    return value


def square_matrix(
    values: Sequence[Sequence[object]], *, expected_size: int | None = None
) -> tuple[tuple[float, ...], ...]:
    matrix = tuple(finite_values(row, name=f"matrix[{i}]") for i, row in enumerate(values))
    size = len(matrix)
    if expected_size is not None and size != expected_size:
        raise InvalidInputError(
            f"matrix dimension {size} does not match vector dimension {expected_size}"
        )
    if any(len(row) != size for row in matrix):
        raise InvalidInputError("matrix must be square")
    for i in range(size):
        for j in range(i + 1, size):
            tolerance = 1e-12 * max(1.0, abs(matrix[i][j]), abs(matrix[j][i]))
            if abs(matrix[i][j] - matrix[j][i]) > tolerance:
                raise InvalidInputError("matrix must be symmetric")
    return matrix


def date_key(value: object) -> str:
    isoformat = getattr(value, "isoformat", None)
    return str(isoformat()) if callable(isoformat) else str(value)
