"""Public API for the framework-independent QuantOps domain package."""

from quantops_domain.audit import AuditEvent
from quantops_domain.entities import Instrument, Portfolio, Position
from quantops_domain.enums import AssetClass, AuditAction, OutboxStatus
from quantops_domain.errors import (
    CurrencyMismatchError,
    DomainError,
    DomainValidationError,
    InvalidStateTransitionError,
    OptimisticConcurrencyError,
)
from quantops_domain.outbox import OutboxEvent
from quantops_domain.ports import (
    AuditEventRepository,
    FxRateProvider,
    InstrumentRepository,
    OutboxEventRepository,
    PortfolioRepository,
    PositionRepository,
    UnitOfWork,
)
from quantops_domain.serialization import canonical_json, to_primitive
from quantops_domain.value_objects import (
    ISO_4217_CODES,
    Currency,
    InstrumentIdentity,
    InstrumentSymbol,
    Money,
)

__all__ = [
    "ISO_4217_CODES",
    "AssetClass",
    "AuditAction",
    "AuditEvent",
    "AuditEventRepository",
    "Currency",
    "CurrencyMismatchError",
    "DomainError",
    "DomainValidationError",
    "FxRateProvider",
    "Instrument",
    "InstrumentIdentity",
    "InstrumentRepository",
    "InstrumentSymbol",
    "InvalidStateTransitionError",
    "Money",
    "OptimisticConcurrencyError",
    "OutboxEvent",
    "OutboxEventRepository",
    "OutboxStatus",
    "Portfolio",
    "PortfolioRepository",
    "Position",
    "PositionRepository",
    "UnitOfWork",
    "canonical_json",
    "to_primitive",
]
