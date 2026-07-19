"""Hypothesis properties installed through the package's optional test extra."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from quantops_risk import historical_expected_shortfall, historical_var, sample_volatility

finite_returns = st.lists(
    st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
    min_size=2,
    max_size=100,
)


@given(finite_returns, st.floats(min_value=0.01, max_value=1e6))
def test_var_and_es_scale_and_order(returns: list[float], scale: float) -> None:
    var = historical_var(returns, portfolio_value=scale).require_value()
    es = historical_expected_shortfall(returns, portfolio_value=scale).require_value()
    assert var >= 0
    assert es >= var


@given(st.integers(min_value=2, max_value=100))
def test_zero_returns_have_zero_volatility(length: int) -> None:
    result = sample_volatility([0.0] * length)
    assert result.sample_volatility == 0.0
    assert result.annualized_volatility == 0.0
