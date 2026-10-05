"""Accounting invariants: cash, flows, partial closes, derivatives and risk sample quality."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from quantops_risk.exceptions import InvalidInputError
from quantops_risk.investor_book import Entry, Instrument, analyze_book, stress_book

D = Decimal
DAY = date(2025, 1, 1)
STOCK = Instrument("A", "Stock", "equity", "Technology", D(1), D(1))
FUTURE = Instrument("F", "Future", "future", "Energy", D(1000), D("0.1"))


def test_cash_flows_do_not_create_investment_returns() -> None:
    days = [DAY + timedelta(days=i) for i in range(3)]
    result = analyze_book(
        [STOCK],
        [
            Entry("deposit", days[0], "deposit", amount_pln=D(1000)),
            Entry("buy", days[0], "buy", "A", D(2), D(100)),
            Entry("deposit2", days[1], "deposit", amount_pln=D(500)),
            Entry("withdraw", days[2], "withdrawal", amount_pln=D(200)),
        ],
        {"A": dict.fromkeys(days, D(100))},
        dict.fromkeys(days, D(1)),
        days[-1],
    )
    assert result.equity == result.net_deposits == 1300
    assert result.profit == 0
    assert result.twr == 0
    assert result.max_drawdown == 0


def test_spot_sale_realizes_average_cost_and_fees_once() -> None:
    end = DAY + timedelta(days=1)
    result = analyze_book(
        [STOCK],
        [
            Entry("deposit", DAY, "deposit", amount_pln=D(10000)),
            Entry("buy", DAY, "buy", "A", D(10), D(100), fee_pln=D(5)),
            Entry("sell", end, "sell", "A", D(4), D(120), fee_pln=D(3)),
            Entry("dividend", end, "dividend", "A", amount_pln=D(10)),
            Entry("fee", end, "fee", amount_pln=D(2)),
        ],
        {"A": {DAY: D(100), end: D(120)}},
        {DAY: D(4), end: D(5)},
        end,
    )
    assert result.positions[0].quantity == 6
    assert result.realized_pnl == 800  # 4*120*5 - 4*100*4
    assert result.positions[0].unrealized_pnl == 1200
    assert result.fees == 10 and result.dividends == 10
    assert result.equity == 12000
    assert result.profit == 2000


@pytest.mark.parametrize(
    "opening,closing,expected", [("buy", "sell", 20000), ("sell", "buy", -20000)]
)
def test_derivative_notional_is_not_cash_or_equity_and_close_realizes_once(
    opening: str, closing: str, expected: int
) -> None:
    end = DAY + timedelta(days=1)
    first = Entry("open", DAY, "buy" if opening == "buy" else "sell", "F", D(1), D(70))
    events = [Entry("cash", DAY, "deposit", amount_pln=D(50000)), first]
    quotes = {"F": {DAY: D(70), end: D(75)}}
    fx = {DAY: D(4), end: D(4)}
    marked = analyze_book([FUTURE], events, quotes, fx, end)
    assert marked.cash == 50000
    assert marked.equity == 50000 + expected
    assert marked.gross_exposure == 300000
    assert marked.margin_estimate == 30000
    assert marked.cash_after_margin == 20000
    assert marked.curve[0].equity == 50000
    closed = analyze_book(
        [FUTURE],
        [*events, Entry("close", end, "buy" if closing == "buy" else "sell", "F", D(1), D(75))],
        quotes,
        fx,
        end,
    )
    assert closed.cash == marked.equity
    assert closed.equity == marked.equity
    assert closed.realized_pnl == expected
    assert closed.positions == []


def test_partial_derivative_close_and_reversal_reset_entry_basis() -> None:
    days = [DAY + timedelta(days=i) for i in range(3)]
    result = analyze_book(
        [FUTURE],
        [
            Entry("cash", DAY, "deposit", amount_pln=D(100000)),
            Entry("open", DAY, "buy", "F", D(2), D(70)),
            Entry("partial", days[1], "sell", "F", D(1), D(75)),
            Entry("reverse", days[2], "sell", "F", D(2), D(80)),
        ],
        {"F": dict(zip(days, [D(70), D(75), D(80)], strict=True))},
        dict.fromkeys(days, D(1)),
        days[-1],
    )
    assert result.realized_pnl == 15000
    assert result.positions[0].quantity == -1
    assert result.positions[0].average_price == 80
    assert result.positions[0].opened == days[-1]
    assert result.positions[0].unrealized_pnl == 0


def test_scenario_respects_signed_notional_and_does_not_shock_pln_cash() -> None:
    book = analyze_book(
        [FUTURE],
        [
            Entry("cash", DAY, "deposit", amount_pln=D(50000)),
            Entry("open", DAY, "buy", "F", D(1), D(70)),
        ],
        {"F": {DAY: D(70)}},
        {DAY: D(4)},
        DAY,
    )
    scenario = stress_book(book, [FUTURE], D(4), D(0), D("0.1"), D("-0.1"), D(0))
    assert scenario.pnl == D(-30800)  # -7 USD/barrel * 1000 barrels * 4.4 PLN/USD
    assert scenario.equity_after == D(19200)


def test_duplicate_transactions_missing_dates_and_overselling_are_rejected() -> None:
    deposit = Entry("cash", DAY, "deposit", amount_pln=D(1000))
    for events in (
        [deposit, deposit],
        [Entry("future", DAY + timedelta(days=1), "deposit", amount_pln=D(1))],
        [deposit, Entry("sell", DAY, "sell", "A", D(1), D(10))],
    ):
        with pytest.raises(InvalidInputError):
            analyze_book([STOCK], events, {"A": {DAY: D(10)}}, {DAY: D(1)}, DAY)


def test_insufficient_history_suppresses_precise_risk_and_large_loss_invalidates_twr() -> None:
    end = DAY + timedelta(days=1)
    book = analyze_book(
        [FUTURE],
        [
            Entry("cash", DAY, "deposit", amount_pln=D(100)),
            Entry("buy", DAY, "buy", "F", D(1), D(70)),
        ],
        {"F": {DAY: D(70), end: D(1)}},
        {DAY: D(1), end: D(1)},
        end,
    )
    assert book.equity < 0
    assert book.twr is None
    assert book.max_drawdown is None
    assert book.risk_status == "invalid_data"
    assert book.var95 is None and book.es95 is None


def test_expired_or_fractional_futures_are_rejected() -> None:
    instrument = Instrument("F", "Future", "future", "Energy", D(1000), D("0.1"), DAY)
    for quantity in (D(1), D("0.1")):
        with pytest.raises(InvalidInputError):
            analyze_book(
                [instrument],
                [Entry("buy", DAY, "buy", "F", quantity, D(70))],
                {"F": {DAY: D(70)}},
                {DAY: D(1)},
                DAY,
            )
