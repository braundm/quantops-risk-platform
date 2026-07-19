"""Numerically stable online sample covariance calculation."""

from __future__ import annotations

from collections.abc import Sequence

from ._validation import finite_values
from .exceptions import InvalidInputError
from .types import CalculationStatus, CovarianceEstimate


def _require_positive_semidefinite(matrix: tuple[tuple[float, ...], ...]) -> None:
    """Validate a covariance matrix with a singularity-tolerant Cholesky factor."""

    size = len(matrix)
    if size == 0:
        return
    scale = max(1.0, *(abs(value) for row in matrix for value in row))
    tolerance = scale * size * 1e-12
    factor = [[0.0] * size for _ in range(size)]
    for i in range(size):
        pivot = matrix[i][i] - sum(factor[i][k] ** 2 for k in range(i))
        if pivot < -tolerance:
            raise InvalidInputError("covariance matrix must be positive semidefinite")
        if pivot <= tolerance:
            factor[i][i] = 0.0
            for j in range(i + 1, size):
                residual = matrix[j][i] - sum(factor[j][k] * factor[i][k] for k in range(i))
                if abs(residual) > tolerance:
                    raise InvalidInputError("covariance matrix must be positive semidefinite")
        else:
            factor[i][i] = pivot**0.5
            for j in range(i + 1, size):
                residual = matrix[j][i] - sum(factor[j][k] * factor[i][k] for k in range(i))
                factor[j][i] = residual / factor[i][i]


def sample_covariance_matrix(rows: Sequence[Sequence[object]]) -> CovarianceEstimate:
    """Calculate ddof=1 covariance using a multivariate Welford update.

    Singular positive-semidefinite matrices are accepted because downstream portfolio
    variance needs no inversion. This policy supports perfectly correlated or constant
    synthetic series without adding arbitrary ridge noise.
    """

    if not rows:
        return CovarianceEstimate(None, None, 0, 0, CalculationStatus.INSUFFICIENT_DATA)
    validated = tuple(finite_values(row, name=f"rows[{index}]") for index, row in enumerate(rows))
    dimension = len(validated[0])
    if dimension == 0:
        raise InvalidInputError("return rows must contain at least one instrument")
    if any(len(row) != dimension for row in validated):
        raise InvalidInputError("all return rows must have the same dimension")
    if len(validated) < 2:
        return CovarianceEstimate(
            None, None, len(validated), dimension, CalculationStatus.INSUFFICIENT_DATA
        )

    means = [0.0] * dimension
    co_moment = [[0.0] * dimension for _ in range(dimension)]
    count = 0
    for row in validated:
        count += 1
        delta = [row[index] - means[index] for index in range(dimension)]
        for index in range(dimension):
            means[index] += delta[index] / count
        delta_after = [row[index] - means[index] for index in range(dimension)]
        for i in range(dimension):
            for j in range(dimension):
                co_moment[i][j] += delta[i] * delta_after[j]

    matrix: list[tuple[float, ...]] = []
    for i in range(dimension):
        row_values: list[float] = []
        for j in range(dimension):
            symmetric = (co_moment[i][j] + co_moment[j][i]) / (2.0 * (count - 1))
            row_values.append(symmetric)
        matrix.append(tuple(row_values))
    return CovarianceEstimate(
        matrix=tuple(matrix),
        means=tuple(means),
        observation_count=count,
        dimension=dimension,
        status=CalculationStatus.OK,
    )


def portfolio_variance(
    exposures: Sequence[object], covariance_matrix: Sequence[Sequence[object]]
) -> float:
    """Return x'Σx, tolerating only round-off-sized negative variance."""

    from ._validation import square_matrix

    vector = finite_values(exposures, name="exposures")
    matrix = square_matrix(covariance_matrix, expected_size=len(vector))
    _require_positive_semidefinite(matrix)
    variance = sum(
        vector[i] * matrix[i][j] * vector[j] for i in range(len(vector)) for j in range(len(vector))
    )
    scale = sum(
        abs(vector[i] * matrix[i][j] * vector[j])
        for i in range(len(vector))
        for j in range(len(vector))
    )
    tolerance = max(1e-15, scale * 1e-12)
    if variance < -tolerance:
        raise InvalidInputError("covariance matrix produces a materially negative variance")
    return max(0.0, variance)
