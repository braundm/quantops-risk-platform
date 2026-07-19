"""Async PostgreSQL engine and session construction."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Protocol

from pgvector.asyncpg import register_vector
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class _AsyncpgConnection(Protocol):
    async def execute(self, query: str) -> str: ...


class _AdaptedAsyncpgConnection(Protocol):
    def run_async(
        self,
        function: Callable[[_AsyncpgConnection], Awaitable[object]],
    ) -> object: ...


def create_engine(
    database_url: str,
    *,
    echo: bool = False,
    pool_pre_ping: bool = True,
) -> AsyncEngine:
    """Create the application engine; migrations own schema creation."""

    engine = create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=pool_pre_ping,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_connection_timezone(
        dbapi_connection: _AdaptedAsyncpgConnection,
        connection_record: object,
    ) -> None:
        """Ensure session-level timestamp rendering is deterministic."""

        del connection_record

        async def configure(driver_connection: _AsyncpgConnection) -> None:
            await driver_connection.execute("SET TIME ZONE 'UTC'")
            await register_vector(driver_connection)

        dbapi_connection.run_async(configure)

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return sessions that never expire entities implicitly after commit."""

    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a transaction-scoped session and rollback on failure."""

    async with factory() as session, session.begin():
        yield session
