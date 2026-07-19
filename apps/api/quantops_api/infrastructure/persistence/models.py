"""PostgreSQL mappings for the QuantOps operational data model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text as sql_text

from quantops_api.infrastructure.persistence.base import Base, UTCDateTime

MONEY_PRECISION = 38
MONEY_SCALE = 12
RATIO_PRECISION = 24
RATIO_SCALE = 12
EMBEDDING_DIMENSIONS = 384


def uuid_primary_key() -> Mapped[UUID]:
    """Typed UUID primary-key column shared by entity tables."""

    return mapped_column(PGUUID(as_uuid=True), primary_key=True)


def created_timestamp() -> Mapped[datetime]:
    return mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class InstrumentModel(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint("source", "symbol", name="uq_instruments_source_symbol"),
        CheckConstraint("symbol = upper(symbol)", name="ck_instruments_symbol_upper"),
        CheckConstraint(
            "symbol ~ '^[A-Z0-9][A-Z0-9._/-]{0,31}$'",
            name="ck_instruments_symbol_format",
        ),
        CheckConstraint(
            "quote_currency ~ '^[A-Z]{3}$'",
            name="ck_instruments_quote_currency_format",
        ),
        CheckConstraint(
            "asset_class IN ('equity_index', 'equity', 'commodity', 'fx', "
            "'bond', 'cash', 'synthetic')",
            name="ck_instruments_asset_class",
        ),
        CheckConstraint("source = lower(source)", name="ck_instruments_source_lower"),
        CheckConstraint("price_scale BETWEEN 0 AND 18", name="ck_instruments_price_scale"),
        Index("ix_instruments_symbol", "symbol"),
        Index("ix_instruments_demo_asset_class", "is_demo", "asset_class"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    price_scale: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    calendar: Mapped[str] = mapped_column(String(64), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=sql_text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = created_timestamp()
    updated_at: Mapped[datetime] = created_timestamp()


class PipelineRunModel(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'cancelled')",
            name="ck_pipeline_runs_status",
        ),
        CheckConstraint(
            "records_read >= 0 AND accepted >= 0 AND updated >= 0 "
            "AND duplicated >= 0 AND rejected >= 0 AND late >= 0",
            name="ck_pipeline_runs_nonnegative_counts",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_pipeline_runs_time_order",
        ),
        Index("ix_pipeline_runs_name_started", "pipeline_name", text("started_at DESC")),
        Index("ix_pipeline_runs_status_started", "status", text("started_at DESC")),
    )

    id: Mapped[UUID] = uuid_primary_key()
    pipeline_name: Mapped[str] = mapped_column(String(120), nullable=False)
    code_version: Mapped[str] = mapped_column(String(80), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    records_read: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    accepted: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    updated: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    duplicated: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    rejected: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    late: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    watermark_before: Mapped[datetime | None] = mapped_column(UTCDateTime())
    watermark_after: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error_summary: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class PortfolioModel(Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        CheckConstraint(
            "base_currency ~ '^[A-Z]{3}$'",
            name="ck_portfolios_base_currency_format",
        ),
        CheckConstraint("version >= 1", name="ck_portfolios_version"),
        Index("ix_portfolios_demo_name", "is_demo", "name"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = created_timestamp()
    updated_at: Mapped[datetime] = created_timestamp()

    __mapper_args__: dict[str, Any] = {  # noqa: RUF012 - SQLAlchemy requires a dict
        "version_id_col": version,
        "version_id_generator": False,
    }


class DocumentModel(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "document_type",
            "source_identifier",
            name="uq_documents_type_source_identifier",
        ),
        CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_documents_content_hash_format",
        ),
        Index("ix_documents_published", text("published_at DESC")),
        Index("ix_documents_synthetic_type", "is_synthetic", "document_type"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    issuer: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_identifier: Mapped[str] = mapped_column(String(300), nullable=False)
    published_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    license_or_usage_note: Mapped[str] = mapped_column(Text, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class ModelVersionModel(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("model_name", "semantic_version", name="uq_model_versions_name_version"),
        UniqueConstraint("mlflow_run_id", name="uq_model_versions_mlflow_run_id"),
        CheckConstraint(
            "approval_status IN ('candidate', 'approved', 'rejected', 'archived')",
            name="ck_model_versions_approval_status",
        ),
        CheckConstraint(
            "activated_at IS NULL OR activated_at >= created_at",
            name="ck_model_versions_activation_time",
        ),
        CheckConstraint(
            "retired_at IS NULL OR activated_at IS NULL OR retired_at >= activated_at",
            name="ck_model_versions_retirement_time",
        ),
        Index("ix_model_versions_name_status", "model_name", "approval_status"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    semantic_version: Mapped[str] = mapped_column(String(40), nullable=False)
    training_data_version: Mapped[str] = mapped_column(String(120), nullable=False)
    training_data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    code_revision: Mapped[str] = mapped_column(String(80), nullable=False)
    mlflow_run_id: Mapped[str] = mapped_column(String(80), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False)
    approver: Mapped[str] = mapped_column(String(160), nullable=False)
    evaluation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    drift_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = created_timestamp()
    activated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    retired_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ScenarioDefinitionModel(Base):
    __tablename__ = "scenario_definitions"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_scenario_definitions_name_version"),
        CheckConstraint(
            "version ~ '^[0-9]+\\.[0-9]+\\.[0-9]+$'",
            name="ck_scenario_definitions_version",
        ),
        Index("ix_scenario_definitions_system_name", "is_system", "name"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    shocks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = created_timestamp()


class PositionModel(Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id",
            "instrument_id",
            "as_of",
            name="uq_positions_portfolio_instrument_as_of",
        ),
        CheckConstraint("average_cost >= 0", name="ck_positions_average_cost_nonnegative"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_positions_currency_format"),
        CheckConstraint(
            "jsonb_typeof(tags) = 'object'",
            name="ck_positions_tags_object",
        ),
        Index("ix_positions_portfolio_as_of", "portfolio_id", text("as_of DESC")),
        Index("ix_positions_instrument_as_of", "instrument_id", text("as_of DESC")),
    )

    id: Mapped[UUID] = uuid_primary_key()
    portfolio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    instrument_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE),
        nullable=False,
    )
    average_cost: Mapped[Decimal] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    as_of: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    tags: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'{}'::jsonb"),
    )


class PriceBarModel(Base):
    """Accepted market bar; see the migration for the safe partition policy."""

    __tablename__ = "price_bars"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "interval",
            "observed_at",
            "source",
            name="uq_price_bars_instrument_interval_observed_source",
        ),
        UniqueConstraint("source", "source_event_id", name="uq_price_bars_source_event"),
        CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0", name="ck_price_bars_positive_ohlc"
        ),
        CheckConstraint(
            "high >= GREATEST(open, close, low) AND low <= LEAST(open, close, high)",
            name="ck_price_bars_ohlc_relationship",
        ),
        CheckConstraint("volume >= 0", name="ck_price_bars_volume_nonnegative"),
        CheckConstraint(
            "interval ~ '^[1-9][0-9]*(m|h|d|w)$'",
            name="ck_price_bars_interval_format",
        ),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_price_bars_currency_format"),
        CheckConstraint(
            "quality_status IN ('accepted', 'warning')",
            name="ck_price_bars_quality_status",
        ),
        Index("ix_price_bars_instrument_observed", "instrument_id", text("observed_at DESC")),
        Index(
            "ix_price_bars_latest_lookup",
            "instrument_id",
            "interval",
            text("observed_at DESC"),
        ),
        {"comment": "Initially unpartitioned; partition policy is documented in migration 0001."},
    )

    id: Mapped[UUID] = uuid_primary_key()
    instrument_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(20), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    pipeline_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )


class MarketEventModel(Base):
    __tablename__ = "market_events"
    __table_args__ = (
        UniqueConstraint(
            "event_type", "source_event_id", name="uq_market_events_type_source_event"
        ),
        CheckConstraint("schema_version >= 1", name="ck_market_events_schema_version"),
        CheckConstraint(
            "received_at >= occurred_at",
            name="ck_market_events_receive_time",
        ),
        CheckConstraint(
            "payload_hash ~ '^[0-9a-f]{64}$'",
            name="ck_market_events_payload_hash_format",
        ),
        CheckConstraint(
            "processing_status IN ('received', 'processed', 'duplicate', 'late', 'rejected')",
            name="ck_market_events_processing_status",
        ),
        Index("ix_market_events_status_received", "processing_status", text("received_at DESC")),
        Index("ix_market_events_correlation", "correlation_id"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(20), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))


class RiskSnapshotModel(Base):
    __tablename__ = "risk_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id",
            "portfolio_version",
            "as_of",
            "methodology_version",
            name="uq_risk_snapshots_portfolio_version_asof_method",
        ),
        CheckConstraint("portfolio_version >= 1", name="ck_risk_snapshots_portfolio_version"),
        CheckConstraint(
            "window_start <= window_end AND window_end <= as_of",
            name="ck_risk_snapshots_window_order",
        ),
        CheckConstraint(
            "confidence_level > 0 AND confidence_level < 1",
            name="ck_risk_snapshots_confidence",
        ),
        CheckConstraint(
            "data_completeness >= 0 AND data_completeness <= 1",
            name="ck_risk_snapshots_completeness",
        ),
        CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="ck_risk_snapshots_currency_format"),
        Index("ix_risk_snapshots_portfolio_as_of", "portfolio_id", text("as_of DESC")),
        Index("ix_risk_snapshots_quality_created", "quality_status", text("created_at DESC")),
    )

    id: Mapped[UUID] = uuid_primary_key()
    portfolio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    portfolio_version: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(80), nullable=False)
    window_start: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    window_end: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(8, 7), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    portfolio_value: Mapped[Decimal] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False
    )
    daily_pnl: Mapped[Decimal] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False
    )
    volatility_annualized: Mapped[Decimal | None] = mapped_column(
        Numeric(RATIO_PRECISION, RATIO_SCALE)
    )
    var_historical: Mapped[Decimal | None] = mapped_column(Numeric(MONEY_PRECISION, MONEY_SCALE))
    var_parametric: Mapped[Decimal | None] = mapped_column(Numeric(MONEY_PRECISION, MONEY_SCALE))
    expected_shortfall: Mapped[Decimal | None] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE)
    )
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(RATIO_PRECISION, RATIO_SCALE))
    data_completeness: Mapped[Decimal] = mapped_column(Numeric(8, 7), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_timestamp()


class RiskContributionModel(Base):
    __tablename__ = "risk_contributions"
    __table_args__ = (Index("ix_risk_contributions_instrument", "instrument_id"),)

    risk_snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("risk_snapshots.id", ondelete="CASCADE"),
        primary_key=True,
    )
    instrument_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    market_value: Mapped[Decimal] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False
    )
    weight: Mapped[Decimal] = mapped_column(Numeric(RATIO_PRECISION, RATIO_SCALE), nullable=False)
    volatility_contribution: Mapped[Decimal] = mapped_column(
        Numeric(RATIO_PRECISION, RATIO_SCALE),
        nullable=False,
    )
    var_contribution: Mapped[Decimal | None] = mapped_column(Numeric(MONEY_PRECISION, MONEY_SCALE))
    evidence_id: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)


class ScenarioRunModel(Base):
    __tablename__ = "scenario_runs"
    __table_args__ = (
        CheckConstraint("portfolio_version >= 1", name="ck_scenario_runs_portfolio_version"),
        CheckConstraint(
            "scenario_version ~ '^[0-9]+\\.[0-9]+\\.[0-9]+$'",
            name="ck_scenario_runs_scenario_version",
        ),
        CheckConstraint(
            "pnl_impact = stressed_value - base_value", name="ck_scenario_runs_pnl_reconciles"
        ),
        Index("ix_scenario_runs_portfolio_run_at", "portfolio_id", text("run_at DESC")),
    )

    id: Mapped[UUID] = uuid_primary_key()
    portfolio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    portfolio_version: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario_definition_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("scenario_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scenario_version: Mapped[str] = mapped_column(String(40), nullable=False)
    run_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    base_value: Mapped[Decimal] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False
    )
    stressed_value: Mapped[Decimal] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False
    )
    pnl_impact: Mapped[Decimal] = mapped_column(
        Numeric(MONEY_PRECISION, MONEY_SCALE), nullable=False
    )
    component_impacts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class DataQualityIssueModel(Base):
    __tablename__ = "data_quality_issues"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warning', 'error', 'critical')",
            name="ck_data_quality_issues_severity",
        ),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= created_at",
            name="ck_data_quality_issues_resolution_time",
        ),
        Index("ix_data_quality_issues_run_severity", "pipeline_run_id", "severity"),
        Index(
            "ix_data_quality_issues_unresolved",
            "created_at",
            postgresql_where=text("resolved_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = uuid_primary_key()
    pipeline_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_reference: Mapped[str] = mapped_column(String(300), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    observed_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expected_constraint: Mapped[str] = mapped_column(Text, nullable=False)
    quarantined_payload_reference: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_timestamp()
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_index"),
        UniqueConstraint("evidence_id", name="uq_document_chunks_evidence_id"),
        CheckConstraint("chunk_index >= 0", name="ck_document_chunks_index_nonnegative"),
        CheckConstraint("token_count > 0", name="ck_document_chunks_token_count_positive"),
        Index("ix_document_chunks_document", "document_id", "chunk_index"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text("embedding IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    evidence_id: Mapped[str] = mapped_column(String(160), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=sql_text("'{}'::jsonb"),
    )


class ModelEvaluationModel(Base):
    __tablename__ = "model_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "model_version_id",
            "evaluation_type",
            "evaluation_data_version",
            name="uq_model_evaluations_model_type_data",
        ),
        Index(
            "ix_model_evaluations_model_evaluated", "model_version_id", text("evaluated_at DESC")
        ),
    )

    id: Mapped[UUID] = uuid_primary_key()
    model_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    evaluation_data_version: Mapped[str] = mapped_column(String(120), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class GeneratedRiskBriefModel(Base):
    __tablename__ = "generated_risk_briefs"
    __table_args__ = (
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0", name="ck_generated_briefs_latency"
        ),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_generated_briefs_input_tokens",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_generated_briefs_output_tokens",
        ),
        CheckConstraint(
            "jsonb_typeof(cited_evidence_ids) = 'array'",
            name="ck_generated_briefs_citations_array",
        ),
        Index("ix_generated_briefs_portfolio_created", "portfolio_id", text("created_at DESC")),
        Index("ix_generated_briefs_validation", "validation_status", text("created_at DESC")),
    )

    id: Mapped[UUID] = uuid_primary_key()
    portfolio_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    risk_snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("risk_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scenario_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("scenario_runs.id", ondelete="SET NULL"),
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    structured_content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    cited_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    tool_trace_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    refusal_category: Mapped[str | None] = mapped_column(String(80))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_timestamp()


class AuditEventModel(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index(
            "ix_audit_events_aggregate", "aggregate_type", "aggregate_id", text("occurred_at DESC")
        ),
        Index("ix_audit_events_correlation", "correlation_id"),
        Index("ix_audit_events_action_occurred", "action", text("occurred_at DESC")),
    )

    id: Mapped[UUID] = uuid_primary_key()
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_outbox_events_idempotency_key"),
        CheckConstraint("schema_version >= 1", name="ck_outbox_events_schema_version"),
        CheckConstraint("attempts >= 0", name="ck_outbox_events_attempts"),
        CheckConstraint(
            "available_at >= occurred_at",
            name="ck_outbox_events_available_time",
        ),
        CheckConstraint(
            "event_type ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'",
            name="ck_outbox_events_event_type_format",
        ),
        CheckConstraint(
            "jsonb_typeof(event_envelope) = 'object'",
            name="ck_outbox_events_envelope_object",
        ),
        CheckConstraint(
            "status IN ('pending', 'retry_scheduled', 'published', 'dead_letter')",
            name="ck_outbox_events_status",
        ),
        CheckConstraint(
            "(status = 'pending' AND attempts = 0 AND published_at IS NULL "
            "AND error_summary IS NULL) OR "
            "(status = 'retry_scheduled' AND attempts >= 1 AND published_at IS NULL "
            "AND error_summary IS NOT NULL) OR "
            "(status = 'published' AND attempts >= 1 AND published_at IS NOT NULL "
            "AND error_summary IS NULL) OR "
            "(status = 'dead_letter' AND attempts >= 1 AND published_at IS NULL "
            "AND error_summary IS NOT NULL)",
            name="ck_outbox_events_publication_state",
        ),
        Index(
            "ix_outbox_events_available_pending",
            "available_at",
            postgresql_where=text("status IN ('pending', 'retry_scheduled')"),
        ),
        Index("ix_outbox_events_aggregate", "aggregate_type", "aggregate_id"),
        Index("ix_outbox_events_correlation", "correlation_id"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    producer: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error_summary: Mapped[str | None] = mapped_column(String(512))
    event_envelope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_timestamp()
    updated_at: Mapped[datetime] = created_timestamp()


ALL_MODELS = (
    InstrumentModel,
    PipelineRunModel,
    PortfolioModel,
    DocumentModel,
    ModelVersionModel,
    ScenarioDefinitionModel,
    PositionModel,
    PriceBarModel,
    MarketEventModel,
    RiskSnapshotModel,
    RiskContributionModel,
    ScenarioRunModel,
    DataQualityIssueModel,
    DocumentChunkModel,
    ModelEvaluationModel,
    GeneratedRiskBriefModel,
    AuditEventModel,
    OutboxEventModel,
)
