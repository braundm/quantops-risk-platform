"""Historical and normal variance-covariance Value at Risk."""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import NormalDist
from typing import Literal

from ._validation import confidence_level as validate_confidence_level
from ._validation import finite_values, positive_float, square_matrix
from .covariance import portfolio_variance, sample_covariance_matrix
from .exceptions import InvalidInputError
from .types import CalculationStatus, RiskEstimate

QuantileInterpolation = Literal["linear", "lower", "higher", "nearest", "midpoint"]


def empirical_quantile(
    values: Sequence[object],
    probability: object,
    *,
    interpolation: QuantileInterpolation = "linear",
) -> float:
    """Return an explicitly interpolated empirical quantile (NumPy-compatible rules)."""

    samples = sorted(finite_values(values, name="values"))
    if not samples:
        raise InvalidInputError("empirical quantile requires at least one observation")
    p = positive_float(probability, name="probability", allow_zero=True)
    if p > 1.0:
        raise InvalidInputError("probability must not exceed 1")
    if interpolation not in {"linear", "lower", "higher", "nearest", "midpoint"}:
        raise InvalidInputError(f"unsupported quantile interpolation: {interpolation!r}")
    position = (len(samples) - 1) * p
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    lower = samples[lower_index]
    upper = samples[upper_index]
    if interpolation == "lower":
        return lower
    if interpolation == "higher":
        return upper
    if interpolation == "nearest":
        # Round halves to the lower index for a stable rule independent of Python's
        # bankers-rounding behavior.
        return samples[lower_index if position - lower_index <= 0.5 else upper_index]
    if interpolation == "midpoint":
        return (lower + upper) / 2.0
    return lower + (position - lower_index) * (upper - lower)


def historical_var(
    returns: Sequence[object],
    *,
    confidence_level: object = 0.95,
    portfolio_value: object = 1.0,
    interpolation: QuantileInterpolation = "linear",
) -> RiskEstimate:
    """Estimate empirical VaR under a nonnegative-amount-is-loss convention.

    Returns are converted to one-period losses as ``-return * portfolio_value``. VaR
    is floored at zero when the selected quantile represents a gain; it is not a claim
    about the maximum possible loss.
    """

    confidence = validate_confidence_level(confidence_level)
    scale = positive_float(portfolio_value, name="portfolio_value", allow_zero=True)
    values = finite_values(returns, name="returns")
    assumptions = (
        "one_period_close_to_close_arithmetic_returns",
        f"empirical_quantile_{interpolation}_interpolation",
        "nonnegative_amount_is_loss",
        "var_is_not_maximum_possible_loss",
    )
    if len(values) < 2:
        return RiskEstimate(
            None,
            confidence,
            len(values),
            "historical_var",
            CalculationStatus.INSUFFICIENT_DATA,
            assumptions,
        )
    losses = tuple(-value * scale for value in values)
    estimate = max(0.0, empirical_quantile(losses, confidence, interpolation=interpolation))
    return RiskEstimate(
        estimate,
        confidence,
        len(values),
        "historical_var",
        CalculationStatus.OK,
        assumptions,
    )


def parametric_var(
    exposures: Sequence[object],
    covariance_matrix: Sequence[Sequence[object]],
    *,
    confidence_level: object = 0.95,
    mean_returns: Sequence[object] | None = None,
    horizon_periods: object = 1.0,
    observation_count: int = 0,
) -> RiskEstimate:
    """Estimate normal variance-covariance VaR for monetary asset exposures.

    ``exposures`` are base-currency market values and covariance is the one-period
    return covariance matrix. A singular positive-semidefinite covariance is accepted;
    no inverse or arbitrary regularization is used.
    """

    confidence = validate_confidence_level(confidence_level)
    vector = finite_values(exposures, name="exposures")
    if not vector:
        return RiskEstimate(
            None,
            confidence,
            0,
            "parametric_var",
            CalculationStatus.INSUFFICIENT_DATA,
            ("normal_returns", "sample_covariance", "singular_covariance_allowed"),
        )
    matrix = square_matrix(covariance_matrix, expected_size=len(vector))
    horizon = positive_float(horizon_periods, name="horizon_periods")
    if isinstance(observation_count, bool) or not isinstance(observation_count, int):
        raise InvalidInputError("observation_count must be an integer")
    if observation_count < 0:
        raise InvalidInputError("observation_count must be nonnegative")
    if mean_returns is None:
        asset_means = (0.0,) * len(vector)
    else:
        asset_means = finite_values(mean_returns, name="mean_returns")
        if len(asset_means) != len(vector):
            raise InvalidInputError("mean_returns and exposures must have equal length")

    standard_deviation = math.sqrt(portfolio_variance(vector, matrix) * horizon)
    expected_pnl = sum(vector[index] * asset_means[index] * horizon for index in range(len(vector)))
    z_score = NormalDist().inv_cdf(confidence)
    estimate = max(0.0, -expected_pnl + z_score * standard_deviation)
    return RiskEstimate(
        estimate,
        confidence,
        observation_count,
        "parametric_var",
        CalculationStatus.OK,
        (
            "multivariate_normal_returns",
            "linear_exposures",
            "square_root_of_time_volatility",
            "covariance_positive_semidefinite_singular_allowed",
            "nonnegative_amount_is_loss",
        ),
    )


def parametric_var_from_returns(
    return_rows: Sequence[Sequence[object]],
    exposures: Sequence[object],
    *,
    confidence_level: object = 0.95,
    include_sample_mean: bool = False,
    horizon_periods: object = 1.0,
) -> RiskEstimate:
    """Estimate covariance from aligned rows, then calculate parametric VaR."""

    confidence = validate_confidence_level(confidence_level)
    covariance = sample_covariance_matrix(return_rows)
    if covariance.matrix is None or covariance.means is None:
        return RiskEstimate(
            None,
            confidence,
            covariance.observation_count,
            "parametric_var",
            CalculationStatus.INSUFFICIENT_DATA,
            ("multivariate_normal_returns", "sample_covariance_ddof_1"),
        )
    return parametric_var(
        exposures,
        covariance.matrix,
        confidence_level=confidence,
        mean_returns=covariance.means if include_sample_mean else None,
        horizon_periods=horizon_periods,
        observation_count=covariance.observation_count,
    )
