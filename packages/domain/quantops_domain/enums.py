"""Stable domain enumerations used across application boundaries."""

from enum import StrEnum


class AssetClass(StrEnum):
    EQUITY_INDEX = "equity_index"
    EQUITY = "equity"
    COMMODITY = "commodity"
    FX = "fx"
    BOND = "bond"
    CASH = "cash"
    SYNTHETIC = "synthetic"


class AuditAction(StrEnum):
    PORTFOLIO_CREATED = "portfolio.created"
    PORTFOLIO_UPDATED = "portfolio.updated"
    RISK_RECOMPUTED = "risk.recomputed"
    SCENARIO_EXECUTED = "scenario.executed"
    DATA_IMPORTED = "data.imported"
    MODEL_ACTIVATED = "model.activated"
    AI_BRIEF_GENERATED = "ai.brief.generated"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    RETRY_SCHEDULED = "retry_scheduled"
    PUBLISHED = "published"
    DEAD_LETTER = "dead_letter"
