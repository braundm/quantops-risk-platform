"""RFC 9457-style problem responses with no internal exception leakage."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from quantops_domain import DomainValidationError, OptimisticConcurrencyError
from quantops_risk import RiskEngineError

from quantops_api.api.schemas import ProblemDetails, ProblemIssue
from quantops_api.application.errors import ApplicationError, RateLimitError

logger = logging.getLogger("quantops_api.errors")


def _identity(request: Request, attribute: str) -> str:
    return cast(str, getattr(request.state, attribute, str(uuid4())))


def _problem(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    errors: tuple[ProblemIssue, ...] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ProblemDetails(
        type=f"https://quantops.dev/problems/{code.replace('_', '-')}",
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        code=code,
        request_id=_identity(request, "request_id"),
        correlation_id=_identity(request, "correlation_id"),
        errors=errors,
    )
    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json", exclude_none=True),
        media_type="application/problem+json",
        headers=headers,
    )


async def application_error_handler(request: Request, exception: Exception) -> JSONResponse:
    error = cast(ApplicationError, exception)
    headers: dict[str, str] = {}
    if error.status_code == 401:
        headers["WWW-Authenticate"] = 'DemoToken realm="quantops-local"'
    if isinstance(error, RateLimitError):
        headers["Retry-After"] = str(error.retry_after)
    return _problem(
        request,
        status=error.status_code,
        code=error.code,
        title=error.title,
        detail=error.detail,
        headers=headers,
    )


async def validation_error_handler(request: Request, exception: Exception) -> JSONResponse:
    error = cast(RequestValidationError, exception)
    issues = tuple(
        ProblemIssue(
            location=tuple(item["loc"]),
            message=str(item["msg"]),
            code=str(item["type"]),
        )
        for item in error.errors()
    )
    return _problem(
        request,
        status=422,
        code="validation_error",
        title="Request validation failed",
        detail="one or more request fields are invalid",
        errors=issues,
    )


async def domain_validation_error_handler(request: Request, exception: Exception) -> JSONResponse:
    error = cast(DomainValidationError | RiskEngineError, exception)
    return _problem(
        request,
        status=422,
        code="domain_validation_error",
        title="Domain validation failed",
        detail=str(error),
    )


async def concurrency_error_handler(request: Request, exception: Exception) -> JSONResponse:
    error = cast(OptimisticConcurrencyError, exception)
    return _problem(
        request,
        status=409,
        code="stale_version",
        title="Portfolio version conflict",
        detail=str(error),
    )


async def http_error_handler(request: Request, exception: Exception) -> JSONResponse:
    error = cast(HTTPException, exception)
    return _problem(
        request,
        status=error.status_code,
        code="http_error",
        title="HTTP request failed",
        detail=str(error.detail),
        headers=error.headers,
    )


async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_request_error",
        extra={
            "request_id": _identity(request, "request_id"),
            "correlation_id": _identity(request, "correlation_id"),
            "path": request.url.path,
        },
    )
    return _problem(
        request,
        status=500,
        code="internal_error",
        title="Internal server error",
        detail="the request could not be completed",
    )


def install_problem_handlers(application: FastAPI) -> None:
    """Register the expected exception hierarchy from narrow to broad."""

    application.add_exception_handler(ApplicationError, application_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(DomainValidationError, domain_validation_error_handler)
    application.add_exception_handler(RiskEngineError, domain_validation_error_handler)
    application.add_exception_handler(OptimisticConcurrencyError, concurrency_error_handler)
    application.add_exception_handler(HTTPException, http_error_handler)
    application.add_exception_handler(Exception, unexpected_error_handler)
