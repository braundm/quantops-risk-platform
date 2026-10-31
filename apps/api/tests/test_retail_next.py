"""Historical alignment, sample sufficiency, no-lookahead education and cost invariants."""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from quantops_api.api.retail import demo_portfolio
from quantops_api.api.retail_history import HistoryRequest, demo_history, historical_risk
from quantops_api.main import create_app
from quantops_api.settings import Settings

D = Decimal
PATH = "/api/v1/retail"


def test_historical_repricing_uses_dated_fx_and_current_units() -> None:
    portfolio = demo_portfolio()
    rows = demo_history()
    response = historical_risk(HistoryRequest(portfolio=portfolio, rows=rows))
    assert response.status == "ok"
    assert response.observation_count == 339
    expected_first = D(10000) + sum((D(100) * r.price * r.fx_to_base for r in rows[:3]), D(0))
    assert response.points[0].value == expected_first
    assert response.es_amount is not None and response.var_amount is not None
    assert response.es_amount >= response.var_amount >= 0
    assert response.source == "synthetic"
    assert "not_investor_performance" in response.warnings
    assert response.tail_count >= 5
    assert response.correlations[0][0] == pytest.approx(1)
    doubled = portfolio.model_copy(deep=True)
    for position in doubled.positions:
        position.quantity *= 2
    second = historical_risk(HistoryRequest(portfolio=doubled, rows=rows))
    assert second.var_amount == response.var_amount * 2
    assert second.var_fraction == response.var_fraction


@pytest.mark.parametrize("kind", ["missing", "duplicate", "base_fx", "same_currency_fx"])
def test_history_rejects_incomplete_or_inconsistent_observations(kind: str) -> None:
    portfolio = demo_portfolio()
    rows = demo_history()
    if kind == "missing":
        rows.pop(0)
    elif kind == "duplicate":
        rows.append(rows[0])
    elif kind == "base_fx":
        rows[2].fx_to_base = D(2)
    else:
        portfolio.positions[1].currency = "USD"
    result = historical_risk(HistoryRequest(portfolio=portfolio, rows=rows))
    assert result.status == "invalid_data"
    assert result.var_amount is None and result.es_amount is None


def test_high_confidence_and_short_samples_suppress_precise_metrics() -> None:
    for rows, confidence, required in [
        (demo_history()[:30], D("0.95"), 252),
        (demo_history(), D("0.99"), 500),
    ]:
        result = historical_risk(
            HistoryRequest(
                portfolio=demo_portfolio(),
                rows=rows,
                confidence=confidence,
            )
        )
        assert result.status == "insufficient_data"
        assert result.required_observations == required
        assert result.var_amount is None
        assert result.daily_volatility is None


def test_history_csv_duplicate_and_nonfinite_inputs_never_import() -> None:
    header = "date,symbol,price,fx_to_base,source\n"
    row = "2025-01-02,OWN,100,4,user\n"
    with TestClient(create_app()) as client:
        for text in (header + row + row, header + row.replace(",100,", ",NaN,")):
            response = client.post(f"{PATH}/history-preview", json={"text": text})
            assert response.status_code == 200
            assert response.json()["importable"] is False
        valid = client.post(f"{PATH}/history-preview", json={"text": header + row})
        assert valid.json()["importable"] is True


def test_lab_reveals_only_decided_steps_and_calculates_costs_and_calibration() -> None:
    with TestClient(create_app(settings=Settings(expensive_rate_limit=100))) as client:
        current = client.post(f"{PATH}/lab/start", json={}).json()
        assert len(current["visible_prices"]) == 40
        assert current["outcome"] is None
        net_sum = D(0)
        for step in range(10):
            direction = "skip" if step == 0 else "up"
            result = client.post(
                f"{PATH}/lab/decision",
                json={
                    "token": current["token"],
                    "direction": direction,
                    "confidence": "0.7",
                    "cost_bps": "10",
                },
            )
            assert result.status_code == 200
            next_round = result.json()
            assert (
                next_round["visible_prices"][: len(current["visible_prices"])]
                == current["visible_prices"]
            )
            assert len(next_round["visible_prices"]) == 40 + 5 * (step + 1)
            outcome = next_round["outcome"]
            if step == 0:
                assert D(outcome["net_return"]) == 0
                assert outcome["correct"] is None
                assert next_round["mean_brier"] is None
            else:
                assert D(outcome["gross_return"]) - D(outcome["net_return"]) == D("0.001")
                expected_brier = (D("0.7") - int(outcome["correct"])) ** 2
                assert D(outcome["brier_score"]) == expected_brier
            net_sum += D(outcome["net_return"])
            assert D(next_round["cumulative_net"]) == net_sum
            current = next_round
        assert current["traded_count"] == 9
        assert D(current["cumulative_cost"]) == D("0.009")
        assert (
            client.post(
                f"{PATH}/lab/decision",
                json={
                    "token": current["token"],
                    "direction": "up",
                    "confidence": "0.7",
                },
            ).status_code
            == 422
        )


def test_lab_cursor_tampering_is_rejected() -> None:
    with TestClient(create_app()) as client:
        token = client.post(f"{PATH}/lab/start", json={}).json()["token"]
        result = client.post(
            f"{PATH}/lab/decision",
            json={
                "token": "A" + token[1:],
                "direction": "up",
                "confidence": "0.7",
            },
        )
    assert result.status_code == 422


def test_costs_do_not_double_count_product_fees_in_prices() -> None:
    items: list[dict[str, object]] = [
        {
            "id": str(uuid4()),
            "category": "product",
            "amount": "100",
            "frequency": "annual",
            "source": "estimated",
            "included_in_prices": True,
        },
        {
            "id": str(uuid4()),
            "category": "commission",
            "amount": "20",
            "frequency": "one_off",
            "source": "actual",
        },
        {
            "id": str(uuid4()),
            "category": "financing",
            "amount": "10",
            "frequency": "monthly",
            "source": "user",
        },
    ]
    with TestClient(create_app()) as client:
        response = client.post(f"{PATH}/cost-budget", json={"items": items})
        duplicate = client.post(f"{PATH}/cost-budget", json={"items": [items[0], items[0]]})
    result = response.json()
    assert D(result["one_off"]) == 20
    assert D(result["recurring_annual"]) == 120
    assert result["excluded_from_total"] == [items[0]["id"]]
    assert duplicate.status_code == 422


def test_preferences_distinguish_willingness_from_financial_capacity() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"{PATH}/preferences",
            json={
                "equity": "100000",
                "cash": "1000",
                "horizon_months": 6,
                "goal": "Liquidity",
                "monthly_inflow": "0",
                "monthly_outflow": "500",
                "liquidity_reserve": "2000",
                "willingness_fraction": "0.2",
                "willingness_amount": "30000",
                "loss_capacity": "5000",
                "concentration_limit": "0.4",
                "asset_experience": {"options": "experienced"},
                "understands_leverage": False,
                "understands_margin": False,
                "constraints": "",
            },
        )
    assert response.status_code == 200
    result = response.json()
    assert D(result["willingness_amount_from_fraction"]) == 20000
    assert D(result["capacity_fraction"]) == D("0.05")
    assert "inconsistent_loss_answers" in result["flags"]
    assert "willingness_exceeds_capacity" in result["flags"]
    assert "explain_leverage_and_margin" in result["flags"]


def test_forecast_quiz_hides_future_until_reveal_and_summarises_calibration() -> None:
    with TestClient(create_app(settings=Settings(expensive_rate_limit=1000))) as client:
        started = client.post(f"{PATH}/forecast/start", json={"confidence_style": "numeric"})
        assert started.status_code == 200
        current = started.json()
        assert current["synthetic"] is True
        assert current["reveal"] is None
        assert len(current["hist_values"]) == 120
        assert current["total"] == 12

        for step in range(1, 5):
            answered = client.post(
                f"{PATH}/forecast/answer",
                json={"token": current["token"], "prediction": "up", "confidence": 70},
            )
            assert answered.status_code == 200
            current = answered.json()
            if step < 4:
                assert current["reveal"] is None
                assert current["finished"] is False
            else:
                assert current["reveal"] is not None
                assert len(current["reveal"]["future_values"]) == 20
                assert current["reveal"]["result"] in {"hit", "miss", "sideways"}
                # Future must not have been present before reveal; history stays fixed length.
                assert len(current["hist_values"]) == 120

        continued = client.post(f"{PATH}/forecast/continue", json={"token": current["token"]})
        assert continued.status_code == 200
        current = continued.json()
        assert current["reveal"] is None
        assert current["question_no"] == 5

        while not current["finished"]:
            if current.get("reveal") is not None:
                current = client.post(
                    f"{PATH}/forecast/continue", json={"token": current["token"]}
                ).json()
                continue
            current = client.post(
                f"{PATH}/forecast/answer",
                json={"token": current["token"], "prediction": "down", "confidence": 60},
            ).json()

        assert current["finished"] is True
        assert current["summary"] is not None
        summary = current["summary"]
        assert summary["hits"] + summary["misses"] + summary["sideways"] == 12
        assert summary["mean_brier"] is not None or summary["sideways"] == 12

        rejected = client.post(
            f"{PATH}/forecast/answer",
            json={"token": current["token"], "prediction": "up", "confidence": 70},
        )
        assert rejected.status_code == 422


def test_forecast_quiz_rejects_invalid_confidence_and_lookahead_continue() -> None:
    with TestClient(create_app(settings=Settings(expensive_rate_limit=1000))) as client:
        token = client.post(f"{PATH}/forecast/start", json={}).json()["token"]
        bad = client.post(
            f"{PATH}/forecast/answer",
            json={"token": token, "prediction": "up", "confidence": 55},
        )
        assert bad.status_code == 422
        early = client.post(f"{PATH}/forecast/continue", json={"token": token})
        assert early.status_code == 422
