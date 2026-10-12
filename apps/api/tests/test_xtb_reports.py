"""Synthetic reports exercise import invariants without personal data or live services."""

import base64
import hashlib
import io
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from quantops_api.application.stock_quotes import StockQuote
from quantops_api.application.xtb_book import analyze_book, merge_book
from quantops_api.application.xtb_models import XtbBook, XtbPreview
from quantops_api.application.xtb_quotes import mapped_stock
from quantops_api.application.xtb_reports import parse_report
from quantops_api.application.xtb_valuation import ImportedQuote, value_book
from quantops_api.main import create_app

OBSERVED = datetime(2026, 7, 1, tzinfo=UTC)
HEADER = "Instrument,Category,Ticker,Type,Volume,Open Price,Open Time (UTC),Position ID"
OPEN = HEADER + "\nSynthetic Apple,Stocks,AAPL.US,BUY,10,100,2026-06-01T10:00:00Z,1001\n"
FILLS = OPEN.replace("Position ID", "ID")


def test_local_demo_fixture_contains_only_normalized_synthetic_portfolio() -> None:
    fixture = Path(__file__).resolve().parents[3] / "apps/web/src/data/localDemo.json"
    seed = json.loads(fixture.read_text(encoding="utf-8"))
    assert seed["synthetic"] is True
    assert seed["counts"] == {
        "open": 20,
        "closed": 26,
        "cash": 76,
        "unique_symbols": 9,
    }
    account = seed["accounts"]["accounts"][0]
    book = XtbBook.model_validate(account["book"])
    assert len(book.records) == 122
    assert sum(record.kind == "open" for record in book.records) == 20
    analysis = analyze_book(book)
    assert len(analysis.holdings) == 20
    assert len(value_book(book, []).positions) == 9
    assert analysis.closed_count == 26
    assert analysis.cash_count == 76
    assert account["marks"] == []
    assert account["imports"][0]["hash"] == seed["source_sha256"]
    assert len(seed["profiles"]) == 2
    for profile in seed["profiles"]:
        credentials = profile["credentials"]
        login = credentials["login"]
        assert login in ("admin", "admin1")
        assert (
            hashlib.pbkdf2_hmac(
                "sha256",
                login.encode(),
                bytes.fromhex(credentials["salt"]),
                credentials["iterations"],
            ).hex()
            == credentials["digest"]
        )


def test_open_position_total_is_not_imported_as_a_trade() -> None:
    result = preview(OPEN + "Open positions total,,,,,,,\n")
    assert result.open_count == 1


def test_provenance_worksheet_is_ignored_only_with_known_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from quantops_api.application import xtb_reports

    sources = [
        ["Source Type", "Ticker", "Instrument / Dataset", "Market", "Data Used", "URL", "Notes"]
    ]
    tables = {
        "Open Positions": [row.split(",") for row in OPEN.strip().splitlines()],
        "Sources": sources,
    }
    monkeypatch.setattr(xtb_reports, "tables_from_file", lambda *_: tables)
    assert preview().open_count == 1
    sources[0] = ["Unknown provenance format"]
    with pytest.raises(ValueError, match="source-provenance"):
        preview()


def preview(text: str = OPEN, filename: str = "open.csv") -> XtbPreview:
    return parse_report(filename, text.encode(), "111111", "USD", OBSERVED)


def merge(p: XtbPreview, current: XtbBook | None = None, ledger: bool = False) -> XtbBook:
    return merge_book(
        current or XtbBook(account_number="111111", currency="USD"),
        p,
        complete_snapshot=p.has_open_section,
        complete_ledger=ledger,
    )[0]


def xlsx(text: str, sheet: str = "Open Positions", formula: bool = False) -> bytes:
    """Synthetic inline-string workbook deliberately carries an incorrect A1 dimension."""
    rows = []
    for index, line in enumerate(text.strip().splitlines(), 1):
        cells = []
        for column, value in enumerate(line.split(",")):
            reference = chr(65 + column) + str(index)
            node = "<f>1+1</f>" if formula else f"<is><t>{escape(value)}</t></is>"
            cells.append(f'<c r="{reference}" t="inlineStr">{node}</c>')
        rows.append(f'<row r="{index}">{"".join(cells)}</row>')
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns:r="urn:rels"><sheets>'
            f'<sheet name="{sheet}" r:id="s1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="s1" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet><dimension ref="A1"/><sheetData>{"".join(rows)}</sheetData></worksheet>',
        )
    return output.getvalue()


def test_buy_without_sale_remains_open_and_partial_sale_reduces_average_cost() -> None:
    text = FILLS + "Synthetic Apple,Stocks,AAPL.US,SELL,3,120,2026-06-02T10:00:00Z,1002\n"
    book = merge(preview(text), ledger=True)
    holding = analyze_book(book).holdings[0]
    assert (holding.quantity, holding.cost) == (Decimal(7), Decimal(700))
    assert analyze_book(book).holdings_status == "reconstructed"
    assert analyze_book(merge(preview(FILLS))).holdings_status == "incomplete"


def test_complete_sale_removes_holding_and_oversell_is_atomic() -> None:
    sale = "Synthetic Apple,Stocks,AAPL.US,SELL,10,120,2026-06-02T10:00:00Z,1002\n"
    assert analyze_book(merge(preview(FILLS + sale), ledger=True)).holdings == []
    with pytest.raises(ValueError):
        merge(preview(FILLS + sale.replace("SELL,10", "SELL,11")), ledger=True)


def test_same_timestamp_numeric_execution_order_is_stable() -> None:
    buy = FILLS.replace("1001", "2")
    sale = "Synthetic Apple,Stocks,AAPL.US,SELL,3,120,2026-06-01T10:00:00Z,10\n"
    assert analyze_book(merge(preview(buy + sale), ledger=True)).holdings[0].quantity == 7


def test_partial_close_after_snapshot_reconciles_without_creating_short_shares() -> None:
    book = merge(preview())
    close = OPEN.replace("Position ID", "Close Time (UTC),Position ID")
    close = close.replace("BUY,10", "BUY,3").replace(",1001\n", ",2026-07-02T10:00:00Z,1001\n")
    p = parse_report(
        "closed.csv", close.encode(), "111111", "USD", datetime(2026, 7, 3, tzinfo=UTC)
    )
    assert analyze_book(merge(p, book)).holdings[0].quantity == 7


def test_cfd_and_owned_shares_with_same_symbol_have_separate_quantities() -> None:
    p = preview(OPEN + "Synthetic CFD,CFD,AAPL.US,SELL,2,100,2026-06-01T10:00:00Z,1002\n")
    rows = value_book(merge(p), []).positions
    assert len(rows) == 2
    assert {(row.asset_type, row.side, row.quantity) for row in rows} == {
        ("cfd", "SELL", Decimal(2)),
        ("equity", "BUY", Decimal(10)),
    }


def test_idempotency_account_isolation_and_conflicts() -> None:
    p = preview(FILLS)
    book = merge(p, ledger=True)
    again, duplicates = merge_book(book, p, complete_snapshot=False, complete_ledger=True)
    assert duplicates == 1 and again == book
    with pytest.raises(ValueError, match="Conflicting"):
        merge(preview(FILLS.replace("BUY,10", "BUY,11")), book, ledger=True)
    with pytest.raises(ValueError, match="account"):
        merge(p, XtbBook(account_number="222222", currency="USD"), ledger=True)


def test_full_snapshot_replacement_empty_snapshot_and_stale_rejection() -> None:
    book = merge(preview())
    assert analyze_book(book).holdings[0].quantity == 10
    updated = merge(preview(OPEN.replace("BUY,10", "BUY,8")), book)
    assert analyze_book(updated).holdings[0].quantity == 8
    empty = parse_report("empty.xlsx", xlsx(HEADER), "111111", "USD", OBSERVED)
    assert analyze_book(merge(empty, book)).holdings == []
    older = preview().model_copy(update={"snapshot_at": datetime(2026, 6, 1, tzinfo=UTC)})
    with pytest.raises(ValueError, match="older"):
        merge(older, book)
    with pytest.raises(ValueError, match="Confirm"):
        merge_book(
            XtbBook(account_number="111111", currency="USD"),
            preview(),
            complete_snapshot=False,
            complete_ledger=False,
        )


def test_closed_history_does_not_imply_empty_portfolio_or_double_count_cash() -> None:
    closed = OPEN.replace("Position ID", "Close Time (UTC),Profit/Loss,Position ID")
    closed = closed.replace(",1001\n", ",2026-06-03T10:00:00Z,25,1001\n")
    cash = (
        "Type,Ticker,Instrument,Time,Amount,ID\n"
        "Close trade,AAPL.US,Synthetic Apple,2026-06-03T10:00:00Z,25,9001"
    )
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("closed.csv", closed)
        archive.writestr("cash.csv", cash)
    p = parse_report("history.zip", output.getvalue(), "111111", "USD", OBSERVED)
    result = analyze_book(merge(p))
    assert result.holdings_status == "unknown"
    assert result.holdings == [] and result.reported_realized_pnl == result.cash_movement == 25


def test_xlsx_in_zip_ignores_bad_dimensions_and_detects_cfd() -> None:
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("111111/USD_111111_report.xlsx", xlsx(OPEN.replace("Stocks", "CFD")))
    p = parse_report("report.zip", output.getvalue(), "111111", "USD", OBSERVED)
    book = merge(p)
    assert p.open_count == 1 and analyze_book(book).holdings[0].status == "derivative_unavailable"
    assert value_book(book, []).positions[0].value is None
    with pytest.raises(ValueError, match="currency"):
        parse_report("report.zip", output.getvalue(), "111111", "PLN", OBSERVED)


@pytest.mark.parametrize("replacement", ["NaN", "Infinity", "-1", "0", "1e100"])
def test_invalid_numeric_report_is_rejected(replacement: str) -> None:
    with pytest.raises(ValueError):
        preview(OPEN.replace("BUY,10", f"BUY,{replacement}"))


def test_account_metadata_polish_csv_and_future_dates() -> None:
    with pytest.raises(ValueError, match="account"):
        preview("Account number,222222\n" + OPEN)
    polish = (
        "Nazwa;Kategoria;Symbol;Typ;Ilość;Cena;Czas UTC;ID\n"
        "Syntetyczne;Akcje;AAPL.US;BUY;1,5;100;2026-06-01T10:00:00Z;1001"
    )
    p = parse_report("raport.csv", polish.encode("utf-16"), "111111", "USD", OBSERVED)
    assert p.book.records[0].quantity == Decimal("1.5")
    with pytest.raises(ValueError):
        preview(OPEN.replace("2026-06-01", "2099-06-01"))


def test_formulas_unsafe_archives_and_entities_rejected() -> None:
    with pytest.raises(ValueError, match="formulas"):
        parse_report("report.xlsx", xlsx(OPEN, formula=True), "111111", "USD", OBSERVED)
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("../report.csv", OPEN)
    with pytest.raises(ValueError, match="Unsafe"):
        parse_report("report.zip", output.getvalue(), "111111", "USD", OBSERVED)
    from quantops_api.application.xtb_reports import xml

    with pytest.raises(ValueError, match="XML"):
        xml(b'<!DOCTYPE test [<!ENTITY x "test">]><test>&x;</test>')


def test_native_currency_valuation_and_split_suppresses_cost() -> None:
    book = merge(preview())
    stock = mapped_stock("AAPL.US")
    quote = StockQuote(
        stock=stock,
        requested_date=date(2026, 6, 1),
        purchase_reference_date=date(2026, 6, 1),
        purchase_reference_close=Decimal(100),
        latest_date=date(2026, 6, 30),
        latest_close=Decimal(120),
        fetched_at=OBSERVED,
        source_url="https://finance.yahoo.com/quote/AAPL/history/",
        provider="Synthetic test fixture",
    )
    mark = ImportedQuote(symbol="AAPL.US", quote=quote)
    result = value_book(book, [mark])
    assert result.totals[0].value == 1200 and result.totals[0].unrealized == 200
    assert result.coverage == "complete_spot_only"
    split = mark.model_copy(
        update={"quote": quote.model_copy(update={"corporate_action_review": True})}
    )
    assert value_book(book, [split]).totals[0].unrealized is None
    assert value_book(book, []).coverage == "partial_or_unknown"
    for symbol in ("OIL.WTI", "http://localhost/", "AAPL.UK"):
        with pytest.raises(ValueError):
            mapped_stock(symbol)


def test_api_preview_merge_value_validation_and_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from quantops_api.api import xtb

    def unavailable(symbol: str, purchased: date) -> StockQuote:
        raise ValueError("Synthetic provider outage")

    monkeypatch.setattr(xtb, "fetch_xtb_quote", unavailable)
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/xtb/preview",
            json={
                "account_number": "111111",
                "currency": "USD",
                "observed_at": OBSERVED.isoformat(),
                "filename": "open.csv",
                "content_base64": base64.b64encode(OPEN.encode()).decode(),
            },
        )
        assert response.status_code == 200
        response = client.post(
            "/api/v1/xtb/merge",
            json={
                "current": {"account_number": "111111", "currency": "USD"},
                "preview": response.json(),
                "complete_snapshot": True,
            },
        )
        assert response.status_code == 200
        book = response.json()["book"]
        assert (
            client.post("/api/v1/xtb/quote", json={"book": book, "symbol": "AAPL.US"}).status_code
            == 503
        )
        assert (
            client.post("/api/v1/xtb/value", json={"book": book}).json()["positions"][0]["quantity"]
            == "10.0000000000"
        )
        assert (
            client.post("/api/v1/xtb/analyze", json={**book, "currency": "ZZZ"}).status_code == 422
        )
