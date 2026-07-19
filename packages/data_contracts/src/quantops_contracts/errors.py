"""Explicit boundary errors for unsupported and unsafe event input."""

from __future__ import annotations


class EventContractError(ValueError):
    """Base class for non-Pydantic contract-boundary failures."""


class UnsupportedEventTypeError(EventContractError):
    """Raised when no contract family is registered for an event type."""

    def __init__(self, event_type: object) -> None:
        self.event_type = event_type
        super().__init__(f"unsupported event_type: {event_type!r}")


class UnsupportedVersionError(EventContractError):
    """Raised before payload parsing when an event version is unsupported."""

    def __init__(
        self,
        event_family: str,
        received_version: object,
        supported_versions: tuple[int, ...] = (1,),
    ) -> None:
        self.event_family = event_family
        self.received_version = received_version
        self.supported_versions = supported_versions
        supported = ", ".join(str(version) for version in supported_versions)
        super().__init__(
            f"unsupported schema version {received_version!r} for {event_family}; "
            f"supported versions: {supported}"
        )


class MessageTooLargeError(EventContractError):
    """Raised when raw, payload, or canonical message bytes exceed a hard limit."""

    def __init__(self, scope: str, actual_bytes: int, maximum_bytes: int) -> None:
        self.scope = scope
        self.actual_bytes = actual_bytes
        self.maximum_bytes = maximum_bytes
        super().__init__(
            f"{scope} is {actual_bytes} bytes; maximum permitted size is {maximum_bytes} bytes"
        )


class MalformedEventError(EventContractError):
    """Raised for malformed JSON before typed Pydantic validation can begin."""
