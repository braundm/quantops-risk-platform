"""Synthetic market-direction forecast quiz with no lookahead and calibration summary."""

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

_CURSOR_KEY = secrets.token_bytes(32)

HISTORY = 120
FUTURE = 20
SIDEWAYS_PCT = Decimal("2.5")
QUESTION_COUNT = 12
REVEAL_EVERY = 4
CASE_POOL = 48

Confidence = Annotated[int, Field(ge=50, le=100)]
Direction = Literal["up", "down"]
Actual = Literal["up", "down", "sideways"]
Result = Literal["hit", "miss", "sideways"]


class ForecastStart(Contract):
    confidence_style: Literal["numeric", "words"] = "numeric"


class ForecastAnswer(Contract):
    token: str = Field(max_length=4000)
    prediction: Direction
    confidence: Confidence


class ForecastContinue(Contract):
    token: str = Field(max_length=4000)


class ForecastReveal(Contract):
    future_values: list[float]
    future_return_pct: Decimal
    actual: Actual
    result: Result


class ForecastAnswerRow(Contract):
    question_no: int
    case_id: int
    prediction: Direction
    confidence: int
    future_return_pct: Decimal
    actual: Actual
    result: Result


class ForecastSummary(Contract):
    hits: int
    misses: int
    sideways: int
    effectiveness_pct: Decimal | None
    mean_confidence: Decimal
    mean_confidence_hit: Decimal | None
    mean_confidence_miss: Decimal | None
    mean_brier: Decimal | None
    by_confidence: list[dict[str, Decimal | int | str]]
    most_confident: ForecastAnswerRow | None


class ForecastRound(Contract):
    model_version: str = "synthetic-forecast-quiz@1.0.0"
    token: str
    question_no: int
    total: int = QUESTION_COUNT
    instrument: str
    hist_values: list[float]
    confidence_style: Literal["numeric", "words"]
    synthetic: bool = True
    reveal: ForecastReveal | None = None
    finished: bool = False
    progress: list[ForecastAnswerRow] = Field(default_factory=list)
    summary: ForecastSummary | None = None


class ForecastState(Contract):
    case_ids: list[int]
    index: int
    issued: int
    confidence_style: Literal["numeric", "words"]
    answers: list[ForecastAnswerRow] = Field(default_factory=list)
    pending_reveal: bool = False
    reveal_case_id: int | None = None


router = APIRouter(prefix="/api/v1/retail/forecast", tags=["Synthetic forecast quiz"])

_SYN_LABELS = (
    "SYN-Alpha",
    "SYN-Beta",
    "SYN-Gamma",
    "SYN-Delta",
    "SYN-Epsilon",
    "SYN-Zeta",
    "SYN-Eta",
    "SYN-Theta",
    "SYN-Iota",
    "SYN-Kappa",
    "SYN-Lambda",
    "SYN-Mu",
)


def _path(case_id: int) -> list[float]:
    """Deterministic synthetic path; every seed is kept (no survivor selection)."""
    values: list[float] = []
    price = 100.0
    for i in range(HISTORY + FUTURE):
        drift = 0.0004 * math.sin(case_id * 0.37 + i * 0.05)
        shock = 0.012 * math.sin(i * (0.31 + case_id * 0.017) + case_id)
        seasonal = 0.008 * math.sin(i * 0.11 + case_id * 0.7)
        trend = (case_id % 7 - 3) * 0.00015
        price *= math.exp(drift + shock + seasonal + trend)
        values.append(round(price, 6))
    return values


def _case(case_id: int) -> tuple[list[float], list[float], Decimal, Actual, str]:
    full = _path(case_id)
    hist = full[:HISTORY]
    future = full[HISTORY : HISTORY + FUTURE]
    ret = (Decimal(str(future[-1])) / Decimal(str(hist[-1])) - 1) * Decimal(100)
    if ret > SIDEWAYS_PCT:
        actual: Actual = "up"
    elif ret < -SIDEWAYS_PCT:
        actual = "down"
    else:
        actual = "sideways"
    label = f"{_SYN_LABELS[case_id % len(_SYN_LABELS)]}-{case_id:02d}"
    return hist, future, ret, actual, label


def _sign(state: ForecastState) -> str:
    payload = base64.urlsafe_b64encode(state.model_dump_json().encode()).decode()
    signature = hmac.new(_CURSOR_KEY, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def _load(token: str) -> ForecastState:
    try:
        payload, signature = token.split(":")
        expected = hmac.new(_CURSOR_KEY, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature mismatch")
        state = ForecastState.model_validate_json(base64.urlsafe_b64decode(payload))
    except (ValueError, TypeError) as error:
        raise HTTPException(422, "Invalid forecast cursor") from error
    age = int(datetime.now(UTC).timestamp()) - state.issued
    if not 0 <= age <= 3600:
        raise HTTPException(422, "Forecast quiz expired; start a new quiz")
    if len(state.case_ids) != QUESTION_COUNT or any(
        not 0 <= case_id < CASE_POOL for case_id in state.case_ids
    ):
        raise HTTPException(422, "Invalid forecast quiz state")
    return state


def _result(prediction: Direction, actual: Actual) -> Result:
    if actual == "sideways":
        return "sideways"
    return "hit" if prediction == actual else "miss"


def _summary(answers: list[ForecastAnswerRow]) -> ForecastSummary:
    hits = sum(1 for row in answers if row.result == "hit")
    misses = sum(1 for row in answers if row.result == "miss")
    sideways = sum(1 for row in answers if row.result == "sideways")
    resolved = [row for row in answers if row.result != "sideways"]
    effectiveness = (
        (Decimal(hits) / Decimal(len(resolved)) * Decimal(100)).quantize(Decimal("0.1"))
        if resolved
        else None
    )
    mean_conf = (
        sum((Decimal(row.confidence) for row in answers), Decimal(0)) / Decimal(len(answers))
    ).quantize(Decimal("0.1"))
    hit_conf = [row.confidence for row in answers if row.result == "hit"]
    miss_conf = [row.confidence for row in answers if row.result == "miss"]
    briers: list[Decimal] = []
    for row in resolved:
        probability = Decimal(row.confidence) / Decimal(100)
        outcome = Decimal(1 if row.result == "hit" else 0)
        briers.append((probability - outcome) ** 2)
    buckets: dict[int, list[ForecastAnswerRow]] = {}
    for row in resolved:
        buckets.setdefault(row.confidence, []).append(row)
    by_confidence: list[dict[str, Decimal | int | str]] = []
    for confidence in sorted(buckets):
        group = buckets[confidence]
        group_hits = sum(1 for row in group if row.result == "hit")
        by_confidence.append(
            {
                "confidence": f"{confidence}%",
                "accuracy_pct": (Decimal(group_hits) / Decimal(len(group)) * Decimal(100)).quantize(
                    Decimal("0.1")
                ),
                "count": len(group),
            }
        )
    most = max(answers, key=lambda row: (row.confidence, -row.question_no)) if answers else None
    return ForecastSummary(
        hits=hits,
        misses=misses,
        sideways=sideways,
        effectiveness_pct=effectiveness,
        mean_confidence=mean_conf,
        mean_confidence_hit=(
            (
                sum((Decimal(value) for value in hit_conf), Decimal(0)) / Decimal(len(hit_conf))
            ).quantize(Decimal("0.1"))
            if hit_conf
            else None
        ),
        mean_confidence_miss=(
            (
                sum((Decimal(value) for value in miss_conf), Decimal(0)) / Decimal(len(miss_conf))
            ).quantize(Decimal("0.1"))
            if miss_conf
            else None
        ),
        mean_brier=(
            (sum(briers, Decimal(0)) / Decimal(len(briers))).quantize(Decimal("0.001"))
            if briers
            else None
        ),
        by_confidence=by_confidence,
        most_confident=most,
    )


def _active_case_id(state: ForecastState) -> int:
    if state.pending_reveal and state.reveal_case_id is not None:
        return state.reveal_case_id
    if state.index >= QUESTION_COUNT:
        return state.case_ids[-1]
    return state.case_ids[state.index]


def _round(state: ForecastState, reveal: ForecastReveal | None = None) -> ForecastRound:
    finished = state.index >= QUESTION_COUNT and not state.pending_reveal
    case_id = _active_case_id(state)
    hist, _future, _ret, _actual, instrument = _case(case_id)
    if finished:
        question_no = QUESTION_COUNT
    elif state.pending_reveal:
        question_no = len(state.answers)
    else:
        question_no = state.index + 1
    return ForecastRound(
        token=_sign(state),
        question_no=question_no,
        instrument=instrument,
        hist_values=hist,
        confidence_style=state.confidence_style,
        reveal=reveal,
        finished=finished,
        progress=state.answers,
        summary=_summary(state.answers) if finished else None,
    )


@router.post("/start", response_model=ForecastRound)
def start_forecast(request: ForecastStart | None = None) -> ForecastRound:
    style = request.confidence_style if request is not None else "numeric"
    issued = int(datetime.now(UTC).timestamp())
    start = issued % CASE_POOL
    case_ids = [(start + i * 7) % CASE_POOL for i in range(QUESTION_COUNT)]
    state = ForecastState(
        case_ids=case_ids,
        index=0,
        issued=issued,
        confidence_style=style,
    )
    return _round(state)


@router.post(
    "/answer",
    response_model=ForecastRound,
    dependencies=[Depends(require_expensive_capacity)],
)
def answer_forecast(request: ForecastAnswer) -> ForecastRound:
    state = _load(request.token)
    if state.pending_reveal:
        raise HTTPException(422, "Acknowledge the reveal before the next forecast")
    if state.index >= QUESTION_COUNT:
        raise HTTPException(422, "Forecast quiz already finished; start a new quiz")
    if request.confidence % 10 != 0:
        raise HTTPException(422, "Confidence must be one of 50, 60, 70, 80, 90, 100")

    case_id = state.case_ids[state.index]
    _hist, future, ret, actual, _instrument = _case(case_id)
    result = _result(request.prediction, actual)
    row = ForecastAnswerRow(
        question_no=state.index + 1,
        case_id=case_id,
        prediction=request.prediction,
        confidence=request.confidence,
        future_return_pct=ret.quantize(Decimal("0.000001")),
        actual=actual,
        result=result,
    )
    state.answers.append(row)
    state.index += 1
    should_reveal = state.index % REVEAL_EVERY == 0 or state.index >= QUESTION_COUNT
    if should_reveal:
        state.pending_reveal = True
        state.reveal_case_id = case_id
        reveal = ForecastReveal(
            future_values=future,
            future_return_pct=row.future_return_pct,
            actual=actual,
            result=result,
        )
        return _round(state, reveal=reveal)
    return _round(state)


@router.post(
    "/continue",
    response_model=ForecastRound,
    dependencies=[Depends(require_expensive_capacity)],
)
def continue_after_reveal(request: ForecastContinue) -> ForecastRound:
    state = _load(request.token)
    if not state.pending_reveal:
        raise HTTPException(422, "No reveal to acknowledge")
    state.pending_reveal = False
    state.reveal_case_id = None
    return _round(state)
