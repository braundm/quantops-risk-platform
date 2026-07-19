"""Transport-neutral application errors mapped to problem details by the API."""

from __future__ import annotations


class ApplicationError(Exception):
    """Expected application failure with a stable public code."""

    status_code = 400
    code = "application_error"
    title = "Application request failed"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class NotFoundError(ApplicationError):
    status_code = 404
    code = "not_found"
    title = "Resource not found"


class ConflictError(ApplicationError):
    status_code = 409
    code = "conflict"
    title = "Resource conflict"


class RequestFormatError(ApplicationError):
    status_code = 400
    code = "invalid_request"
    title = "Invalid request"


class AuthenticationError(ApplicationError):
    status_code = 401
    code = "demo_token_required"
    title = "Authentication required"


class PreconditionRequiredError(ApplicationError):
    status_code = 428
    code = "precondition_required"
    title = "Precondition required"


class FeatureUnavailableError(ApplicationError):
    status_code = 503
    code = "feature_unavailable"
    title = "Feature unavailable"


class RateLimitError(ApplicationError):
    status_code = 429
    code = "rate_limit_exceeded"
    title = "Rate limit exceeded"

    def __init__(self, detail: str, *, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(detail)
