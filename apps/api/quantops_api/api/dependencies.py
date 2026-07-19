"""Small, testable HTTP boundary dependencies."""

from __future__ import annotations

import re
import secrets
from typing import Annotated, cast
from uuid import UUID

from fastapi import Header, Query, Request

from quantops_api.application.demo_service import DemoQuantOpsService
from quantops_api.application.errors import (
    AuthenticationError,
    PreconditionRequiredError,
    RequestFormatError,
)
from quantops_api.settings import Settings

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]

_ETAG_PATTERN = re.compile(r'^(?:W/)?"(?P<version>[1-9][0-9]*)"$')
_IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


def get_service(request: Request) -> DemoQuantOpsService:
    """Resolve the process-scoped deterministic application service."""

    return cast(DemoQuantOpsService, request.app.state.quantops_service)


def get_request_correlation_id(request: Request) -> UUID:
    """Return the normalized correlation ID installed by middleware."""

    return UUID(cast(str, request.state.correlation_id))


def require_demo_token(
    request: Request,
    x_quantops_demo_token: Annotated[str | None, Header(alias="X-QuantOps-Demo-Token")] = None,
    x_demo_token: Annotated[str | None, Header(alias="X-Demo-Token")] = None,
) -> None:
    """Protect writes with a constant-time local demo credential check."""

    settings = cast(Settings, request.app.state.settings)
    supplied = x_quantops_demo_token or x_demo_token
    if supplied is None or not secrets.compare_digest(
        supplied.encode("utf-8"), settings.demo_api_token.encode("utf-8")
    ):
        raise AuthenticationError(
            "a valid X-QuantOps-Demo-Token header is required for this operation"
        )


def require_if_match(
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> int:
    """Parse the strong or weak quoted aggregate-version ETag."""

    if if_match is None:
        raise PreconditionRequiredError(
            'If-Match is required; use the current portfolio ETag, for example "1"'
        )
    match = _ETAG_PATTERN.fullmatch(if_match.strip())
    if match is None:
        raise RequestFormatError('If-Match must be a quoted positive version, for example "1"')
    return int(match.group("version"))


def require_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    """Require a bounded, log-safe key for expensive repeatable writes."""

    if idempotency_key is None:
        raise RequestFormatError("Idempotency-Key is required for this operation")
    normalized = idempotency_key.strip()
    if _IDEMPOTENCY_PATTERN.fullmatch(normalized) is None:
        raise RequestFormatError(
            "Idempotency-Key must be 8-128 characters using letters, digits, '.', '_', ':', or '-'"
        )
    return normalized


def require_expensive_capacity(request: Request) -> None:
    """Apply the configured process-local demo limiter to expensive operations."""

    client = request.client.host if request.client is not None else "unknown"
    request.app.state.expensive_rate_limiter.check(f"{client}:{request.url.path}")


def etag(version: int) -> str:
    """Render a portfolio aggregate version as an HTTP entity tag."""

    return f'"{version}"'
