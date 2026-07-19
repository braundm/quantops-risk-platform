"""Async SQLAlchemy adapters for the framework-independent domain ports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, cast
from uuid import UUID

from quantops_domain import (
    AssetClass,
    AuditAction,
    AuditEvent,
    Currency,
    DomainValidationError,
    Instrument,
    InstrumentIdentity,
    InstrumentSymbol,
    OptimisticConcurrencyError,
    OutboxEvent,
    OutboxStatus,
    Portfolio,
    Position,
    to_primitive,
)
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from quantops_api.infrastructure.persistence.models import (
    AuditEventModel,
    InstrumentModel,
    OutboxEventModel,
    PortfolioModel,
    PositionModel,
)


def _json_object(value: object, field_name: str) -> dict[str, Any]:
    primitive = to_primitive(value)
    if not isinstance(primitive, dict) or not all(isinstance(key, str) for key in primitive):
        raise DomainValidationError(f"{field_name} must serialize to a JSON object")
    return cast(dict[str, Any], primitive)


def _require_numeric_38_12(value: Decimal, field_name: str) -> None:
    """Reject values PostgreSQL NUMERIC(38,12) would round or overflow."""

    quantum = Decimal("0.000000000001")
    with localcontext() as context:
        context.prec = max(50, len(value.as_tuple().digits) + 20)
        try:
            if value.quantize(quantum) != value:
                raise DomainValidationError(f"{field_name} exceeds NUMERIC(38,12) scale")
        except InvalidOperation as error:
            raise DomainValidationError(f"{field_name} exceeds NUMERIC(38,12) capacity") from error
    if not value.is_zero() and value.copy_abs().adjusted() >= 26:
        raise DomainValidationError(f"{field_name} exceeds NUMERIC(38,12) precision")


def instrument_from_model(model: InstrumentModel) -> Instrument:
    return Instrument(
        id=model.id,
        source=model.source,
        symbol=InstrumentSymbol(model.symbol),
        name=model.name,
        asset_class=AssetClass(model.asset_class),
        quote_currency=Currency(model.quote_currency),
        price_scale=model.price_scale,
        timezone=model.timezone,
        calendar=model.calendar,
        is_demo=model.is_demo,
        metadata=model.metadata_json,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def portfolio_from_model(model: PortfolioModel) -> Portfolio:
    return Portfolio(
        id=model.id,
        name=model.name,
        base_currency=Currency(model.base_currency),
        description=model.description,
        is_demo=model.is_demo,
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def position_from_model(model: PositionModel) -> Position:
    return Position(
        id=model.id,
        portfolio_id=model.portfolio_id,
        instrument_id=model.instrument_id,
        quantity=model.quantity,
        average_cost=model.average_cost,
        currency=Currency(model.currency),
        as_of=model.as_of,
        tags=model.tags,
    )


def audit_model_from_domain(event: AuditEvent) -> AuditEventModel:
    return AuditEventModel(
        id=event.id,
        action=event.action.value,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        actor_id=event.actor_id,
        occurred_at=event.occurred_at,
        correlation_id=event.correlation_id,
        details=_json_object(event.details, "audit details"),
    )


def audit_from_model(model: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        id=model.id,
        action=AuditAction(model.action),
        aggregate_type=model.aggregate_type,
        aggregate_id=model.aggregate_id,
        actor_id=model.actor_id,
        occurred_at=model.occurred_at,
        correlation_id=model.correlation_id,
        details=model.details,
    )


def outbox_model_from_domain(event: OutboxEvent) -> OutboxEventModel:
    return OutboxEventModel(
        id=event.id,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        event_type=event.event_type,
        schema_version=event.schema_version,
        producer=event.producer,
        idempotency_key=event.idempotency_key,
        occurred_at=event.occurred_at,
        available_at=event.available_at,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        status=event.status.value,
        attempts=event.attempts,
        published_at=event.published_at,
        error_summary=event.error_summary,
        event_envelope=_json_object(event.event_envelope, "event envelope"),
    )


def outbox_from_model(model: OutboxEventModel) -> OutboxEvent:
    payload = model.event_envelope.get("payload")
    if not isinstance(payload, Mapping):
        raise DomainValidationError("stored outbox envelope payload must be a JSON object")
    return OutboxEvent(
        id=model.id,
        aggregate_type=model.aggregate_type,
        aggregate_id=model.aggregate_id,
        event_type=model.event_type,
        schema_version=model.schema_version,
        producer=model.producer,
        idempotency_key=model.idempotency_key,
        occurred_at=model.occurred_at,
        available_at=model.available_at,
        correlation_id=model.correlation_id,
        causation_id=model.causation_id,
        payload=cast(Mapping[str, Any], payload),
        status=OutboxStatus(model.status),
        attempts=model.attempts,
        published_at=model.published_at,
        error_summary=model.error_summary,
    )


class SqlAlchemyInstrumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, instrument_id: UUID) -> Instrument | None:
        model = await self._session.get(InstrumentModel, instrument_id)
        return instrument_from_model(model) if model is not None else None

    async def get_by_identity(self, identity: InstrumentIdentity) -> Instrument | None:
        statement = select(InstrumentModel).where(
            InstrumentModel.source == identity.source,
            InstrumentModel.symbol == identity.symbol.value,
        )
        model = await self._session.scalar(statement)
        return instrument_from_model(model) if model is not None else None

    async def add(self, instrument: Instrument) -> None:
        self._session.add(
            InstrumentModel(
                id=instrument.id,
                source=instrument.source,
                symbol=instrument.symbol.value,
                name=instrument.name,
                asset_class=instrument.asset_class.value,
                quote_currency=instrument.quote_currency.code,
                price_scale=instrument.price_scale,
                timezone=instrument.timezone,
                calendar=instrument.calendar,
                is_demo=instrument.is_demo,
                metadata_json=_json_object(instrument.metadata, "instrument metadata"),
                created_at=instrument.created_at,
                updated_at=instrument.updated_at,
            )
        )


class SqlAlchemyPortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, portfolio_id: UUID) -> Portfolio | None:
        model = await self._session.get(PortfolioModel, portfolio_id)
        return portfolio_from_model(model) if model is not None else None

    async def add(self, portfolio: Portfolio) -> None:
        self._session.add(
            PortfolioModel(
                id=portfolio.id,
                name=portfolio.name,
                base_currency=portfolio.base_currency.code,
                description=portfolio.description,
                is_demo=portfolio.is_demo,
                version=portfolio.version,
                created_at=portfolio.created_at,
                updated_at=portfolio.updated_at,
            )
        )

    async def save(self, portfolio: Portfolio, *, expected_version: int) -> None:
        if portfolio.version != expected_version + 1:
            raise DomainValidationError(
                "portfolio.version must equal expected_version + 1 for a guarded update"
            )
        statement = (
            update(PortfolioModel)
            .where(
                PortfolioModel.id == portfolio.id,
                PortfolioModel.version == expected_version,
            )
            .values(
                name=portfolio.name,
                base_currency=portfolio.base_currency.code,
                description=portfolio.description,
                is_demo=portfolio.is_demo,
                version=portfolio.version,
                updated_at=portfolio.updated_at,
            )
            .execution_options(synchronize_session="fetch")
        )
        result = cast(CursorResult[Any], await self._session.execute(statement))
        if result.rowcount == 1:
            return
        actual_version = await self._session.scalar(
            select(PortfolioModel.version).where(PortfolioModel.id == portfolio.id)
        )
        if actual_version is None:
            raise LookupError(f"portfolio {portfolio.id} does not exist")
        raise OptimisticConcurrencyError(portfolio.id, expected_version, actual_version)


class SqlAlchemyPositionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, position_id: UUID) -> Position | None:
        model = await self._session.get(PositionModel, position_id)
        return position_from_model(model) if model is not None else None

    async def list_for_portfolio(
        self,
        portfolio_id: UUID,
        *,
        as_of: datetime | None = None,
    ) -> Sequence[Position]:
        candidate = aliased(PositionModel)
        latest_as_of = select(func.max(candidate.as_of)).where(
            candidate.portfolio_id == PositionModel.portfolio_id,
            candidate.instrument_id == PositionModel.instrument_id,
        )
        if as_of is not None:
            latest_as_of = latest_as_of.where(candidate.as_of <= as_of)
        statement = select(PositionModel).where(
            PositionModel.portfolio_id == portfolio_id,
            PositionModel.as_of == latest_as_of.correlate(PositionModel).scalar_subquery(),
        )
        statement = statement.order_by(PositionModel.instrument_id, PositionModel.id)
        models = (await self._session.scalars(statement)).all()
        return tuple(position_from_model(model) for model in models)

    async def upsert(self, position: Position) -> None:
        _require_numeric_38_12(position.quantity, "position.quantity")
        _require_numeric_38_12(position.average_cost, "position.average_cost")
        values = {
            "id": position.id,
            "portfolio_id": position.portfolio_id,
            "instrument_id": position.instrument_id,
            "quantity": position.quantity,
            "average_cost": position.average_cost,
            "currency": position.currency.code,
            "as_of": position.as_of,
            "tags": dict(position.tags),
        }
        statement = pg_insert(PositionModel).values(**values)
        statement = statement.on_conflict_do_update(
            constraint="uq_positions_portfolio_instrument_as_of",
            set_={
                "quantity": statement.excluded.quantity,
                "average_cost": statement.excluded.average_cost,
                "currency": statement.excluded.currency,
                "tags": statement.excluded.tags,
            },
        )
        await self._session.execute(statement)

    async def remove(self, position_id: UUID) -> None:
        await self._session.execute(delete(PositionModel).where(PositionModel.id == position_id))


class SqlAlchemyAuditEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: AuditEvent) -> None:
        self._session.add(audit_model_from_domain(event))


class SqlAlchemyOutboxEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: OutboxEvent) -> None:
        self._session.add(outbox_model_from_domain(event))

    async def claim_available(
        self,
        *,
        at: datetime,
        limit: int,
        worker_id: str,
    ) -> Sequence[OutboxEvent]:
        """Lock available rows until the surrounding unit of work completes.

        ``worker_id`` is accepted for the domain port and future lease telemetry.
        The initial implementation deliberately uses transaction-scoped
        ``FOR UPDATE SKIP LOCKED`` rather than pretending to provide a lease.
        """

        del worker_id
        if limit < 1 or limit > 1_000:
            raise DomainValidationError("outbox claim limit must be between 1 and 1000")
        statement = (
            select(OutboxEventModel)
            .where(
                OutboxEventModel.status.in_(("pending", "retry_scheduled")),
                OutboxEventModel.available_at <= at,
            )
            .order_by(OutboxEventModel.available_at, OutboxEventModel.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        models = (await self._session.scalars(statement)).all()
        return tuple(outbox_from_model(model) for model in models)

    async def save(self, event: OutboxEvent) -> None:
        statement = (
            update(OutboxEventModel)
            .where(OutboxEventModel.id == event.id)
            .values(
                status=event.status.value,
                attempts=event.attempts,
                available_at=event.available_at,
                published_at=event.published_at,
                error_summary=event.error_summary,
                event_envelope=_json_object(event.event_envelope, "event envelope"),
                updated_at=func.now(),
            )
            .execution_options(synchronize_session="fetch")
        )
        result = cast(CursorResult[Any], await self._session.execute(statement))
        if result.rowcount != 1:
            raise LookupError(f"outbox event {event.id} does not exist")
