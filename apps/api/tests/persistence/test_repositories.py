from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from quantops_api.infrastructure.persistence.models import (
    AuditEventModel,
    InstrumentModel,
    OutboxEventModel,
    PortfolioModel,
    PositionModel,
)
from quantops_api.infrastructure.persistence.repositories import (
    SqlAlchemyPortfolioRepository,
    SqlAlchemyPositionRepository,
    audit_from_model,
    audit_model_from_domain,
    instrument_from_model,
    outbox_from_model,
    outbox_model_from_domain,
    portfolio_from_model,
    position_from_model,
)
from quantops_api.infrastructure.persistence.unit_of_work import append_audit_and_outbox
from quantops_domain import (
    AssetClass,
    AuditAction,
    AuditEvent,
    Currency,
    DomainValidationError,
    Instrument,
    InstrumentSymbol,
    OptimisticConcurrencyError,
    OutboxEvent,
    Portfolio,
    Position,
)
from sqlalchemy.ext.asyncio import AsyncSession

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
INSTRUMENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
PORTFOLIO_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
POSITION_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
AUDIT_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
OUTBOX_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
CORRELATION_ID = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")


def test_core_models_round_trip_to_strict_domain_entities() -> None:
    instrument = instrument_from_model(
        InstrumentModel(
            id=INSTRUMENT_ID,
            source="synthetic",
            symbol="QSPX",
            name="QuantOps Equity Index",
            asset_class="equity_index",
            quote_currency="USD",
            price_scale=4,
            timezone="UTC",
            calendar="WEEKDAY",
            is_demo=True,
            metadata_json={"synthetic": True},
            created_at=NOW,
            updated_at=NOW,
        )
    )
    portfolio = portfolio_from_model(
        PortfolioModel(
            id=PORTFOLIO_ID,
            name="Demo Portfolio",
            base_currency="USD",
            description="Synthetic",
            is_demo=True,
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    position = position_from_model(
        PositionModel(
            id=POSITION_ID,
            portfolio_id=PORTFOLIO_ID,
            instrument_id=INSTRUMENT_ID,
            quantity=Decimal("2.5"),
            average_cost=Decimal("100.25"),
            currency="USD",
            as_of=NOW,
            tags={"book": "macro"},
        )
    )

    assert instrument == Instrument(
        id=INSTRUMENT_ID,
        source="synthetic",
        symbol=InstrumentSymbol("QSPX"),
        name="QuantOps Equity Index",
        asset_class=AssetClass.EQUITY_INDEX,
        quote_currency=Currency("USD"),
        price_scale=4,
        timezone="UTC",
        calendar="WEEKDAY",
        is_demo=True,
        metadata={"synthetic": True},
        created_at=NOW,
        updated_at=NOW,
    )
    assert portfolio.version == 1
    assert position.quantity == Decimal("2.5")
    assert position.tags["book"] == "macro"


def _audit_and_outbox() -> tuple[AuditEvent, OutboxEvent]:
    audit = AuditEvent.create(
        audit_id=AUDIT_ID,
        action=AuditAction.PORTFOLIO_UPDATED,
        aggregate_type="portfolio",
        aggregate_id=PORTFOLIO_ID,
        actor_id="demo-user",
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
        details={"version": 2},
    )
    outbox = OutboxEvent.pending(
        event_id=OUTBOX_ID,
        aggregate_type="portfolio",
        aggregate_id=PORTFOLIO_ID,
        event_type="portfolio.changed",
        schema_version=1,
        producer="quantops-api",
        idempotency_key="portfolio:bbbb:v2",
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
        payload={"portfolio_version": 2},
    )
    return audit, outbox


def test_audit_and_outbox_mapping_round_trips_safe_payloads() -> None:
    audit, outbox = _audit_and_outbox()

    stored_audit = audit_model_from_domain(audit)
    stored_outbox = outbox_model_from_domain(outbox)

    assert audit_from_model(stored_audit) == audit
    assert outbox_from_model(stored_outbox) == outbox
    assert stored_outbox.event_envelope["payload"] == {"portfolio_version": 2}


def test_same_transaction_helper_stages_audit_and_outbox_together() -> None:
    audit, outbox = _audit_and_outbox()
    session = MagicMock(spec=AsyncSession)

    append_audit_and_outbox(session, audit_event=audit, outbox_event=outbox)

    staged = session.add_all.call_args.args[0]
    assert len(staged) == 2
    assert isinstance(staged[0], AuditEventModel)
    assert isinstance(staged[1], OutboxEventModel)


def test_same_transaction_helper_rejects_mismatched_correlation() -> None:
    audit, _outbox = _audit_and_outbox()
    mismatched = OutboxEvent.pending(
        event_id=OUTBOX_ID,
        aggregate_type="portfolio",
        aggregate_id=PORTFOLIO_ID,
        event_type="portfolio.changed",
        schema_version=1,
        producer="quantops-api",
        idempotency_key="portfolio:bbbb:v2",
        occurred_at=NOW,
        payload={"portfolio_version": 2},
    )

    with pytest.raises(DomainValidationError, match="correlation IDs"):
        append_audit_and_outbox(
            MagicMock(spec=AsyncSession),
            audit_event=audit,
            outbox_event=mismatched,
        )


@pytest.mark.asyncio
async def test_portfolio_repository_detects_stale_guarded_update() -> None:
    current = Portfolio.create(
        portfolio_id=PORTFOLIO_ID,
        name="Demo Portfolio",
        base_currency="USD",
        description=None,
        is_demo=True,
        now=NOW,
    )
    revised = current.revise(
        expected_version=1,
        updated_at=NOW + timedelta(seconds=1),
        name="Revised",
    )
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=SimpleNamespace(rowcount=0))
    session.scalar = AsyncMock(return_value=3)

    with pytest.raises(OptimisticConcurrencyError) as raised:
        await SqlAlchemyPortfolioRepository(session).save(revised, expected_version=1)

    assert raised.value.expected == 1
    assert raised.value.actual == 3


@pytest.mark.asyncio
async def test_portfolio_update_synchronizes_the_identity_map() -> None:
    current = Portfolio.create(
        portfolio_id=PORTFOLIO_ID,
        name="Demo Portfolio",
        base_currency="USD",
        description=None,
        is_demo=True,
        now=NOW,
    )
    revised = current.revise(
        expected_version=1,
        updated_at=NOW + timedelta(seconds=1),
        name="Revised",
    )
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=SimpleNamespace(rowcount=1))

    await SqlAlchemyPortfolioRepository(session).save(revised, expected_version=1)

    statement = session.execute.await_args.args[0]
    assert statement.get_execution_options()["synchronize_session"] == "fetch"


@pytest.mark.asyncio
async def test_portfolio_repository_rejects_an_unguarded_version_jump() -> None:
    invalid = Portfolio(
        id=PORTFOLIO_ID,
        name="Version Three",
        base_currency=Currency("USD"),
        description=None,
        is_demo=True,
        version=3,
        created_at=NOW,
        updated_at=NOW + timedelta(seconds=1),
    )

    with pytest.raises(DomainValidationError, match=r"expected_version \+ 1"):
        await SqlAlchemyPortfolioRepository(MagicMock(spec=AsyncSession)).save(
            invalid,
            expected_version=1,
        )


@pytest.mark.asyncio
async def test_position_listing_selects_latest_row_per_instrument() -> None:
    scalar_result = MagicMock()
    scalar_result.all.return_value = []
    session = MagicMock(spec=AsyncSession)
    session.scalars = AsyncMock(return_value=scalar_result)
    repository = SqlAlchemyPositionRepository(session)

    await repository.list_for_portfolio(PORTFOLIO_ID)
    latest_sql = str(session.scalars.await_args.args[0])
    assert "max(positions_1.as_of)" in latest_sql
    assert "positions_1.instrument_id = positions.instrument_id" in latest_sql

    await repository.list_for_portfolio(PORTFOLIO_ID, as_of=NOW)
    bounded_sql = str(session.scalars.await_args.args[0])
    assert "positions_1.as_of <=" in bounded_sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("quantity", "message"),
    [
        (Decimal("0.0000000000001"), "scale"),
        (Decimal("100000000000000000000000000"), "precision"),
    ],
)
async def test_position_upsert_rejects_values_outside_numeric_capacity(
    quantity: Decimal,
    message: str,
) -> None:
    position = Position(
        id=POSITION_ID,
        portfolio_id=PORTFOLIO_ID,
        instrument_id=INSTRUMENT_ID,
        quantity=quantity,
        average_cost=Decimal("1"),
        currency=Currency("USD"),
        as_of=NOW,
    )
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()

    with pytest.raises(DomainValidationError, match=message):
        await SqlAlchemyPositionRepository(session).upsert(position)
    session.execute.assert_not_awaited()
