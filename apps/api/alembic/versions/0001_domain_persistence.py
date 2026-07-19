"""Create the QuantOps domain persistence schema.

Revision ID: 0001_domain_persistence
Revises: None
Create Date: 2026-07-19

Price-bar partition policy
--------------------------
The initial demo table is deliberately unpartitioned. Its source identity unique
constraint and UUID foreign-key targets remain simple and fully testable. Before
production volume justifies partitioning, measure table/index size and time-range
latency. Migrate online to monthly RANGE partitions on ``observed_at`` only after:

1. changing uniqueness/primary keys to include the partition key as PostgreSQL
   requires;
2. creating a default partition so late data cannot fail ingestion;
3. backfilling bounded month ranges and validating row counts/checksums;
4. swapping tables in a short lock window and retaining rollback capacity; and
5. automating future partition creation and retention without dropping lineage.

This policy avoids a decorative partition design that would weaken idempotency.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_domain_persistence"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
MONEY = sa.Numeric(38, 12)
RATIO = sa.Numeric(24, 12)
UTC = sa.DateTime(timezone=True)


def _id() -> sa.Column[object]:
    return sa.Column("id", UUID, nullable=False)


def _created_at() -> sa.Column[object]:
    return sa.Column("created_at", UTC, server_default=sa.text("now()"), nullable=False)


def _json(name: str, *, default: bool = False) -> sa.Column[object]:
    return sa.Column(
        name,
        JSONB,
        server_default=sa.text("'{}'::jsonb") if default else None,
        nullable=False,
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "instruments",
        _id(),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("quote_currency", sa.String(length=3), nullable=False),
        sa.Column("price_scale", sa.SmallInteger(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("calendar", sa.String(length=64), nullable=False),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _json("metadata", default=True),
        _created_at(),
        sa.Column("updated_at", UTC, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("symbol = upper(symbol)", name="ck_instruments_symbol_upper"),
        sa.CheckConstraint(
            "symbol ~ '^[A-Z0-9][A-Z0-9._/-]{0,31}$'",
            name="ck_instruments_symbol_format",
        ),
        sa.CheckConstraint(
            "quote_currency ~ '^[A-Z]{3}$'",
            name="ck_instruments_quote_currency_format",
        ),
        sa.CheckConstraint(
            "asset_class IN ('equity_index', 'equity', 'commodity', 'fx', "
            "'bond', 'cash', 'synthetic')",
            name="ck_instruments_asset_class",
        ),
        sa.CheckConstraint("source = lower(source)", name="ck_instruments_source_lower"),
        sa.CheckConstraint(
            "price_scale BETWEEN 0 AND 18",
            name="ck_instruments_price_scale",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_instruments"),
        sa.UniqueConstraint("source", "symbol", name="uq_instruments_source_symbol"),
    )
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"])
    op.create_index(
        "ix_instruments_demo_asset_class",
        "instruments",
        ["is_demo", "asset_class"],
    )

    op.create_table(
        "pipeline_runs",
        _id(),
        sa.Column("pipeline_name", sa.String(length=120), nullable=False),
        sa.Column("code_version", sa.String(length=80), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("started_at", UTC, nullable=False),
        sa.Column("finished_at", UTC, nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("records_read", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("accepted", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("duplicated", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("rejected", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("late", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("watermark_before", UTC, nullable=True),
        sa.Column("watermark_after", UTC, nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        _json("metadata", default=True),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'cancelled')",
            name="ck_pipeline_runs_status",
        ),
        sa.CheckConstraint(
            "records_read >= 0 AND accepted >= 0 AND updated >= 0 "
            "AND duplicated >= 0 AND rejected >= 0 AND late >= 0",
            name="ck_pipeline_runs_nonnegative_counts",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_pipeline_runs_time_order",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pipeline_runs"),
    )
    op.create_index(
        "ix_pipeline_runs_name_started",
        "pipeline_runs",
        ["pipeline_name", sa.text("started_at DESC")],
    )
    op.create_index(
        "ix_pipeline_runs_status_started",
        "pipeline_runs",
        ["status", sa.text("started_at DESC")],
    )

    op.create_table(
        "portfolios",
        _id(),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        _created_at(),
        sa.Column("updated_at", UTC, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "base_currency ~ '^[A-Z]{3}$'",
            name="ck_portfolios_base_currency_format",
        ),
        sa.CheckConstraint("version >= 1", name="ck_portfolios_version"),
        sa.PrimaryKeyConstraint("id", name="pk_portfolios"),
    )
    op.create_index("ix_portfolios_demo_name", "portfolios", ["is_demo", "name"])

    op.create_table(
        "documents",
        _id(),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("document_type", sa.String(length=80), nullable=False),
        sa.Column("issuer", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_identifier", sa.String(length=300), nullable=False),
        sa.Column("published_at", UTC, nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("license_or_usage_note", sa.Text(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("ingested_at", UTC, nullable=False),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_documents_content_hash_format",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint(
            "document_type",
            "source_identifier",
            name="uq_documents_type_source_identifier",
        ),
    )
    op.create_index("ix_documents_published", "documents", [sa.text("published_at DESC")])
    op.create_index(
        "ix_documents_synthetic_type",
        "documents",
        ["is_synthetic", "document_type"],
    )

    op.create_table(
        "model_versions",
        _id(),
        sa.Column("model_name", sa.String(length=160), nullable=False),
        sa.Column("semantic_version", sa.String(length=40), nullable=False),
        sa.Column("training_data_version", sa.String(length=120), nullable=False),
        sa.Column("training_data_hash", sa.String(length=64), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=40), nullable=False),
        sa.Column("code_revision", sa.String(length=80), nullable=False),
        sa.Column("mlflow_run_id", sa.String(length=80), nullable=False),
        _json("metrics"),
        _json("thresholds"),
        sa.Column("approval_status", sa.String(length=20), nullable=False),
        sa.Column("approver", sa.String(length=160), nullable=False),
        sa.Column("evaluation_status", sa.String(length=40), nullable=False),
        sa.Column("drift_status", sa.String(length=40), nullable=False),
        _created_at(),
        sa.Column("activated_at", UTC, nullable=True),
        sa.Column("retired_at", UTC, nullable=True),
        sa.CheckConstraint(
            "approval_status IN ('candidate', 'approved', 'rejected', 'archived')",
            name="ck_model_versions_approval_status",
        ),
        sa.CheckConstraint(
            "activated_at IS NULL OR activated_at >= created_at",
            name="ck_model_versions_activation_time",
        ),
        sa.CheckConstraint(
            "retired_at IS NULL OR activated_at IS NULL OR retired_at >= activated_at",
            name="ck_model_versions_retirement_time",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_model_versions"),
        sa.UniqueConstraint(
            "model_name",
            "semantic_version",
            name="uq_model_versions_name_version",
        ),
        sa.UniqueConstraint("mlflow_run_id", name="uq_model_versions_mlflow_run_id"),
    )
    op.create_index(
        "ix_model_versions_name_status",
        "model_versions",
        ["model_name", "approval_status"],
    )

    op.create_table(
        "scenario_definitions",
        _id(),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        _json("shocks"),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "version ~ '^[0-9]+\\.[0-9]+\\.[0-9]+$'",
            name="ck_scenario_definitions_version",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scenario_definitions"),
        sa.UniqueConstraint(
            "name",
            "version",
            name="uq_scenario_definitions_name_version",
        ),
    )
    op.create_index(
        "ix_scenario_definitions_system_name",
        "scenario_definitions",
        ["is_system", "name"],
    )

    op.create_table(
        "positions",
        _id(),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("instrument_id", UUID, nullable=False),
        sa.Column("quantity", MONEY, nullable=False),
        sa.Column("average_cost", MONEY, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("as_of", UTC, nullable=False),
        sa.Column("tags", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("average_cost >= 0", name="ck_positions_average_cost_nonnegative"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_positions_currency_format"),
        sa.CheckConstraint(
            "jsonb_typeof(tags) = 'object'",
            name="ck_positions_tags_object",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_positions_instrument_id_instruments",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            name="fk_positions_portfolio_id_portfolios",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_positions"),
        sa.UniqueConstraint(
            "portfolio_id",
            "instrument_id",
            "as_of",
            name="uq_positions_portfolio_instrument_as_of",
        ),
    )
    op.create_index(
        "ix_positions_portfolio_as_of",
        "positions",
        ["portfolio_id", sa.text("as_of DESC")],
    )
    op.create_index(
        "ix_positions_instrument_as_of",
        "positions",
        ["instrument_id", sa.text("as_of DESC")],
    )

    op.create_table(
        "price_bars",
        _id(),
        sa.Column("instrument_id", UUID, nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("observed_at", UTC, nullable=False),
        sa.Column("open", MONEY, nullable=False),
        sa.Column("high", MONEY, nullable=False),
        sa.Column("low", MONEY, nullable=False),
        sa.Column("close", MONEY, nullable=False),
        sa.Column("volume", MONEY, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_event_id", sa.String(length=200), nullable=False),
        sa.Column("quality_status", sa.String(length=20), nullable=False),
        sa.Column("ingested_at", UTC, nullable=False),
        sa.Column("pipeline_run_id", UUID, nullable=False),
        sa.CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0",
            name="ck_price_bars_positive_ohlc",
        ),
        sa.CheckConstraint(
            "high >= GREATEST(open, close, low) AND low <= LEAST(open, close, high)",
            name="ck_price_bars_ohlc_relationship",
        ),
        sa.CheckConstraint("volume >= 0", name="ck_price_bars_volume_nonnegative"),
        sa.CheckConstraint(
            "interval ~ '^[1-9][0-9]*(m|h|d|w)$'",
            name="ck_price_bars_interval_format",
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_price_bars_currency_format"),
        sa.CheckConstraint(
            "quality_status IN ('accepted', 'warning')",
            name="ck_price_bars_quality_status",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_price_bars_instrument_id_instruments",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_runs.id"],
            name="fk_price_bars_pipeline_run_id_pipeline_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_price_bars"),
        sa.UniqueConstraint(
            "instrument_id",
            "interval",
            "observed_at",
            "source",
            name="uq_price_bars_instrument_interval_observed_source",
        ),
        sa.UniqueConstraint("source", "source_event_id", name="uq_price_bars_source_event"),
        comment="Initially unpartitioned; see revision policy before production partitioning.",
    )
    op.create_index(
        "ix_price_bars_instrument_observed",
        "price_bars",
        ["instrument_id", sa.text("observed_at DESC")],
    )
    op.create_index(
        "ix_price_bars_latest_lookup",
        "price_bars",
        ["instrument_id", "interval", sa.text("observed_at DESC")],
    )

    op.create_table(
        "market_events",
        _id(),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("source_event_id", sa.String(length=200), nullable=False),
        sa.Column("occurred_at", UTC, nullable=False),
        sa.Column("received_at", UTC, nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("processing_status", sa.String(length=20), nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("causation_id", UUID, nullable=True),
        sa.CheckConstraint("schema_version >= 1", name="ck_market_events_schema_version"),
        sa.CheckConstraint("received_at >= occurred_at", name="ck_market_events_receive_time"),
        sa.CheckConstraint(
            "payload_hash ~ '^[0-9a-f]{64}$'",
            name="ck_market_events_payload_hash_format",
        ),
        sa.CheckConstraint(
            "processing_status IN ('received', 'processed', 'duplicate', 'late', 'rejected')",
            name="ck_market_events_processing_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_market_events"),
        sa.UniqueConstraint(
            "event_type",
            "source_event_id",
            name="uq_market_events_type_source_event",
        ),
    )
    op.create_index(
        "ix_market_events_status_received",
        "market_events",
        ["processing_status", sa.text("received_at DESC")],
    )
    op.create_index("ix_market_events_correlation", "market_events", ["correlation_id"])

    op.create_table(
        "risk_snapshots",
        _id(),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("portfolio_version", sa.Integer(), nullable=False),
        sa.Column("as_of", UTC, nullable=False),
        sa.Column("methodology_version", sa.String(length=80), nullable=False),
        sa.Column("window_start", UTC, nullable=False),
        sa.Column("window_end", UTC, nullable=False),
        sa.Column("confidence_level", sa.Numeric(8, 7), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("portfolio_value", MONEY, nullable=False),
        sa.Column("daily_pnl", MONEY, nullable=False),
        sa.Column("volatility_annualized", RATIO, nullable=True),
        sa.Column("var_historical", MONEY, nullable=True),
        sa.Column("var_parametric", MONEY, nullable=True),
        sa.Column("expected_shortfall", MONEY, nullable=True),
        sa.Column("max_drawdown", RATIO, nullable=True),
        sa.Column("data_completeness", sa.Numeric(8, 7), nullable=False),
        sa.Column("quality_status", sa.String(length=32), nullable=False),
        _json("metrics"),
        _json("evidence_manifest"),
        _created_at(),
        sa.CheckConstraint(
            "portfolio_version >= 1",
            name="ck_risk_snapshots_portfolio_version",
        ),
        sa.CheckConstraint(
            "window_start <= window_end AND window_end <= as_of",
            name="ck_risk_snapshots_window_order",
        ),
        sa.CheckConstraint(
            "confidence_level > 0 AND confidence_level < 1",
            name="ck_risk_snapshots_confidence",
        ),
        sa.CheckConstraint(
            "data_completeness >= 0 AND data_completeness <= 1",
            name="ck_risk_snapshots_completeness",
        ),
        sa.CheckConstraint(
            "base_currency ~ '^[A-Z]{3}$'",
            name="ck_risk_snapshots_currency_format",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            name="fk_risk_snapshots_portfolio_id_portfolios",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_snapshots"),
        sa.UniqueConstraint(
            "portfolio_id",
            "portfolio_version",
            "as_of",
            "methodology_version",
            name="uq_risk_snapshots_portfolio_version_asof_method",
        ),
    )
    op.create_index(
        "ix_risk_snapshots_portfolio_as_of",
        "risk_snapshots",
        ["portfolio_id", sa.text("as_of DESC")],
    )
    op.create_index(
        "ix_risk_snapshots_quality_created",
        "risk_snapshots",
        ["quality_status", sa.text("created_at DESC")],
    )

    op.create_table(
        "risk_contributions",
        sa.Column("risk_snapshot_id", UUID, nullable=False),
        sa.Column("instrument_id", UUID, nullable=False),
        sa.Column("market_value", MONEY, nullable=False),
        sa.Column("weight", RATIO, nullable=False),
        sa.Column("volatility_contribution", RATIO, nullable=False),
        sa.Column("var_contribution", MONEY, nullable=True),
        sa.Column("evidence_id", sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_risk_contributions_instrument_id_instruments",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["risk_snapshot_id"],
            ["risk_snapshots.id"],
            name="fk_risk_contributions_risk_snapshot_id_risk_snapshots",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "risk_snapshot_id",
            "instrument_id",
            name="pk_risk_contributions",
        ),
        sa.UniqueConstraint("evidence_id", name="uq_risk_contributions_evidence_id"),
    )
    op.create_index(
        "ix_risk_contributions_instrument",
        "risk_contributions",
        ["instrument_id"],
    )

    op.create_table(
        "scenario_runs",
        _id(),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("portfolio_version", sa.Integer(), nullable=False),
        sa.Column("scenario_definition_id", UUID, nullable=False),
        sa.Column("scenario_version", sa.String(length=40), nullable=False),
        sa.Column("run_at", UTC, nullable=False),
        sa.Column("base_value", MONEY, nullable=False),
        sa.Column("stressed_value", MONEY, nullable=False),
        sa.Column("pnl_impact", MONEY, nullable=False),
        _json("component_impacts"),
        _json("assumptions"),
        _json("evidence_manifest"),
        sa.CheckConstraint(
            "portfolio_version >= 1",
            name="ck_scenario_runs_portfolio_version",
        ),
        sa.CheckConstraint(
            "scenario_version ~ '^[0-9]+\\.[0-9]+\\.[0-9]+$'",
            name="ck_scenario_runs_scenario_version",
        ),
        sa.CheckConstraint(
            "pnl_impact = stressed_value - base_value",
            name="ck_scenario_runs_pnl_reconciles",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            name="fk_scenario_runs_portfolio_id_portfolios",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_definition_id"],
            ["scenario_definitions.id"],
            name="fk_scenario_runs_scenario_definition_id_scenario_definitions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scenario_runs"),
    )
    op.create_index(
        "ix_scenario_runs_portfolio_run_at",
        "scenario_runs",
        ["portfolio_id", sa.text("run_at DESC")],
    )

    op.create_table(
        "data_quality_issues",
        _id(),
        sa.Column("pipeline_run_id", UUID, nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_reference", sa.String(length=300), nullable=False),
        sa.Column("rule_code", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        _json("observed_value"),
        sa.Column("expected_constraint", sa.Text(), nullable=False),
        sa.Column("quarantined_payload_reference", sa.Text(), nullable=True),
        _created_at(),
        sa.Column("resolved_at", UTC, nullable=True),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'error', 'critical')",
            name="ck_data_quality_issues_severity",
        ),
        sa.CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= created_at",
            name="ck_data_quality_issues_resolution_time",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_runs.id"],
            name="fk_data_quality_issues_pipeline_run_id_pipeline_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_data_quality_issues"),
    )
    op.create_index(
        "ix_data_quality_issues_run_severity",
        "data_quality_issues",
        ["pipeline_run_id", "severity"],
    )
    op.create_index(
        "ix_data_quality_issues_unresolved",
        "data_quality_issues",
        ["created_at"],
        postgresql_where=sa.text("resolved_at IS NULL"),
    )

    op.create_table(
        "document_chunks",
        _id(),
        sa.Column("document_id", UUID, nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("evidence_id", sa.String(length=160), nullable=False),
        _json("metadata", default=True),
        sa.CheckConstraint("chunk_index >= 0", name="ck_document_chunks_index_nonnegative"),
        sa.CheckConstraint("token_count > 0", name="ck_document_chunks_token_count_positive"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_chunks_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_chunks"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_index",
        ),
        sa.UniqueConstraint("evidence_id", name="uq_document_chunks_evidence_id"),
    )
    op.create_index(
        "ix_document_chunks_document",
        "document_chunks",
        ["document_id", "chunk_index"],
    )
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("embedding IS NOT NULL"),
    )

    op.create_table(
        "model_evaluations",
        _id(),
        sa.Column("model_version_id", UUID, nullable=False),
        sa.Column("evaluation_type", sa.String(length=80), nullable=False),
        sa.Column("evaluation_data_version", sa.String(length=120), nullable=False),
        _json("metrics"),
        _json("thresholds"),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("evaluated_at", UTC, nullable=False),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name="fk_model_evaluations_model_version_id_model_versions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_model_evaluations"),
        sa.UniqueConstraint(
            "model_version_id",
            "evaluation_type",
            "evaluation_data_version",
            name="uq_model_evaluations_model_type_data",
        ),
    )
    op.create_index(
        "ix_model_evaluations_model_evaluated",
        "model_evaluations",
        ["model_version_id", sa.text("evaluated_at DESC")],
    )

    op.create_table(
        "generated_risk_briefs",
        _id(),
        sa.Column("portfolio_id", UUID, nullable=False),
        sa.Column("risk_snapshot_id", UUID, nullable=False),
        sa.Column("scenario_run_id", UUID, nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("workflow_version", sa.String(length=40), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        _json("structured_content"),
        sa.Column("cited_evidence_ids", JSONB, nullable=False),
        _json("tool_trace_summary"),
        sa.Column("validation_status", sa.String(length=40), nullable=False),
        sa.Column("refusal_category", sa.String(length=80), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_generated_briefs_latency",
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_generated_briefs_input_tokens",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_generated_briefs_output_tokens",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(cited_evidence_ids) = 'array'",
            name="ck_generated_briefs_citations_array",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            name="fk_generated_risk_briefs_portfolio_id_portfolios",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["risk_snapshot_id"],
            ["risk_snapshots.id"],
            name="fk_generated_risk_briefs_risk_snapshot_id_risk_snapshots",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_run_id"],
            ["scenario_runs.id"],
            name="fk_generated_risk_briefs_scenario_run_id_scenario_runs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_generated_risk_briefs"),
    )
    op.create_index(
        "ix_generated_briefs_portfolio_created",
        "generated_risk_briefs",
        ["portfolio_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_generated_briefs_validation",
        "generated_risk_briefs",
        ["validation_status", sa.text("created_at DESC")],
    )

    op.create_table(
        "audit_events",
        _id(),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("aggregate_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_id", UUID, nullable=True),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("occurred_at", UTC, nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        _json("details", default=True),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index(
        "ix_audit_events_aggregate",
        "audit_events",
        ["aggregate_type", "aggregate_id", sa.text("occurred_at DESC")],
    )
    op.create_index("ix_audit_events_correlation", "audit_events", ["correlation_id"])
    op.create_index(
        "ix_audit_events_action_occurred",
        "audit_events",
        ["action", sa.text("occurred_at DESC")],
    )

    op.create_table(
        "outbox_events",
        _id(),
        sa.Column("aggregate_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_id", UUID, nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("producer", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("occurred_at", UTC, nullable=False),
        sa.Column("available_at", UTC, nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("causation_id", UUID, nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("published_at", UTC, nullable=True),
        sa.Column("error_summary", sa.String(length=512), nullable=True),
        _json("event_envelope"),
        _created_at(),
        sa.Column("updated_at", UTC, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("schema_version >= 1", name="ck_outbox_events_schema_version"),
        sa.CheckConstraint("attempts >= 0", name="ck_outbox_events_attempts"),
        sa.CheckConstraint(
            "available_at >= occurred_at",
            name="ck_outbox_events_available_time",
        ),
        sa.CheckConstraint(
            "event_type ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'",
            name="ck_outbox_events_event_type_format",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(event_envelope) = 'object'",
            name="ck_outbox_events_envelope_object",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'retry_scheduled', 'published', 'dead_letter')",
            name="ck_outbox_events_status",
        ),
        sa.CheckConstraint(
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
        sa.PrimaryKeyConstraint("id", name="pk_outbox_events"),
        sa.UniqueConstraint("idempotency_key", name="uq_outbox_events_idempotency_key"),
    )
    op.create_index(
        "ix_outbox_events_available_pending",
        "outbox_events",
        ["available_at"],
        postgresql_where=sa.text("status IN ('pending', 'retry_scheduled')"),
    )
    op.create_index(
        "ix_outbox_events_aggregate",
        "outbox_events",
        ["aggregate_type", "aggregate_id"],
    )
    op.create_index("ix_outbox_events_correlation", "outbox_events", ["correlation_id"])


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("audit_events")
    op.drop_table("generated_risk_briefs")
    op.drop_table("model_evaluations")
    op.drop_table("document_chunks")
    op.drop_table("data_quality_issues")
    op.drop_table("scenario_runs")
    op.drop_table("risk_contributions")
    op.drop_table("risk_snapshots")
    op.drop_table("market_events")
    op.drop_table("price_bars")
    op.drop_table("positions")
    op.drop_table("scenario_definitions")
    op.drop_table("model_versions")
    op.drop_table("documents")
    op.drop_table("portfolios")
    op.drop_table("pipeline_runs")
    op.drop_table("instruments")
    # Do not drop the shared vector extension; other schemas may depend on it.
