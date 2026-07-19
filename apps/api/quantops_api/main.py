"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quantops_api import __version__
from quantops_api.api.router import router
from quantops_api.settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Own process-level resources without side effects during import."""

    yield


def create_app() -> FastAPI:
    """Construct an isolated application instance for runtime and tests."""

    settings = get_settings()
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
        allow_origins=list(settings.cors_origin_list),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "Idempotency-Key", "X-Demo-Token"],
    )
    application.include_router(router)
    return application


app = create_app()
