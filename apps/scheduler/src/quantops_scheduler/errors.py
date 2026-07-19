"""Safe scheduler boundary failures."""

from __future__ import annotations


class SchedulerError(Exception):
    """Base scheduler error."""


class SchedulerUnavailableError(SchedulerError):
    """The optional scheduler or command runtime is unavailable."""

    code = "scheduler_unavailable"

    def __init__(self) -> None:
        super().__init__(self.code)


class InvalidJobOutputError(SchedulerError):
    """A wrapped command returned output that does not match its public summary."""

    code = "invalid_job_output"

    def __init__(self) -> None:
        super().__init__(self.code)


class ExplicitCancellation(SchedulerError):
    """The caller requested cancellation through the cooperative boundary."""

    code = "cancelled"

    def __init__(self) -> None:
        super().__init__(self.code)


class OutputLimitError(SchedulerError):
    """A child command exceeded the bounded captured-output allowance."""

    code = "output_limit_exceeded"

    def __init__(self) -> None:
        super().__init__(self.code)
