"""Historical and normal Expected Shortfall under the VaR loss convention."""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import NormalDist

from ._validation import confidence_level as validate_confidence_level
from ._validation import finite_values, positive_float, square_matrix
from .covariance import portfolio_variance
from .exceptions import InvalidInputError
from .types import CalculationStatus, ExpectedShortfallEstimate
from .var import QuantileInterpolation, historical_var


def historical_expected_shortfall(
    returns: Sequence[object],
    *,
    confidence_level: object = 0.95,
    portfolio_value: object = 1.0,
    interpolation: QuantileInterpolation = "linear",
) -> ExpectedShortfallEstimate:
    """Average observed losses at or beyond the interpolated historical VaR threshold.

    The threshold is inclusive. Interpolation chooses the VaR boundary, while ES itself
    is an unweighted mean of actual observations in that tail. A single tail observation
    is returned with ``UNSTABLE`` status to make finite-sample weakness explicit.
    """

    confidence = validate_confidence_level(confidence_level)
    scale = positive_float(portfolio_value, name="portfolio_value", allow_zero=True)
    values = finite_values(returns, name="returns")
    assumptions = (
        "observed_losses_at_or_above_var_threshold",
        f"var_uses_{interpolation}_interpolation",
        "inclusive_tail_threshold",
        "nonnegative_amount_is_loss",
    )
    if len(values) < 2:
        return ExpectedShortfallEstimate(
            None,
            None,
            confidence,
            len(values),
            0,
            "historical_expected_shortfall",
            CalculationStatus.INSUFFICIENT_DATA,
            assumptions,
        )

    var_estimate = historical_var(
        values,
        confidence_level=confidence,
        portfolio_value=scale,
        interpolation=interpolation,
    ).require_value()
    losses = tuple(-value * scale for value in values)
    tail = tuple(loss for loss in losses if loss >= var_estimate)
    if not tail:
        # This occurs only when VaR was floored at zero and every observation was a gain.
        estimate = 0.0
        status = CalculationStatus.UNSTABLE
    else:
        estimate = max(var_estimate, sum(tail) / len(tail))
        status = CalculationStatus.OK if len(tail) >= 2 else CalculationStatus.UNSTABLE
    return ExpectedShortfallEstimate(
        estimate,
        var_estimate,
        confidence,
        len(values),
        len(tail),
        "historical_expected_shortfall",
        status,
        assumptions,
    )


def parametric_expected_shortfall(
    exposures: Sequence[object],
    covariance_matrix: Sequence[Sequence[object]],
    *,
    confidence_level: object = 0.95,
    mean_returns: Sequence[object] | None = None,
    horizon_periods: object = 1.0,
    observation_count: int = 0,
) -> ExpectedShortfallEstimate:
    """Normal-theory ES using phi(z)/(1-confidence)."""

    confidence = validate_confidence_level(confidence_level)
    vector = finite_values(exposures, name="exposures")
    assumptions = (
        "multivariate_normal_returns",
        "linear_exposures",
        "normal_closed_form_tail_mean",
        "nonnegative_amount_is_loss",
    )
    if not vector:
        return ExpectedShortfallEstimate(
            None,
            None,
            confidence,
            0,
            0,
            "parametric_expected_shortfall",
            CalculationStatus.INSUFFICIENT_DATA,
            assumptions,
        )
    matrix = square_matrix(covariance_matrix, expected_size=len(vector))
    horizon = positive_float(horizon_periods, name="horizon_periods")
    if isinstance(observation_count, bool) or not isinstance(observation_count, int):
        raise InvalidInputError("observation_count must be an integer")
    if observation_count < 0:
        raise InvalidInputError("observation_count must be nonnegative")
    if mean_returns is None:
        means = (0.0,) * len(vector)
    else:
        means = finite_values(mean_returns, name="mean_returns")
        if len(means) != len(vector):
            raise InvalidInputError("mean_returns and exposures must have equal length")
    standard_deviation = math.sqrt(portfolio_variance(vector, matrix) * horizon)
    expected_pnl = sum(vector[i] * means[i] * horizon for i in range(len(vector)))
    z_score = NormalDist().inv_cdf(confidence)
    density = math.exp(-(z_score**2) / 2.0) / math.sqrt(2.0 * math.pi)
    value = max(0.0, -expected_pnl + standard_deviation * density / (1.0 - confidence))
    var_threshold = max(0.0, -expected_pnl + z_score * standard_deviation)
    return ExpectedShortfallEstimate(
        max(value, var_threshold),
        var_threshold,
        confidence,
        observation_count,
        0,
        "parametric_expected_shortfall",
        CalculationStatus.OK,
        assumptions,
    )


expected_shortfall = historical_expected_shortfall
