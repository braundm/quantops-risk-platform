"""Property and invariant tests for numeric, temporal, and collection constraints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from quantops_contracts import (
    AiBriefRequestedPayload,
    EventType,
    PortfolioChangedPayload,
    PriceBarPayload,
    RiskSnapshotCreatedPayload,
    parse_event_json,
)

from .factories import (
    AT,
    REQUEST_ID,
    SNAPSHOT_ID,
    envelope,
    portfolio_changed,
    price_bar,
    snapshot_created,
)


@given(
    open_price=st.decimals(
        min_value=Decimal("1"),
        max_value=Decimal("10000"),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    ),
    close_price=st.decimals(
        min_value=Decimal("1"),
        max_value=Decimal("10000"),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    ),
    spread=st.decimals(
        min_value=Decimal("0"),
        max_value=Decimal("0.5"),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    ),
)
@settings(max_examples=40, deadline=None)
def test_valid_ohlc_round_trips_for_bounded_decimal_examples(
    open_price: Decimal,
    close_price: Decimal,
    spread: Decimal,
) -> None:
    low = min(open_price, close_price) - spread
    if low <= 0:
        low = Decimal("0.0001")
    payload = price_bar(
        open=open_price,
        high=max(open_price, close_price) + spread,
        low=low,
        close=close_price,
    )
    event = envelope(EventType.MARKET_PRICE_BAR_V1, payload, AT)
    parsed = parse_event_json(event.to_canonical_json())
    assert parsed.payload == payload


@pytest.mark.parametrize(
    "changes",
    [
        {"high": Decimal("99"), "open": Decimal("100"), "close": Decimal("101")},
        {"low": Decimal("102"), "open": Decimal("100"), "close": Decimal("101")},
    ],
)
def test_invalid_ohlc_relationships_are_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        price_bar(**changes)


@pytest.mark.parametrize("non_finite", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_prices_are_rejected(non_finite: Decimal) -> None:
    with pytest.raises(ValidationError):
        price_bar(open=non_finite)


def test_non_finite_risk_metrics_are_rejected() -> None:
    raw = snapshot_created().model_dump(mode="python")
    raw["value_at_risk_95"] = Decimal("NaN")
    with pytest.raises(ValidationError):
        RiskSnapshotCreatedPayload.model_validate(raw)


def test_expected_shortfall_cannot_be_below_var() -> None:
    raw = snapshot_created().model_dump(mode="python")
    raw["value_at_risk_95"] = Decimal("100")
    raw["expected_shortfall_95"] = Decimal("99")
    with pytest.raises(ValidationError, match="expected_shortfall_95"):
        RiskSnapshotCreatedPayload.model_validate(raw)


@pytest.mark.parametrize(
    "timestamp",
    [datetime(2024, 3, 4, 21, 0), datetime(2024, 3, 4, 22, 0, tzinfo=timezone(timedelta(hours=1)))],
)
def test_timestamp_must_be_explicit_utc(timestamp: datetime) -> None:
    with pytest.raises(ValidationError, match="UTC"):
        price_bar(timestamp=timestamp)


def test_nil_uuid_and_missing_synthetic_marker_are_rejected() -> None:
    raw = price_bar().model_dump(mode="python")
    raw["instrument_id"] = "00000000-0000-0000-0000-000000000000"
    raw.pop("is_synthetic")
    with pytest.raises(ValidationError) as captured:
        PriceBarPayload.model_validate(raw)
    errors = captured.value.errors()
    assert {error["loc"] for error in errors} >= {("instrument_id",), ("is_synthetic",)}


def test_collection_identifiers_must_be_unique() -> None:
    portfolio_raw = portfolio_changed().model_dump(mode="python")
    position = portfolio_raw["changed_position_ids"][0]
    portfolio_raw["changed_position_ids"] = (position, position)
    with pytest.raises(ValidationError, match="must be unique"):
        PortfolioChangedPayload.model_validate(portfolio_raw)

    with pytest.raises(ValidationError, match="must be unique"):
        AiBriefRequestedPayload(
            request_id=REQUEST_ID,
            snapshot_id=SNAPSHOT_ID,
            requested_at=AT,
            question="Explain the synthetic snapshot.",
            evidence_ids=("risk:snapshot:1", "risk:snapshot:1"),
            is_synthetic=True,
        )


def test_payload_models_reject_unknown_fields() -> None:
    raw = price_bar().model_dump(mode="python")
    raw["broker_order"] = "BUY"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PriceBarPayload.model_validate(raw)
