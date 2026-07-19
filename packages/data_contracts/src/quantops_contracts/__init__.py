"""Versioned, deterministic, broker-independent QuantOps event contracts."""

from quantops_contracts._base import (
    MAX_MESSAGE_BYTES,
    MAX_PAYLOAD_BYTES,
    MAX_RAW_INPUT_BYTES,
    canonical_json,
)
from quantops_contracts.codec import parse_event_json, parse_event_mapping
from quantops_contracts.envelope import (
    EVENT_PAYLOAD_TYPES,
    SUPPORTED_SCHEMA_VERSIONS,
    EventEnvelope,
    EventType,
    derive_idempotency_key,
)
from quantops_contracts.errors import (
    EventContractError,
    MalformedEventError,
    MessageTooLargeError,
    UnsupportedEventTypeError,
    UnsupportedVersionError,
)
from quantops_contracts.payloads import (
    AiBriefCreatedPayload,
    AiBriefRequestedPayload,
    BriefStatus,
    EventPayload,
    Payload,
    PortfolioChangedPayload,
    PortfolioChangeKind,
    PriceBarPayload,
    RecomputeReason,
    RiskQualityStatus,
    RiskRecomputeRequestedPayload,
    RiskSnapshotCreatedPayload,
)

__all__ = [
    "EVENT_PAYLOAD_TYPES",
    "MAX_MESSAGE_BYTES",
    "MAX_PAYLOAD_BYTES",
    "MAX_RAW_INPUT_BYTES",
    "SUPPORTED_SCHEMA_VERSIONS",
    "AiBriefCreatedPayload",
    "AiBriefRequestedPayload",
    "BriefStatus",
    "EventContractError",
    "EventEnvelope",
    "EventPayload",
    "EventType",
    "MalformedEventError",
    "MessageTooLargeError",
    "Payload",
    "PortfolioChangeKind",
    "PortfolioChangedPayload",
    "PriceBarPayload",
    "RecomputeReason",
    "RiskQualityStatus",
    "RiskRecomputeRequestedPayload",
    "RiskSnapshotCreatedPayload",
    "UnsupportedEventTypeError",
    "UnsupportedVersionError",
    "canonical_json",
    "derive_idempotency_key",
    "parse_event_json",
    "parse_event_mapping",
]

__version__ = "0.1.0"
