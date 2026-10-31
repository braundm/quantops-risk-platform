"""Bounded user-supplied XTB report contracts; no authenticated broker connection."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from quantops_domain.value_objects import ISO_4217_CODES

Number = Annotated[Decimal, Field(allow_inf_nan=False, max_digits=36, decimal_places=18)]
Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False, max_digits=36, decimal_places=18)]


class ReportContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


def iso_currency(value: str) -> str:
    if value not in ISO_4217_CODES:
        raise ValueError("Choose an ISO 4217 account currency")
    return value


def utc_time(value: datetime) -> datetime:
    if value.utcoffset() is None or value > datetime.now(UTC):
        raise ValueError("Report times must be timezone aware and not future")
    return value.astimezone(UTC)


class XtbRecord(ReportContract):
    id: UUID
    account_number: str = Field(pattern=r"^[0-9]{1,20}$")
    kind: Literal["closed", "open", "fill", "cash"]
    source_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(default="", max_length=80)
    name: str = Field(default="", max_length=200)
    asset_type: Literal["equity", "etf", "cfd", "unknown"] = "unknown"
    side: Literal["BUY", "SELL"] | None = None
    quantity: Positive | None = None
    price: Positive | None = None
    event_at: datetime
    observed_at: datetime
    close_at: datetime | None = None
    close_price: Positive | None = None
    reported_pnl: Number | None = None
    cash_amount: Number | None = None
    operation: str = Field(default="", max_length=100)

    _event = field_validator("event_at", "observed_at")(utc_time)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.close_at is not None:
            self.close_at = utc_time(self.close_at)
        if self.kind != "cash" and (
            not self.symbol or self.side is None or self.quantity is None or self.price is None
        ):
            raise ValueError("A position or fill requires symbol, side, quantity and price")
        if self.kind == "cash" and self.cash_amount is None:
            raise ValueError("Cash operation requires an amount")
        if self.event_at > self.observed_at:
            raise ValueError("Event must not be later than report observation")
        if self.kind == "closed" and (
            self.close_at is None or not self.event_at <= self.close_at <= self.observed_at
        ):
            raise ValueError("Closed position requires a consistent closing timestamp")
        if self.kind != "closed" and self.close_at is not None:
            raise ValueError("Only closed positions may have a closing timestamp")
        if self.id != record_id(self.account_number, self.kind, self.source_id, self.close_at):
            raise ValueError("Record identity must match its account and broker event")
        return self


class XtbBook(ReportContract):
    account_number: str = Field(pattern=r"^[0-9]{1,20}$")
    currency: str
    records: list[XtbRecord] = Field(default_factory=list, max_length=20000)
    open_snapshot_at: datetime | None = None
    ledger_complete: bool = False

    _currency = field_validator("currency")(iso_currency)

    @model_validator(mode="after")
    def isolated(self) -> Self:
        if any(row.account_number != self.account_number for row in self.records):
            raise ValueError("Report account differs from the selected account")
        if len({row.id for row in self.records}) != len(self.records):
            raise ValueError("Duplicate report record IDs")
        kinds = {row.kind for row in self.records}
        if "fill" in kinds and ("open" in kinds or self.open_snapshot_at is not None):
            raise ValueError("Do not combine a transaction ledger and an open-position snapshot")
        if self.open_snapshot_at is not None:
            self.open_snapshot_at = utc_time(self.open_snapshot_at)
            if any(
                row.kind == "open" and row.observed_at != self.open_snapshot_at
                for row in self.records
            ):
                raise ValueError("Open records must belong to the selected snapshot")
        return self


class XtbPreview(ReportContract):
    book: XtbBook
    report_hash: str
    sheets: list[str]
    has_open_section: bool
    snapshot_at: datetime | None = None
    warnings: list[str]
    closed_count: int
    open_count: int
    fill_count: int
    cash_count: int

    @model_validator(mode="after")
    def coherent(self) -> Self:
        for kind in ("closed", "open", "fill", "cash"):
            if getattr(self, f"{kind}_count") != sum(row.kind == kind for row in self.book.records):
                raise ValueError("Preview counts must match records")
        if self.has_open_section != (self.snapshot_at is not None):
            raise ValueError("Open section requires a snapshot time")
        if self.open_count and not self.has_open_section:
            raise ValueError("Open positions require a snapshot")
        if self.snapshot_at is not None:
            self.snapshot_at = utc_time(self.snapshot_at)
            if any(
                row.kind == "open" and row.observed_at != self.snapshot_at
                for row in self.book.records
            ):
                raise ValueError("Open records must match the preview snapshot")
        return self


def record_id(account: str, kind: str, source_id: str, closed: datetime | None = None) -> UUID:
    return uuid5(NAMESPACE_URL, f"quantops:xtb:{account}:{kind}:{source_id}:{closed or ''}")
