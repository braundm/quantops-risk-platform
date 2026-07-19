"""Explicit transaction boundary for state, audit, and outbox writes."""

from __future__ import annotations

from types import TracebackType

from quantops_domain import AuditEvent, DomainValidationError, OutboxEvent
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from quantops_api.infrastructure.persistence.repositories import (
    SqlAlchemyAuditEventRepository,
    SqlAlchemyInstrumentRepository,
    SqlAlchemyOutboxEventRepository,
    SqlAlchemyPortfolioRepository,
    SqlAlchemyPositionRepository,
    audit_model_from_domain,
    outbox_model_from_domain,
)


def append_audit_and_outbox(
    session: AsyncSession,
    *,
    audit_event: AuditEvent,
    outbox_event: OutboxEvent,
) -> None:
    """Stage audit and outbox rows together in the caller's transaction."""

    if audit_event.correlation_id != outbox_event.correlation_id:
        raise DomainValidationError("audit and outbox correlation IDs must match")
    session.add_all([audit_model_from_domain(audit_event), outbox_model_from_domain(outbox_event)])


class SqlAlchemyUnitOfWork:
    """Require an explicit commit; otherwise all pending work is rolled back."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("unit of work has not been entered")
        return self._session

    @property
    def instruments(self) -> SqlAlchemyInstrumentRepository:
        return SqlAlchemyInstrumentRepository(self.session)

    @property
    def portfolios(self) -> SqlAlchemyPortfolioRepository:
        return SqlAlchemyPortfolioRepository(self.session)

    @property
    def positions(self) -> SqlAlchemyPositionRepository:
        return SqlAlchemyPositionRepository(self.session)

    @property
    def audit_events(self) -> SqlAlchemyAuditEventRepository:
        return SqlAlchemyAuditEventRepository(self.session)

    @property
    def outbox_events(self) -> SqlAlchemyOutboxEventRepository:
        return SqlAlchemyOutboxEventRepository(self.session)

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        if self._session is not None:
            raise RuntimeError("unit of work cannot be entered twice")
        self._session = self._session_factory()
        self._committed = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_value, traceback
        if exc_type is not None or not self._committed:
            await self.session.rollback()
        await self.session.close()
        self._session = None

    async def commit(self) -> None:
        await self.session.commit()
        self._committed = True

    async def rollback(self) -> None:
        await self.session.rollback()
        self._committed = False

    async def append_audit_and_outbox(
        self,
        *,
        audit_event: AuditEvent,
        outbox_event: OutboxEvent,
    ) -> None:
        if audit_event.correlation_id != outbox_event.correlation_id:
            raise DomainValidationError("audit and outbox correlation IDs must match")
        await self.audit_events.append(audit_event)
        await self.outbox_events.add(outbox_event)
