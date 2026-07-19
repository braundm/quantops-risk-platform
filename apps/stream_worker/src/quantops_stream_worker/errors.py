"""Stable failure classes used for retry and dead-letter decisions."""

from __future__ import annotations

import re

_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def _validated_code(value: str) -> str:
    if _SAFE_CODE.fullmatch(value) is None:
        raise ValueError("failure code must be a lowercase safe identifier")
    return value


class StreamWorkerError(Exception):
    """Base worker failure."""


class PermanentProcessingError(StreamWorkerError):
    """A deterministic message failure that is safe to dead-letter."""

    def __init__(self, code: str = "permanent_processing_failure") -> None:
        self.code = _validated_code(code)
        super().__init__(self.code)


class IdempotencyConflictError(PermanentProcessingError):
    """The same stable identity was observed with different canonical content."""

    def __init__(self) -> None:
        super().__init__("idempotency_conflict")


class TransientProcessingError(StreamWorkerError):
    """A retryable dependency or durability failure."""

    def __init__(self, code: str = "transient_processing_failure") -> None:
        self.code = _validated_code(code)
        super().__init__(self.code)


class BrokerUnavailableError(TransientProcessingError):
    """The broker did not acknowledge a publish or offset commit."""

    def __init__(self) -> None:
        super().__init__("broker_unavailable")
