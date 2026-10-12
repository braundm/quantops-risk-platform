"""Native-currency valuations of identified imported spot holdings and supplied price snapshots."""

from datetime import date
from decimal import Decimal

from quantops_risk.imported_holdings import mark_spot

from quantops_api.application.stock_quotes import StockQuote
from quantops_api.application.xtb_book import analyze_book
from quantops_api.application.xtb_models import ReportContract, XtbBook
from quantops_api.application.xtb_quotes import mapped_stock


class ImportedQuote(ReportContract):
    symbol: str
    quote: StockQuote


class ImportedValue(ReportContract):
    symbol: str
    asset_type: str
    side: str
    quantity: Decimal
    currency: str | None
    value: Decimal | None
    cost: Decimal | None
    unrealized: Decimal | None
    price_date: date | None
    status: str


class ImportedTotals(ReportContract):
    currency: str
    value: Decimal
    cost: Decimal | None
    unrealized: Decimal | None


class ImportedValuation(ReportContract):
    methodology: str = "imported-spot@1.0.0"
    origin: str = "user_supplied_report_and_price_snapshot"
    coverage: str
    positions: list[ImportedValue]
    totals: list[ImportedTotals]


def value_book(book: XtbBook, marks: list[ImportedQuote]) -> ImportedValuation:
    analysis = analyze_book(book)
    if len({mark.symbol for mark in marks}) != len(marks):
        raise ValueError("Duplicate price snapshots")
    by_symbol = {mark.symbol: mark.quote for mark in marks}
    symbols = {row.symbol for row in analysis.holdings}
    if set(by_symbol) - symbols:
        raise ValueError("Price snapshot does not match an imported holding")
    values: list[ImportedValue] = []
    groups = {(row.symbol, row.asset_type, row.side) for row in analysis.holdings}
    for symbol, asset_type, side in sorted(groups):
        holdings = [
            row
            for row in analysis.holdings
            if (row.symbol, row.asset_type, row.side) == (symbol, asset_type, side)
        ]
        quantity = sum((row.quantity for row in holdings), Decimal(0))
        status = "unpriced"
        price = None
        cost = None
        pnl = None
        currency = None
        price_date = None
        if any(row.status != "spot" for row in holdings):
            status = "derivative_or_unclassified"
        elif analysis.holdings_status in ("unknown", "incomplete"):
            status = "incomplete_history"
        elif symbol in by_symbol:
            quote = by_symbol[symbol]
            expected = mapped_stock(symbol)
            if quote.stock != expected or quote.requested_date != min(
                row.opened_at.date() for row in holdings
            ):
                raise ValueError(
                    "Price identifier, currency and opening date must match the imported book"
                )
            imported_cost = sum((row.cost for row in holdings if row.cost is not None), Decimal(0))
            price, cost, pnl = mark_spot(
                quantity, quote.latest_close, imported_cost, not quote.corporate_action_review
            )
            currency, price_date = expected.currency, quote.latest_date
            status = "corporate_action_review" if quote.corporate_action_review else "priced"
        values.append(
            ImportedValue(
                symbol=symbol,
                asset_type=asset_type,
                side=side,
                quantity=quantity,
                currency=currency,
                value=price,
                cost=cost,
                unrealized=pnl,
                price_date=price_date,
                status=status,
            )
        )
    totals: list[ImportedTotals] = []
    for currency in sorted({row.currency for row in values if row.currency is not None}):
        bucket = [row for row in values if row.currency == currency and row.value is not None]
        comparable = all(row.cost is not None for row in bucket)
        totals.append(
            ImportedTotals(
                currency=currency,
                value=sum((row.value for row in bucket if row.value is not None), Decimal(0)),
                cost=sum((row.cost for row in bucket if row.cost is not None), Decimal(0))
                if comparable
                else None,
                unrealized=sum(
                    (row.unrealized for row in bucket if row.unrealized is not None), Decimal(0)
                )
                if comparable
                else None,
            )
        )
    complete = analysis.holdings_status not in ("unknown", "incomplete") and all(
        row.value is not None for row in values
    )
    return ImportedValuation(
        coverage="complete_spot_only" if complete else "partial_or_unknown",
        positions=values,
        totals=totals,
    )
