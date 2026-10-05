"""Anonymous synthetic decision exercise with server-held future observations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import math
import secrets
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from quantops_api.api.dependencies import require_expensive_capacity
from quantops_api.api.retail import Contract

# Deterministic synthetic paths are held on the server. The browser receives only
# already visible indices. A signed cursor binds the chosen exercise and step.
_CURSOR_KEY = secrets.token_bytes(32)


class LabChoice(Contract):
    token: str = Field(max_length=1000)
    direction: Literal["up", "down", "skip"]
    confidence: Annotated[Decimal, Field(ge=Decimal("0.5"), le=1)]
    cost_bps: Annotated[Decimal, Field(ge=0, le=1000)] = Decimal(10)


class LabOutcome(Contract):
    step: int
    direction: Literal["up", "down", "skip"]
    confidence: Decimal
    correct: bool | None
    market_return: Decimal
    gross_return: Decimal
    net_return: Decimal
    benchmark_return: Decimal
    cost: Decimal
    brier_score: Decimal | None


class LabRound(Contract):
    model_version: str = "anonymous-synthetic-lab@1.0.0"
    token: str
    exercise: int
    step: int
    max_steps: int = 10
    visible_prices: list[float]
    outcome: LabOutcome | None = None
    synthetic: bool = True
    cumulative_gross: Decimal = Decimal(0)
    cumulative_net: Decimal = Decimal(0)
    cumulative_benchmark: Decimal = Decimal(0)
    cumulative_cost: Decimal = Decimal(0)
    correct_count: int = 0
    traded_count: int = 0
    mean_confidence: Decimal | None = None
    mean_brier: Decimal | None = None


class LabState(Contract):
    exercise: int
    step: int
    issued: int
    gross: Decimal = Decimal(0)
    net: Decimal = Decimal(0)
    benchmark: Decimal = Decimal(0)
    cost: Decimal = Decimal(0)
    correct: int = 0
    traded: int = 0
    confidence_sum: Decimal = Decimal(0)
    brier_sum: Decimal = Decimal(0)


router = APIRouter(prefix="/api/v1/retail/lab", tags=["Synthetic education exercise"])


def prices(exercise: int) -> list[float]:
    """Return diverse deterministic synthetic paths, with no survivor selection."""
    return [
        round(
            100
            * math.exp(
                0.02 * math.sin(i * (0.47 + exercise * 0.07))
                + 0.05 * math.sin(i * 0.12 + exercise)
                + (exercise - 2) * i * 0.0003,
            ),
            6,
        )
        for i in range(100)
    ]


def cursor(state: LabState) -> str:
    payload = base64.urlsafe_b64encode(state.model_dump_json().encode()).decode()
    signature = hmac.new(_CURSOR_KEY, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def round_response(state: LabState, outcome: LabOutcome | None = None) -> LabRound:
    return LabRound(
        token=cursor(state),
        exercise=state.exercise,
        step=state.step,
        visible_prices=prices(state.exercise)[: 40 + state.step * 5],
        outcome=outcome,
        cumulative_gross=state.gross,
        cumulative_net=state.net,
        cumulative_benchmark=state.benchmark,
        cumulative_cost=state.cost,
        correct_count=state.correct,
        traded_count=state.traded,
        mean_confidence=state.confidence_sum / state.traded if state.traded else None,
        mean_brier=state.brier_sum / state.traded if state.traded else None,
    )


@router.post("/start", response_model=LabRound)
def start_lab() -> LabRound:
    # Four paths vary by starting time; neither the series nor its future is sent.
    issued = int(datetime.now(UTC).timestamp())
    return round_response(LabState(exercise=issued % 4, step=0, issued=issued))


@router.post(
    "/decision", response_model=LabRound, dependencies=[Depends(require_expensive_capacity)]
)
def lab_decision(request: LabChoice) -> LabRound:
    try:
        payload, signature = request.token.split(":")
        expected = hmac.new(_CURSOR_KEY, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature mismatch")
        state = LabState.model_validate_json(base64.urlsafe_b64decode(payload))
        exercise, step, issued = state.exercise, state.step, state.issued
    except (ValueError, TypeError) as error:
        raise HTTPException(422, "Invalid exercise cursor") from error
    age = int(datetime.now(UTC).timestamp()) - issued
    if not 0 <= exercise < 4 or not 0 <= step < 10 or not 0 <= age <= 3600:
        raise HTTPException(422, "Exercise expired or completed; start a new exercise")
    path = prices(exercise)
    before, after = Decimal(str(path[39 + step * 5])), Decimal(str(path[44 + step * 5]))
    market = after / before - 1
    direction = Decimal(1) if request.direction == "up" else Decimal(-1)
    traded = request.direction != "skip"
    gross = direction * market if traded else Decimal(0)
    cost = request.cost_bps / Decimal(10_000) if traded else Decimal(0)
    correct = gross > 0 if traded else None
    brier = (request.confidence - Decimal(int(bool(correct)))) ** 2 if traded else None
    outcome = LabOutcome(
        step=step + 1,
        direction=request.direction,
        confidence=request.confidence,
        correct=correct,
        market_return=market,
        gross_return=gross,
        net_return=gross - cost,
        benchmark_return=market - request.cost_bps / Decimal(10_000),
        cost=cost,
        brier_score=brier,
    )
    state.step += 1
    state.gross += gross
    state.net += gross - cost
    state.benchmark += outcome.benchmark_return
    state.cost += cost
    if traded:
        state.traded += 1
        state.correct += int(bool(correct))
        state.confidence_sum += request.confidence
        state.brier_sum += brier or Decimal(0)
    return round_response(state, outcome)
