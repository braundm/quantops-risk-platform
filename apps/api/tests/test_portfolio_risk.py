from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from quantops_api.api.xtb import risk_example
from quantops_api.application.portfolio_risk import (
    CashBalance,
    EtfComposition,
    EtfHolding,
    ExposureMetadata,
    RiskHistory,
    RiskPrice,
    RiskRequest,
    RiskScenario,
    analyze_imported_risk,
)
from quantops_api.application.xtb_models import XtbBook, XtbRecord, record_id
from quantops_api.main import create_app


def small_request() -> RiskRequest:
    observed = datetime(2024, 1, 5, tzinfo=UTC)
    record = XtbRecord(
        id=record_id("123", "open", "a", None),
        account_number="123",
        source_id="a",
        kind="open",
        symbol="AAPL.US",
        name="Synthetic Apple",
        asset_type="equity",
        side="BUY",
        quantity=Decimal(1),
        price=Decimal(100),
        event_at=observed,
        observed_at=observed,
    )
    history = RiskHistory(
        symbol="AAPL.US",
        currency="USD",
        base_currency="PLN",
        source="Synthetic",
        source_url="https://example.com/synthetic",
        fx_source="Synthetic",
        origin="synthetic",
        fetched_at=observed,
        rows=[
            RiskPrice(
                date=date(2024, 1, 2) + timedelta(days=i),
                close=Decimal(price),
                adjusted_close=Decimal(price),
                fx_to_base=Decimal(4),
            )
            for i, price in enumerate((100, 110, 90, 100))
        ],
    )
    return RiskRequest(
        book=XtbBook(
            account_number="123", currency="PLN", records=[record], open_snapshot_at=observed
        ),
        histories=[history],
        cash_confirmed=True,
        cash=[
            CashBalance(
                symbol="CASH:PLN", currency="PLN", amount=Decimal(100), as_of=observed.date()
            )
        ],
        scenarios=[
            RiskScenario(
                name="Combined",
                class_shocks={"equity": Decimal("-0.2")},
                fx_shocks={"USD": Decimal("-0.1")},
            )
        ],
        tolerance_fraction=Decimal("0.1"),
    )


def test_import_value_scenarios_and_cash_reconcile_by_hand() -> None:
    result = analyze_imported_risk(small_request())
    assert result.before is not None
    assert result.before.value == 500
    assert result.before.weights == {"AAPL.US": Decimal("0.8"), "CASH:PLN": Decimal("0.2")}
    assert result.before.position_values == {"AAPL.US": Decimal(400), "CASH:PLN": Decimal(100)}
    assert result.before.var_amount is None
    scenario = result.before.scenarios[0]
    assert scenario.pnl == -112
    assert scenario.value_after == 388
    assert scenario.fraction == Decimal("-0.224")
    assert scenario.exceeds_tolerance
    assert sum(scenario.impacts.values()) == scenario.pnl
    assert result.before.risk.var_fraction is None
    assert result.before.performance.maximum_drawdown == pytest.approx(80 / 540)


def test_saved_securities_can_be_analyzed_without_inventing_account_cash() -> None:
    request = small_request().model_copy(
        update={"scope": "securities_only", "cash": [], "cash_confirmed": False}
    )
    result = analyze_imported_risk(request)
    assert result.scope == "securities_only"
    assert result.status == "complete"
    assert result.before is not None
    assert result.before.value == Decimal(400)
    assert result.before.weights == {"AAPL.US": Decimal(1)}
    assert result.before.scenarios[0].pnl == Decimal(-112)
    assert result.before.scenarios[0].value_after == Decimal(288)
    assert "securities_only_account_cash_not_included" in result.warnings
    assert "cash_balance_unconfirmed" not in result.warnings

    # The default full-account mode must retain the confirmed-cash gate.
    full = analyze_imported_risk(request.model_copy(update={"scope": "full_account"}))
    assert full.before is None
    assert "cash_balance_unconfirmed" in full.warnings


def test_securities_scope_rejects_an_account_cash_balance() -> None:
    body = small_request().model_dump()
    body["scope"] = "securities_only"
    with pytest.raises(ValueError, match="cannot include an account cash balance"):
        RiskRequest.model_validate(body)


@pytest.mark.parametrize("with_current_prices", [False, True])
def test_reconstructed_quantities_require_prices_after_the_latest_execution(
    with_current_prices: bool,
) -> None:
    request = small_request()
    first = request.book.records[0].model_dump()
    fills = [
        XtbRecord.model_validate(
            {
                **first,
                "kind": "fill",
                "source_id": str(day),
                "id": record_id("123", "fill", str(day), None),
                "event_at": datetime(2024, 1, day, tzinfo=UTC),
                "observed_at": datetime(2024, 1, 10, tzinfo=UTC),
            }
        )
        for day in (2, 8)
    ]
    request.book = XtbBook(
        account_number="123", currency="PLN", records=fills, ledger_complete=True
    )
    request.scope, request.cash, request.cash_confirmed = "securities_only", [], False
    if with_current_prices:
        request.histories[0].rows.append(
            RiskPrice(
                date=date(2024, 1, 9),
                close=Decimal(100),
                adjusted_close=Decimal(100),
                fx_to_base=Decimal(4),
            )
        )
    report = analyze_imported_risk(request)
    assert report.quantity_date == date(2024, 1, 8)
    if not with_current_prices:
        assert report.before is None
        assert "valuation_precedes_quantity_snapshot" in report.warnings
    else:
        assert report.before is not None and report.before.value == 800
        # A split after the first execution still requires explicit quantity reconciliation.
        request.histories[0].split_dates = [date(2024, 1, 4)]
        split = analyze_imported_risk(request)
        assert split.before is None
        assert split.excluded["AAPL.US"] == "split_requires_quantity_reconciliation"


def test_partial_closure_after_snapshot_advances_the_quantity_date() -> None:
    request = small_request()
    close_at = datetime(2024, 1, 8, tzinfo=UTC)
    closure = XtbRecord.model_validate(
        {
            **request.book.records[0].model_dump(),
            "kind": "closed",
            "id": record_id("123", "closed", "a", close_at),
            "close_at": close_at,
            "quantity": Decimal("0.5"),
            "observed_at": datetime(2024, 1, 10, tzinfo=UTC),
        }
    )
    request.book.records.append(closure)
    request.scope, request.cash, request.cash_confirmed = "securities_only", [], False
    report = analyze_imported_risk(request)
    assert report.quantity_date == close_at.date()
    assert report.before is None
    assert "valuation_precedes_quantity_snapshot" in report.warnings


def test_securities_scope_still_requires_complete_positions_and_history() -> None:
    request = small_request().model_copy(
        update={"scope": "securities_only", "cash": [], "cash_confirmed": False, "histories": []}
    )
    result = analyze_imported_risk(request)
    assert result.before is None
    assert result.coverage_fraction is None
    assert result.excluded["AAPL.US"] == "missing_history_or_fx"


def test_position_shock_overrides_class_and_never_double_counts() -> None:
    request = small_request()
    request.scenarios[0].position_shocks = {"AAPL.US": Decimal("-0.1")}
    result = analyze_imported_risk(request)
    assert result.before is not None
    assert result.before.scenarios[0].pnl == Decimal(-76)


def test_variant_same_capital_and_dates_never_mutates_book() -> None:
    request = small_request()
    before = request.book.model_dump_json()
    request.variant = {"AAPL.US": Decimal("0.5"), "CASH:PLN": Decimal("0.5")}
    result = analyze_imported_risk(request)
    assert result.before and result.after
    assert result.before.value == result.after.value == 500
    assert result.after.scenarios[0].pnl == -70
    assert result.before.risk.observations == result.after.risk.observations
    assert request.book.model_dump_json() == before


def test_missing_history_does_not_report_partial_book_as_complete() -> None:
    request = small_request()
    request.histories = []
    result = analyze_imported_risk(request)
    assert result.before is None
    assert result.coverage_fraction is None
    assert result.excluded["AAPL.US"] == "missing_history_or_fx"


def test_unconfirmed_cash_and_stale_balance_date_suppress_full_risk() -> None:
    request = small_request()
    request.cash_confirmed = False
    assert analyze_imported_risk(request).before is None
    request.cash_confirmed = True
    request.cash[0].as_of = date(2024, 1, 4)
    assert analyze_imported_risk(request).before is None


def test_common_calendar_never_fills_or_bridges_a_missing_instrument_date() -> None:
    request = risk_example()
    request.histories[0].rows.pop(100)
    result = analyze_imported_risk(request)
    assert result.before is not None
    assert result.history_dates == 339
    assert result.return_dates == 337
    assert result.skipped_pairs == 1


def test_history_window_does_not_change_current_capital_or_cash_date() -> None:
    request = small_request()
    request.end = date(2024, 1, 4)
    result = analyze_imported_risk(request)
    assert result.before is not None
    assert result.valuation_date == date(2024, 1, 5)
    assert result.period_end == date(2024, 1, 4)
    assert result.before.value == 500
    assert result.before.scenarios[-1].pnl == -40


def test_split_after_quantity_snapshot_blocks_unreconciled_current_valuation() -> None:
    request = small_request()
    request.histories[0].split_dates = [date(2024, 1, 5)]
    # A split already reflected in the dated snapshot is not counted a second time.
    assert analyze_imported_risk(request).before is not None
    request.book.open_snapshot_at = datetime(2024, 1, 4, tzinfo=UTC)
    request.book.records[0].observed_at = request.book.open_snapshot_at
    result = analyze_imported_risk(request)
    assert result.before is None
    assert result.excluded["AAPL.US"] == "split_requires_quantity_reconciliation"


def test_unknown_etf_holdings_and_metadata_are_explicit_not_listing_inferences() -> None:
    result = analyze_imported_risk(risk_example())
    assert result.before is not None
    assert result.etf_overlap[0]["status"] == "unknown"
    assert result.before.exposures["issuer_country"] == {"unknown": Decimal(1)}
    assert result.before.exposures["economic_currency"] == {"unknown": Decimal(1)}
    assert result.benchmark is not None


def test_supplied_partial_etf_composition_discloses_coverage_and_date() -> None:
    request = risk_example()
    request.etf_compositions = [
        EtfComposition(
            symbol="CSPX.UK",
            source_url="https://example.com/synthetic",
            as_of=date(2024, 1, 1),
            holdings=[EtfHolding(issuer_id="synthetic-issuer", weight=Decimal("0.4"))],
        )
    ]
    result = analyze_imported_risk(request)
    assert result.etf_overlap[0]["coverage"] == "0.4"
    assert result.etf_overlap[0]["as_of"] == "2024-01-01"
    request.metadata = [
        ExposureMetadata(
            symbol="AAPL.US",
            issuer_id="synthetic-issuer",
            source_url="https://example.com/synthetic",
            as_of=date(2024, 1, 1),
        )
    ]
    result = analyze_imported_risk(request)
    assert result.etf_overlap[1]["symbol"] == "CSPX.UK / AAPL.US"
    assert result.etf_overlap[1]["coverage"] == "0.4"


def test_adjusted_returns_do_not_treat_split_as_loss_or_add_dividends_again() -> None:
    request = small_request()
    for row, raw, adjusted in zip(
        request.histories[0].rows, (100, 100, 50, 50), (49, 49, 50, 50), strict=True
    ):
        row.close, row.adjusted_close = Decimal(raw), Decimal(adjusted)
    result = analyze_imported_risk(request)
    assert result.before is not None
    assert result.before.value == 300  # One current share at 50 USD * 4, plus 100 PLN cash.
    assert result.before.performance.period_return == pytest.approx((200 / 300) * (50 / 49 - 1))
    assert result.before.performance.maximum_drawdown == 0


def test_foreign_cash_has_only_fx_return_and_combined_shock() -> None:
    request = small_request()
    cash_history = request.histories[0].model_copy(deep=True)
    cash_history.symbol = "CASH:USD"
    for row in cash_history.rows:
        row.close = row.adjusted_close = Decimal(1)
        row.fx_to_base = Decimal(4)
    request.histories.append(cash_history)
    request.cash = [
        CashBalance(symbol="CASH:USD", currency="USD", amount=Decimal(25), as_of=date(2024, 1, 5))
    ]
    result = analyze_imported_risk(request)
    assert result.before is not None
    assert result.before.scenarios[0].pnl == -122  # -112 equity and -10 FX on cash.


def test_conflicting_currency_rates_are_rejected_instead_of_blended() -> None:
    request = small_request()
    history = request.histories[0].model_copy(deep=True)
    history.symbol = "MSFT.US"
    history.rows[0].fx_to_base = Decimal(5)
    request.histories.append(history)
    request.variant = {"MSFT.US": Decimal(1)}
    with pytest.raises(ValueError, match="Contradictory FX"):
        analyze_imported_risk(request)


def test_missing_benchmark_keeps_portfolio_period_and_new_variant_requires_history() -> None:
    request = small_request()
    request.benchmark = "CSPX.UK"
    result = analyze_imported_risk(request)
    assert result.before is not None
    assert result.benchmark is None
    request.variant = {"MSFT.US": Decimal(1)}
    result = analyze_imported_risk(request)
    assert result.before is None and result.after is None
    assert result.excluded["MSFT.US"] == "missing_history_or_fx"


def test_cfd_in_same_account_prevents_whole_portfolio_risk_claim() -> None:
    request = small_request()
    derivative = request.book.records[0].model_copy(deep=True)
    derivative.source_id = "cfd"
    derivative.id = record_id("123", "open", "cfd", None)
    derivative.symbol = "US500"
    derivative.asset_type = "cfd"
    request.book.records.append(derivative)
    result = analyze_imported_risk(request)
    assert result.before is None
    assert result.excluded["US500"] == "unsupported_derivative_or_unclassified"


def test_api_rejects_unbalanced_weights_wrong_fx_and_base_currency_shock() -> None:
    payload = small_request().model_dump(mode="json")
    with TestClient(create_app()) as client:
        for patch_value in (
            {"variant": {"AAPL.US": "0.9"}},
            {"scenarios": [{"name": "bad", "fx_shocks": {"PLN": "0.1"}}]},
            {"base_currency": "EUR"},
        ):
            response = client.post("/api/v1/xtb/risk", json={**payload, **patch_value})
            assert response.status_code == 422
            assert response.headers["content-type"].startswith("application/problem+json")


def test_provider_outage_is_explicit_and_service_free_example_is_analyzable() -> None:
    with TestClient(create_app()) as client:
        with patch(
            "quantops_api.application.portfolio_history_provider.fetch_adjusted_history",
            side_effect=ValueError("provider unavailable"),
        ):
            response = client.post(
                "/api/v1/xtb/risk-history",
                json={
                    "symbols": ["AAPL.US"],
                    "base_currency": "PLN",
                    "start": "2024-01-01",
                    "end": "2024-12-31",
                },
            )
        assert response.status_code == 200
        assert response.json()["histories"] == []
        assert "AAPL.US" in response.json()["failures"]
        demo = client.get("/api/v1/xtb/risk-example")
        analyzed = client.post("/api/v1/xtb/risk", json=demo.json())
        assert analyzed.status_code == 200
        assert analyzed.json()["status"] == "complete"
        assert "synthetic_history" in analyzed.json()["warnings"]
