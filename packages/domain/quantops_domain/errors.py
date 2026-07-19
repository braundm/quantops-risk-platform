"""Domain-specific exceptions with no transport or persistence coupling."""

from __future__ import annotations

from uuid import UUID


class DomainError(Exception):
    """Base class for expected business-rule failures."""


class DomainValidationError(DomainError, ValueError):
    """Raised when a value cannot exist in the QuantOps domain."""


class CurrencyMismatchError(DomainError):
    """Raised when an operation would silently combine different currencies."""

    def __init__(self, left: str, right: str) -> None:
        self.left = left
        self.right = right
        super().__init__(f"currency mismatch: {left} != {right}")


class OptimisticConcurrencyError(DomainError):
    """Raised when a write is based on a stale aggregate version."""

    def __init__(self, aggregate_id: UUID, expected: int, actual: int) -> None:
        self.aggregate_id = aggregate_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"stale portfolio {aggregate_id}: expected version {expected}, actual version {actual}"
        )


class InvalidStateTransitionError(DomainError):
    """Raised when an entity state transition is not legal."""
