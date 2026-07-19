"""Immutable, deliberately low-data audit records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from quantops_domain._validation import (
    as_utc,
    fail,
    freeze_json_object,
    require_optional_uuid,
    require_text,
    require_uuid,
)
from quantops_domain.enums import AuditAction


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """A safe audit fact; secrets and authorization material are rejected."""

    id: UUID
    action: AuditAction
    aggregate_type: str
    aggregate_id: UUID | None
    actor_id: str
    occurred_at: datetime
    correlation_id: UUID
    details: Mapping[str, Any] = field(default_factory=dict, hash=False, repr=False)

    def __post_init__(self) -> None:
        require_uuid(self.id, "id")
        if not isinstance(self.action, AuditAction):
            fail("action", "must be AuditAction")
        aggregate_type = require_text(self.aggregate_type, "aggregate_type", maximum=80).casefold()
        require_optional_uuid(self.aggregate_id, "aggregate_id")
        actor_id = require_text(self.actor_id, "actor_id", maximum=120)
        occurred_at = as_utc(self.occurred_at, "occurred_at")
        require_uuid(self.correlation_id, "correlation_id")
        details = freeze_json_object(
            self.details,
            "details",
            max_bytes=16_384,
            reject_sensitive_keys=True,
        )

        object.__setattr__(self, "aggregate_type", aggregate_type)
        object.__setattr__(self, "actor_id", actor_id)
        object.__setattr__(self, "occurred_at", occurred_at)
        object.__setattr__(self, "details", details)

    @classmethod
    def create(
        cls,
        *,
        action: AuditAction,
        aggregate_type: str,
        aggregate_id: UUID | None,
        actor_id: str,
        occurred_at: datetime,
        details: Mapping[str, Any] | None = None,
        audit_id: UUID | None = None,
        correlation_id: UUID | None = None,
    ) -> AuditEvent:
        return cls(
            id=audit_id or uuid4(),
            action=action,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            actor_id=actor_id,
            occurred_at=occurred_at,
            correlation_id=correlation_id or uuid4(),
            details=details or {},
        )
