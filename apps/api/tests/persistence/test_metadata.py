from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from alembic import command
from alembic.config import Config
from pgvector.sqlalchemy import Vector
from quantops_api.infrastructure.persistence.base import Base, UTCDateTime
from quantops_api.infrastructure.persistence.models import EMBEDDING_DIMENSIONS
from quantops_domain import DomainValidationError
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Numeric,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.engine import Dialect
from sqlalchemy.schema import CreateIndex, CreateTable

EXPECTED_TABLES = {
    "audit_events",
    "data_quality_issues",
    "document_chunks",
    "documents",
    "generated_risk_briefs",
    "instruments",
    "market_events",
    "model_evaluations",
    "model_versions",
    "outbox_events",
    "pipeline_runs",
    "portfolios",
    "positions",
    "price_bars",
    "risk_contributions",
    "risk_snapshots",
    "scenario_definitions",
    "scenario_runs",
}


def postgresql_dialect() -> Dialect:
    return cast(Dialect, postgresql.dialect())  # type: ignore[no-untyped-call]


def test_metadata_contains_the_authoritative_domain_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_all_database_constraints_are_named() -> None:
    named_constraint_types = (
        CheckConstraint,
        ForeignKeyConstraint,
        PrimaryKeyConstraint,
        UniqueConstraint,
    )
    for table in Base.metadata.sorted_tables:
        for constraint in table.constraints:
            if isinstance(constraint, named_constraint_types):
                assert constraint.name, f"unnamed constraint on {table.name}: {constraint}"


def test_postgresql_native_types_cover_identity_json_and_vector() -> None:
    instruments = Base.metadata.tables["instruments"]
    positions = Base.metadata.tables["positions"]
    chunks = Base.metadata.tables["document_chunks"]

    assert isinstance(instruments.c.id.type, PGUUID)
    assert isinstance(instruments.c.metadata.type, JSONB)
    quantity_type = cast(Numeric[Decimal], positions.c.quantity.type)
    assert quantity_type.precision == 38
    assert quantity_type.scale == 12
    assert isinstance(chunks.c.embedding.type, Vector)
    assert chunks.c.embedding.type.dim == EMBEDDING_DIMENSIONS


def test_scenario_versions_match_risk_engine_semantic_versions() -> None:
    definitions = Base.metadata.tables["scenario_definitions"]
    runs = Base.metadata.tables["scenario_runs"]

    assert cast(String, definitions.c.version.type).length == 40
    assert cast(String, runs.c.scenario_version.type).length == 40
    constraint_sql = " ".join(
        str(constraint.sqltext)
        for constraint in definitions.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "[0-9]+" in constraint_sql


def test_every_table_and_index_compiles_for_postgresql() -> None:
    dialect = postgresql_dialect()
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table.name}" in ddl
        for index in table.indexes:
            index_ddl = str(CreateIndex(index).compile(dialect=dialect))
            assert index.name is not None
            assert str(index.name) in index_ddl


def test_position_tag_constraint_uses_only_real_postgresql_functions() -> None:
    positions = Base.metadata.tables["positions"]
    ddl = str(CreateTable(positions).compile(dialect=postgresql_dialect()))

    assert "jsonb_typeof(tags) = 'object'" in ddl
    assert "jsonb_object_length" not in ddl


def test_utc_type_rejects_naive_values_and_normalizes_offsets() -> None:
    column_type = UTCDateTime()
    offset = timezone(timedelta(hours=2))
    instant = datetime(2026, 7, 19, 14, 0, tzinfo=offset)

    dialect = postgresql_dialect()
    assert column_type.process_bind_param(instant, dialect) == datetime(
        2026,
        7,
        19,
        12,
        0,
        tzinfo=UTC,
    )
    with pytest.raises(DomainValidationError, match="timezone-aware"):
        column_type.process_bind_param(instant.replace(tzinfo=None), dialect)


def test_domain_package_has_no_persistence_or_framework_dependency() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    domain_root = repository_root / "packages" / "domain" / "quantops_domain"
    forbidden = ("sqlalchemy", "fastapi", "asyncpg", "alembic", "pgvector")

    for source_file in domain_root.glob("*.py"):
        source = source_file.read_text(encoding="utf-8").casefold()
        for dependency in forbidden:
            assert dependency not in source, f"{source_file.name} imports {dependency}"


def test_initial_revision_renders_complete_offline_sql(capsys: pytest.CaptureFixture[str]) -> None:
    api_root = Path(__file__).resolve().parents[2]
    config = Config(str(api_root / "alembic.ini"))

    command.upgrade(config, "head", sql=True)

    sql = capsys.readouterr().out
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "CREATE TABLE price_bars" in sql
    assert "CREATE TABLE outbox_events" in sql
    assert "CREATE INDEX ix_document_chunks_embedding_hnsw" in sql
    assert "INSERT INTO alembic_version" in sql
