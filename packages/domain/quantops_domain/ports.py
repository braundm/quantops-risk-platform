"""Framework-independent ports implemented by application infrastructure."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from types import TracebackType
from typing import Protocol, Self, runtime_checkable
from uuid import UUID

from quantops_domain.audit import AuditEvent
from quantops_domain.entities import Instrument, Portfolio, Position
from quantops_domain.outbox import OutboxEvent
from quantops_domain.value_objects import Currency, InstrumentIdentity


@runtime_checkable
class InstrumentRepository(Protocol):
    async def get(self, instrument_id: UUID) -> Instrument | None: ...

    async def get_by_identity(self, identity: InstrumentIdentity) -> Instrument | None: ...

    async def add(self, instrument: Instrument) -> None: ...


@runtime_checkable
class PortfolioRepository(Protocol):
    async def get(self, portfolio_id: UUID) -> Portfolio | None: ...

    async def add(self, portfolio: Portfolio) -> None: ...

    async def save(self, portfolio: Portfolio, *, expected_version: int) -> None:
        """Atomically persist only if storage still contains expected_version.

        Adapters must raise OptimisticConcurrencyError when the guarded update
        affects no row. For a change, ``portfolio.version`` is expected to be
        ``expected_version + 1``.
        """
        ...


@runtime_checkable
class PositionRepository(Protocol):
    async def get(self, position_id: UUID) -> Position | None: ...

    async def list_for_portfolio(
        self,
        portfolio_id: UUID,
        *,
        as_of: datetime | None = None,
    ) -> Sequence[Position]: ...

    async def upsert(self, position: Position) -> None: ...

    async def remove(self, position_id: UUID) -> None: ...


@runtime_checkable
class AuditEventRepository(Protocol):
    async def append(self, event: AuditEvent) -> None: ...


@runtime_checkable
class OutboxEventRepository(Protocol):
    async def add(self, event: OutboxEvent) -> None: ...

    async def claim_available(
        self,
        *,
        at: datetime,
        limit: int,
        worker_id: str,
    ) -> Sequence[OutboxEvent]: ...

    async def save(self, event: OutboxEvent) -> None: ...


@runtime_checkable
class FxRateProvider(Protocol):
    async def get_rate(
        self,
        *,
        source_currency: Currency,
        target_currency: Currency,
        as_of: datetime,
    ) -> Decimal:
        """Return target-currency units per one source-currency unit."""
        ...


class UnitOfWork(Protocol):
    """Transaction boundary that stores state and outbox events atomically."""

    instruments: InstrumentRepository
    portfolios: PortfolioRepository
    positions: PositionRepository
    audit_events: AuditEventRepository
    outbox_events: OutboxEventRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
