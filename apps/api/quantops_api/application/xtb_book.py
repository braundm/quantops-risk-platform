"""Idempotent local-book merging and conservative holdings derivation."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from quantops_risk.imported_holdings import SpotFill, reconstruct_spot

from quantops_api.application.xtb_models import ReportContract, XtbBook, XtbPreview


class ImportedHolding(ReportContract):
    symbol: str
    name: str
    asset_type: str
    side: str
    quantity: Decimal
    cost: Decimal | None
    opened_at: datetime
    status: Literal["spot", "derivative_unavailable", "classification_required"]


class XtbAnalysis(ReportContract):
    holdings: list[ImportedHolding]
    closed_count: int
    cash_count: int
    reported_realized_pnl: Decimal | None
    cash_movement: Decimal
    currency: str
    holdings_status: Literal["snapshot", "reconstructed", "incomplete", "unknown"]
    warnings: list[str]


def merge_book(
    current: XtbBook,
    preview: XtbPreview,
    *,
    complete_snapshot: bool,
    complete_ledger: bool,
) -> tuple[XtbBook, int]:
    incoming = preview.book
    if complete_ledger and not any(row.kind == "fill" for row in incoming.records):
        raise ValueError("A complete purchase ledger requires purchase or sale records")
    if (current.account_number, current.currency) != (incoming.account_number, incoming.currency):
        raise ValueError("Selected account number and currency must match the report book")
    if preview.has_open_section and not complete_snapshot:
        raise ValueError("Confirm that the supplied open-position section is a complete snapshot")
    if complete_snapshot and not preview.has_open_section:
        raise ValueError("This report contains no open-position section")
    if preview.has_open_section and preview.snapshot_at is None:
        raise ValueError("An open snapshot requires an observation timestamp")
    if (
        preview.snapshot_at
        and current.open_snapshot_at
        and preview.snapshot_at < current.open_snapshot_at
    ):
        raise ValueError("An older snapshot cannot replace the current open-position snapshot")
    existing = {row.id: row for row in current.records}
    duplicates = 0
    for row in incoming.records:
        old = existing.get(row.id)
        if old is not None:
            if (
                old.model_dump(exclude={"observed_at"}) != row.model_dump(exclude={"observed_at"})
                and row.kind != "open"
            ):
                raise ValueError(
                    "Conflicting broker event: previous imported history was preserved"
                )
            duplicates += 1
    if complete_snapshot:
        existing = {key: row for key, row in existing.items() if row.kind != "open"}
    for row in incoming.records:
        if row.id not in existing:
            existing[row.id] = row
    book = XtbBook(
        account_number=current.account_number,
        currency=current.currency,
        records=list(existing.values()),
        open_snapshot_at=preview.snapshot_at if complete_snapshot else current.open_snapshot_at,
        ledger_complete=current.ledger_complete or complete_ledger,
    )
    analyze_book(book)  # Reject oversells atomically before the browser persists the book.
    return book, duplicates


def analyze_book(book: XtbBook) -> XtbAnalysis:
    closed = [row for row in book.records if row.kind == "closed"]
    cash = [row for row in book.records if row.kind == "cash"]
    fills = [row for row in book.records if row.kind == "fill"]
    opens = [row for row in book.records if row.kind == "open"]
    holdings: list[ImportedHolding] = []
    warnings: list[str] = []
    status: Literal["snapshot", "reconstructed", "incomplete", "unknown"] = "unknown"
    if fills:
        if not book.ledger_complete:
            status = "incomplete"
            warnings.append(
                "Confirm complete purchase/sale history before reconstructing current holdings."
            )
        else:
            status = "reconstructed"
            spot_fills = []
            for index, row in enumerate(
                sorted(fills, key=lambda r: (r.event_at, r.source_id.zfill(100), r.source_id))
            ):
                if (
                    row.asset_type not in ("equity", "etf")
                    or row.side is None
                    or row.quantity is None
                    or row.price is None
                ):
                    warnings.append(
                        "Unclassified or derivative transaction excluded from spot reconstruction."
                    )
                    status = "incomplete"
                    continue
                spot_fills.append(
                    SpotFill(row.symbol, row.side, row.quantity, row.price, row.event_at, index)
                )
            for holding in reconstruct_spot(spot_fills):
                source = next(row for row in fills if row.symbol == holding.symbol)
                holdings.append(
                    ImportedHolding(
                        symbol=holding.symbol,
                        name=source.name or holding.symbol,
                        asset_type=source.asset_type,
                        side="BUY",
                        quantity=holding.quantity,
                        cost=holding.cost,
                        opened_at=holding.first_purchase,
                        status="spot",
                    )
                )
    elif book.open_snapshot_at is not None:
        status = "snapshot"
        for row in opens:
            if row.quantity is None or row.price is None:
                raise ValueError("Invalid open position")
            quantity = row.quantity
            later_closures = [
                c
                for c in closed
                if c.source_id == row.source_id
                and c.close_at is not None
                and c.close_at > book.open_snapshot_at
            ]
            for closure in later_closures:
                if (
                    closure.quantity is None
                    or closure.quantity > quantity
                    or closure.symbol != row.symbol
                ):
                    raise ValueError(
                        "Closing report cannot reconcile to the imported open position"
                    )
                quantity -= closure.quantity
            if not quantity:
                continue
            spot = row.asset_type in ("equity", "etf") and row.side == "BUY"
            holdings.append(
                ImportedHolding(
                    symbol=row.symbol,
                    name=row.name or row.symbol,
                    asset_type=row.asset_type,
                    side=row.side or "",
                    quantity=quantity,
                    cost=quantity * row.price if spot else None,
                    opened_at=row.event_at,
                    status="spot"
                    if spot
                    else "derivative_unavailable"
                    if row.asset_type == "cfd"
                    else "classification_required",
                )
            )
    else:
        warnings.append("A closed-position report does not establish current holdings.")
    pnl = sum((row.reported_pnl for row in closed if row.reported_pnl is not None), Decimal(0))
    return XtbAnalysis(
        holdings=holdings,
        closed_count=len(closed),
        cash_count=len(cash),
        reported_realized_pnl=pnl
        if closed and all(r.reported_pnl is not None for r in closed)
        else None,
        cash_movement=sum((r.cash_amount for r in cash if r.cash_amount is not None), Decimal(0)),
        currency=book.currency,
        holdings_status=status,
        warnings=warnings,
    )
