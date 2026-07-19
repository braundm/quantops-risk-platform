"""Core QuantOps entities and the portfolio aggregate."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from quantops_domain._validation import (
    as_utc,
    fail,
    freeze_json_object,
    require_decimal,
    require_int,
    require_text,
    require_uuid,
)
from quantops_domain.enums import AssetClass
from quantops_domain.errors import CurrencyMismatchError, OptimisticConcurrencyError
from quantops_domain.value_objects import (
    Currency,
    InstrumentIdentity,
    InstrumentSymbol,
    Money,
)

_TAG_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,31}$")


@dataclass(frozen=True, slots=True)
class _Unset:
    pass


_UNSET = _Unset()


def _require_bool(value: bool, field_name: str) -> bool:
    if not isinstance(value, bool):
        fail(field_name, "must be a boolean")
    return value


def _freeze_tags(tags: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(tags, Mapping):
        fail("tags", "must be a mapping")
    if len(tags) > 20:
        fail("tags", "must contain at most 20 entries")
    normalized: dict[str, str] = {}
    for raw_key, raw_value in tags.items():
        if not isinstance(raw_key, str):
            fail("tags", "keys must be strings")
        key = raw_key.strip().casefold()
        if _TAG_KEY.fullmatch(key) is None:
            fail("tags", f"invalid key {raw_key!r}")
        if key in normalized:
            fail("tags", f"duplicate normalized key {key!r}")
        normalized[key] = require_text(
            raw_value,
            f"tags.{key}",
            maximum=100,
            allow_empty=False,
        )
    return MappingProxyType(dict(sorted(normalized.items())))


@dataclass(frozen=True, slots=True)
class Instrument:
    """A market instrument identified uniquely by source and canonical symbol."""

    id: UUID
    source: str
    symbol: InstrumentSymbol
    name: str
    asset_class: AssetClass
    quote_currency: Currency
    price_scale: int
    timezone: str
    calendar: str
    is_demo: bool
    created_at: datetime
    updated_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict, hash=False, repr=False)

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        source = require_text(self.source, "source", maximum=64).casefold()
        if not isinstance(self.symbol, InstrumentSymbol):
            fail("symbol", "must be InstrumentSymbol")
        name = require_text(self.name, "name", maximum=160)
        if not isinstance(self.asset_class, AssetClass):
            fail("asset_class", "must be AssetClass")
        if not isinstance(self.quote_currency, Currency):
            fail("quote_currency", "must be Currency")
        require_int(self.price_scale, "price_scale", minimum=0, maximum=18)
        timezone = require_text(self.timezone, "timezone", maximum=64)
        calendar = require_text(self.calendar, "calendar", maximum=64)
        _require_bool(self.is_demo, "is_demo")
        created_at = as_utc(self.created_at, "created_at")
        updated_at = as_utc(self.updated_at, "updated_at")
        if updated_at < created_at:
            fail("updated_at", "must not precede created_at")
        metadata = freeze_json_object(self.metadata, "metadata", max_bytes=16_384)

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "timezone", timezone)
        object.__setattr__(self, "calendar", calendar)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "updated_at", updated_at)
        object.__setattr__(self, "metadata", metadata)

    @property
    def identity(self) -> InstrumentIdentity:
        return InstrumentIdentity(self.source, self.symbol)

    @classmethod
    def create(
        cls,
        *,
        source: str,
        symbol: str,
        name: str,
        asset_class: AssetClass,
        quote_currency: str,
        price_scale: int,
        timezone: str,
        calendar: str,
        is_demo: bool,
        now: datetime,
        metadata: Mapping[str, Any] | None = None,
        instrument_id: UUID | None = None,
    ) -> Instrument:
        return cls(
            id=instrument_id or uuid4(),
            source=source,
            symbol=InstrumentSymbol(symbol),
            name=name,
            asset_class=asset_class,
            quote_currency=Currency(quote_currency),
            price_scale=price_scale,
            timezone=timezone,
            calendar=calendar,
            is_demo=is_demo,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )


@dataclass(frozen=True, slots=True)
class Portfolio:
    """Portfolio aggregate with explicit copy-on-write optimistic concurrency."""

    id: UUID
    name: str
    base_currency: Currency
    description: str | None
    is_demo: bool
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        name = require_text(self.name, "name", maximum=120)
        if not isinstance(self.base_currency, Currency):
            fail("base_currency", "must be Currency")
        description = self.description
        if description is not None:
            description = require_text(
                description,
                "description",
                maximum=2_000,
                allow_empty=True,
            )
        _require_bool(self.is_demo, "is_demo")
        require_int(self.version, "version", minimum=1)
        created_at = as_utc(self.created_at, "created_at")
        updated_at = as_utc(self.updated_at, "updated_at")
        if updated_at < created_at:
            fail("updated_at", "must not precede created_at")

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "updated_at", updated_at)

    @classmethod
    def create(
        cls,
        *,
        name: str,
        base_currency: str,
        description: str | None,
        is_demo: bool,
        now: datetime,
        portfolio_id: UUID | None = None,
    ) -> Portfolio:
        return cls(
            id=portfolio_id or uuid4(),
            name=name,
            base_currency=Currency(base_currency),
            description=description,
            is_demo=is_demo,
            version=1,
            created_at=now,
            updated_at=now,
        )

    def assert_version(self, expected_version: int) -> None:
        require_int(expected_version, "expected_version", minimum=1)
        if expected_version != self.version:
            raise OptimisticConcurrencyError(self.id, expected_version, self.version)

    def revise(
        self,
        *,
        expected_version: int,
        updated_at: datetime,
        name: str | _Unset = _UNSET,
        description: str | None | _Unset = _UNSET,
    ) -> Portfolio:
        """Return a new version, or self for a semantically identical update."""

        self.assert_version(expected_version)
        normalized_updated_at = as_utc(updated_at, "updated_at")
        if normalized_updated_at < self.updated_at:
            fail("updated_at", "must not move backwards")

        next_name = (
            self.name if isinstance(name, _Unset) else require_text(name, "name", maximum=120)
        )
        next_description = self.description
        if not isinstance(description, _Unset):
            next_description = (
                None
                if description is None
                else require_text(
                    description,
                    "description",
                    maximum=2_000,
                    allow_empty=True,
                )
            )
        if next_name == self.name and next_description == self.description:
            return self
        return replace(
            self,
            name=next_name,
            description=next_description,
            version=self.version + 1,
            updated_at=normalized_updated_at,
        )


@dataclass(frozen=True, slots=True)
class Position:
    """An exact, dated holding in one instrument and one explicit currency."""

    id: UUID
    portfolio_id: UUID
    instrument_id: UUID
    quantity: Decimal
    average_cost: Decimal
    currency: Currency
    as_of: datetime
    tags: Mapping[str, str] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        require_uuid(self.portfolio_id, "portfolio_id")
        require_uuid(self.instrument_id, "instrument_id")
        require_decimal(self.quantity, "quantity")
        require_decimal(self.average_cost, "average_cost", minimum=Decimal("0"))
        if not isinstance(self.currency, Currency):
            fail("currency", "must be Currency")
        as_of = as_utc(self.as_of, "as_of")
        tags = _freeze_tags(self.tags)
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "tags", tags)

    @classmethod
    def create(
        cls,
        *,
        portfolio_id: UUID,
        instrument_id: UUID,
        quantity: Decimal,
        average_cost: Decimal,
        currency: str,
        as_of: datetime,
        tags: Mapping[str, str] | None = None,
        position_id: UUID | None = None,
    ) -> Position:
        return cls(
            id=position_id or uuid4(),
            portfolio_id=portfolio_id,
            instrument_id=instrument_id,
            quantity=quantity,
            average_cost=average_cost,
            currency=Currency(currency),
            as_of=as_of,
            tags=tags or {},
        )

    @property
    def cost_basis(self) -> Money:
        return Money(self.average_cost * self.quantity, self.currency)

    def market_value(self, unit_price: Money) -> Money:
        if unit_price.currency != self.currency:
            raise CurrencyMismatchError(str(self.currency), str(unit_price.currency))
        return unit_price * self.quantity
