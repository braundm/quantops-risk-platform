"""Versioned public instrument specifications, independent of account access and quotes."""

from datetime import date, datetime
from functools import lru_cache
from importlib.resources import files
from typing import Literal, Self
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from quantops_domain.value_objects import ISO_4217_CODES

Broker = Literal["bossa", "xtb"]
InstrumentType = Literal[
    "equity",
    "etf",
    "etc",
    "etn",
    "etp",
    "bond",
    "option",
    "future",
    "cfd",
    "right",
    "warrant",
    "certificate",
    "other",
]
NAMESPACE = UUID("4dfaa2b6-297d-4f95-bbfe-4df5ac84f036")


class CatalogContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CatalogInstrument(CatalogContract):
    id: UUID
    broker: Broker
    symbol: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=500)
    instrument_type: InstrumentType
    market: str = Field(min_length=1, max_length=100)
    currency: str | None = None
    source_id: str
    source_category: str
    isin: str | None = None
    close_only: bool | None = None
    specifications: dict[str, str] = Field(default_factory=dict)
    valuation_status: Literal["reference_only"] = "reference_only"

    @field_validator("currency")
    @classmethod
    def iso_currency(cls, value: str | None) -> str | None:
        if value is not None and value not in ISO_4217_CODES:
            raise ValueError("Currency must be an ISO 4217 code or unknown")
        return value

    @model_validator(mode="after")
    def stable_identity(self) -> Self:
        expected = instrument_id(self.broker, self.instrument_type, self.market, self.symbol)
        if self.id != expected:
            raise ValueError("Catalog identity must include broker, type, market and symbol")
        return self


def instrument_id(broker: str, kind: str, market: str, symbol: str) -> UUID:
    return uuid5(NAMESPACE, "|".join((broker, kind, market, symbol)))


class CatalogSource(CatalogContract):
    id: str
    broker: Broker
    url: str
    fetched_at: datetime
    effective_date: date | None = None
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    count: int = Field(ge=0)
    expected_count: int | None = Field(default=None, ge=0)
    status: Literal["source_complete", "partial", "unavailable"]
    note: str

    @model_validator(mode="after")
    def provenance(self) -> Self:
        if self.fetched_at.utcoffset() is None:
            raise ValueError("Source timestamp must be timezone aware")
        if not self.url.startswith(
            ("https://bossa.pl/", "https://bossafx.pl/", "https://www.xtb.com/")
        ):
            raise ValueError("Source must be an official public specification")
        if self.status == "source_complete" and self.expected_count != self.count:
            raise ValueError("Complete source requires matching expected and actual counts")
        return self


class BrokerCatalog(CatalogContract):
    schema_version: Literal["broker-catalog@1.0.0"] = "broker-catalog@1.0.0"
    coverage: Literal["partial"] = "partial"
    sources: tuple[CatalogSource, ...]
    instruments: tuple[CatalogInstrument, ...]

    @model_validator(mode="after")
    def integrity(self) -> Self:
        ids = {row.id for row in self.instruments}
        sources = {source.id: source for source in self.sources}
        if len(ids) != len(self.instruments) or len(sources) != len(self.sources):
            raise ValueError("Duplicate instrument or source identities")
        for row in self.instruments:
            if row.source_id not in sources or sources[row.source_id].broker != row.broker:
                raise ValueError("Instrument must reference a source for its broker")
        for source in self.sources:
            if sum(row.source_id == source.id for row in self.instruments) != source.count:
                raise ValueError("Source count must match its instruments")
        return self


@lru_cache(maxsize=1)
def load_catalog() -> BrokerCatalog:
    return BrokerCatalog.model_validate_json(
        files("quantops_api").joinpath("data/broker_catalog.json").read_text(encoding="utf-8")
    )
