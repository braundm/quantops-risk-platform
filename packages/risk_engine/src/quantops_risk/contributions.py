"""Euler volatility contributions with signed diversifying components."""

from __future__ import annotations

import math
from collections.abc import Sequence

from ._validation import finite_values, positive_float, square_matrix
from .covariance import portfolio_variance
from .exceptions import InvalidInputError
from .types import (
    CalculationStatus,
    ContributionEstimate,
    VolatilityContribution,
)


def volatility_contributions(
    exposures: Sequence[object],
    covariance_matrix: Sequence[Sequence[object]],
    *,
    instrument_ids: Sequence[str] | None = None,
    reconciliation_tolerance: object = 1e-10,
) -> ContributionEstimate:
    """Decompose portfolio volatility using Euler's homogeneous-risk identity.

    Component ``i`` is ``exposure_i * (Sigma exposure)_i / portfolio_volatility``.
    Negative diversifying contributions are retained rather than clipped.
    """

    vector = finite_values(exposures, name="exposures")
    if not vector:
        raise InvalidInputError("at least one exposure is required")
    matrix = square_matrix(covariance_matrix, expected_size=len(vector))
    tolerance = positive_float(
        reconciliation_tolerance, name="reconciliation_tolerance", allow_zero=True
    )
    if instrument_ids is None:
        identifiers = tuple(str(index) for index in range(len(vector)))
    else:
        identifiers = tuple(instrument_ids)
        if len(identifiers) != len(vector):
            raise InvalidInputError("instrument_ids and exposures must have equal length")
        if len(set(identifiers)) != len(identifiers) or any(
            not item.strip() for item in identifiers
        ):
            raise InvalidInputError("instrument_ids must be unique and non-empty")

    variance = portfolio_variance(vector, matrix)
    portfolio_volatility = math.sqrt(variance)
    covariance_times_exposure = tuple(
        sum(matrix[i][j] * vector[j] for j in range(len(vector))) for i in range(len(vector))
    )
    if portfolio_volatility == 0.0:
        contributions = tuple(
            VolatilityContribution(identifier, exposure, 0.0, 0.0, 0.0)
            for identifier, exposure in zip(identifiers, vector, strict=True)
        )
    else:
        contributions = tuple(
            VolatilityContribution(
                instrument_id=identifiers[index],
                exposure=vector[index],
                marginal_contribution=covariance_times_exposure[index] / portfolio_volatility,
                component_contribution=(
                    vector[index] * covariance_times_exposure[index] / portfolio_volatility
                ),
                percentage_contribution=(
                    vector[index] * covariance_times_exposure[index] / variance
                ),
            )
            for index in range(len(vector))
        )
    component_sum = sum(item.component_contribution for item in contributions)
    difference = component_sum - portfolio_volatility
    allowed = tolerance * max(1.0, portfolio_volatility)
    return ContributionEstimate(
        portfolio_volatility,
        contributions,
        component_sum,
        difference,
        abs(difference) <= allowed,
        CalculationStatus.OK,
    )
