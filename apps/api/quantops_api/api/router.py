"""Versioned API routes available before infrastructure is connected."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from quantops_api import __version__
from quantops_api.settings import get_settings

router = APIRouter(prefix="/api/v1")


class HealthResponse(BaseModel):
    """Stable health/readiness response contract."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "ready", "degraded"]
    service: Literal["quantops-api"] = "quantops-api"
    version: str


class VersionResponse(BaseModel):
    """Build identity without leaking environment details."""

    model_config = ConfigDict(frozen=True)

    name: Literal["QuantOps"] = "QuantOps"
    version: str
    methodology_version: str


@router.get("/health", response_model=HealthResponse, tags=["operations"])
async def health() -> HealthResponse:
    """Report process liveness without testing downstream dependencies."""

    return HealthResponse(status="ok", version=__version__)


@router.get("/ready", response_model=HealthResponse, tags=["operations"])
async def ready() -> HealthResponse:
    """Report scaffold readiness; dependency checks are added with persistence."""

    settings = get_settings()
    status: Literal["ready", "degraded"] = "ready" if settings.demo_mode else "degraded"
    return HealthResponse(status=status, version=__version__)


@router.get("/version", response_model=VersionResponse, tags=["operations"])
async def version() -> VersionResponse:
    """Return application and risk-methodology versions."""

    return VersionResponse(version=__version__, methodology_version="0.1.0")
