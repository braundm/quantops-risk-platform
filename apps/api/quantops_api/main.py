"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quantops_api import __version__
from quantops_api.api.middleware import FixedWindowRateLimiter, request_context_middleware
from quantops_api.api.problems import install_problem_handlers
from quantops_api.api.router import router
from quantops_api.application.demo_service import DemoQuantOpsService
from quantops_api.settings import Settings, get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Own process-level resources without side effects during import."""

    yield


def create_app(
    *,
    service: DemoQuantOpsService | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Construct an isolated application instance for runtime and tests."""

    runtime_settings = settings or get_settings()
    application = FastAPI(
        title="QuantOps API",
        summary="Market Risk, Data, and Grounded AI Research Platform",
        description=(
            "A research and risk-observability API. It does not execute trades or provide "
            "investment recommendations."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.cors_origin_list),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Content-Type",
            "Idempotency-Key",
            "If-Match",
            "X-Correlation-ID",
            "X-Demo-Token",
            "X-QuantOps-Demo-Token",
            "X-Request-ID",
        ],
        expose_headers=[
            "ETag",
            "Idempotent-Replay",
            "Retry-After",
            "X-Correlation-ID",
            "X-Request-ID",
        ],
    )
    application.state.settings = runtime_settings
    application.state.quantops_service = service or DemoQuantOpsService()
    application.state.expensive_rate_limiter = FixedWindowRateLimiter(
        capacity=runtime_settings.expensive_rate_limit,
        window_seconds=runtime_settings.expensive_rate_window_seconds,
    )
    application.middleware("http")(request_context_middleware)
    install_problem_handlers(application)
    application.include_router(router)
    return application


app = create_app()
