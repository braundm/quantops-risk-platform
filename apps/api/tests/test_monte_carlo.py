"""Native simulation, calibration, invalid-input and API boundary regressions."""

import math
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from quantops_api.api.xtb import risk_example
from quantops_api.application.monte_carlo import MonteCarloRequest, analyze_monte_carlo
from quantops_api.infrastructure.monte_carlo import NativeUnavailable, simulate
from quantops_api.main import create_app


def request() -> MonteCarloRequest:
    return MonteCarloRequest(portfolio=risk_example("equities_only"), simulations=1000, days=21)


def native_ready() -> None:
    try:
        simulate([1.0], [[0.0]], [0.0], 1, 1000, 42, 0.95)
    except NativeUnavailable:
        pytest.skip("Optional C++ engine has not been built on this host")


def test_native_seed_covariance_tail_and_histogram_contract() -> None:
    native_ready()
    result = analyze_monte_carlo(request())
    assert result == analyze_monte_carlo(request())
    assert result.engine == "C++17" and result.hypothetical and result.synthetic_input
    assert result.observations >= 252
    assert result.es_amount >= result.var_amount
    assert sum(b.count for b in result.histogram) == result.simulations
    assert len(result.sample_paths) == 12
    assert result.bands[0].low == result.bands[0].high == result.initial_value
    assert result.bands[-1].day == result.days
    assert all(b.low <= b.median <= b.high for b in result.bands)
    assert any(abs(row[i]) > 0 for i, row in enumerate(result.annual_covariance))
    assert all(len(p) == len(result.bands) for p in result.sample_paths)


def test_zero_volatility_and_known_growth() -> None:
    native_ready()
    summary, bands, paths, terminal = simulate([100000.0], [[0.0]], [0.0], 252, 1000, 42, 0.95)
    assert summary == [0, 0, 0, 100000, 100000]
    assert all(v == 100000 for row in bands + paths for v in row)
    assert terminal == [100000] * 1000
    summary, _, _, _ = simulate([100000.0], [[0.0]], [0.1], 252, 1000, 42, 0.95)
    assert summary[3] == pytest.approx(100000 * math.exp(0.1))
    assert summary[1] < 0 and summary[2] < 0


@pytest.mark.parametrize(
    ("exposures", "covariance", "drift"),
    [
        ([-1.0], [[0.04]], [0.0]),
        ([1.0], [[float("nan")]], [0.0]),
        ([1.0], [[-1.0]], [0.0]),
        ([1.0, 1.0], [[0.04, 0.09], [0.09, 0.04]], [0.0, 0.0]),
        ([1.0, 1.0], [[0.04, 0.01], [0.0, 0.04]], [0.0, 0.0]),
        ([1.0, 1.0], [[0.04, 0.01]], [0.0, 0.0]),
        ([0.0], [[0.0]], [0.0]),
    ],
)
def test_invalid_native_inputs_are_rejected(
    exposures: list[float], covariance: list[list[float]], drift: list[float]
) -> None:
    native_ready()
    with pytest.raises(ValueError):
        simulate(exposures, covariance, drift, 21, 1000, 42, 0.95)


def test_work_is_bounded_before_large_allocation() -> None:
    native_ready()
    with pytest.raises(ValueError, match="Work limit"):
        simulate([1.0] * 20, [[0.0] * 20 for _ in range(20)], [0.0] * 20, 1260, 50000, 42, 0.95)


def test_missing_history_does_not_silently_drop_an_asset() -> None:
    req = request()
    req.portfolio.histories.pop()
    with pytest.raises(ValueError, match="complete valued"):
        analyze_monte_carlo(req)


def test_short_history_is_rejected_before_native_execution() -> None:
    req = request()
    req.portfolio.histories = [
        h.model_copy(update={"rows": h.rows[-100:]}) for h in req.portfolio.histories
    ]
    with pytest.raises(ValueError, match="252 aligned"):
        analyze_monte_carlo(req)


def test_stale_provider_data_is_blocked() -> None:
    req = request()
    req.portfolio.histories = [
        h.model_copy(update={"origin": "provider"}) for h in req.portfolio.histories
    ]
    with pytest.raises(ValueError, match="stale"):
        analyze_monte_carlo(req)


def test_after_allocation_requires_a_validated_variant() -> None:
    req = request().model_copy(update={"allocation": "after"})
    with pytest.raises(ValueError, match="complete valued"):
        analyze_monte_carlo(req)


def test_cash_variant_is_used_and_remains_constant() -> None:
    native_ready()
    req = request()
    req.portfolio.variant = {"CASH:PLN": Decimal(1)}
    req.allocation = "after"
    cash = analyze_monte_carlo(req)
    assert cash.var_amount == cash.es_amount == 0
    assert all(b.low == b.median == b.high == cash.initial_value for b in cash.bands)
    req.portfolio.variant = {"CASH:PLN": Decimal(".5"), "AAPL.US": Decimal(".5")}
    result = analyze_monte_carlo(req)
    assert result.symbols == ["AAPL.US", "CASH:PLN"]
    assert result.annual_covariance[1] == [0, 0]


def test_api_returns_real_native_results_and_validation_problem() -> None:
    native_ready()
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/xtb/monte-carlo", json=request().model_dump(mode="json"))
        assert response.status_code == 200
        assert response.json()["engine"] == "C++17"
        assert response.json()["initial_value"] == str(analyze_monte_carlo(request()).initial_value)
        bad = request().model_dump(mode="json")
        bad["simulations"] = 999
        assert client.post("/api/v1/xtb/monte-carlo", json=bad).status_code == 422


def test_missing_native_engine_is_503_without_python_fallback() -> None:
    with (
        patch(
            "quantops_api.application.monte_carlo.simulate",
            side_effect=NativeUnavailable("Build native engine"),
        ),
        TestClient(create_app()) as client,
    ):
        response = client.post("/api/v1/xtb/monte-carlo", json=request().model_dump(mode="json"))
    assert response.status_code == 503


def test_library_with_missing_exports_is_unavailable() -> None:
    with (
        patch("quantops_api.infrastructure.monte_carlo.Path.is_file", return_value=True),
        patch("quantops_api.infrastructure.monte_carlo.ctypes.CDLL", return_value=object()),
        pytest.raises(NativeUnavailable, match="rebuild"),
    ):
        simulate([100.0], [[0.0]], [0.0], 1, 1000, 42, 0.95)
