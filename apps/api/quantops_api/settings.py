"""Validated API configuration sourced from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings with deliberately safe demo defaults."""

    model_config = SettingsConfigDict(
        env_prefix="QUANTOPS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    demo_mode: bool = True
    demo_api_token: str = Field(default="replace-with-a-local-random-token", min_length=16)
    database_url: str = "postgresql+asyncpg://quantops:quantops_local@localhost:5432/quantops"
    cors_origins: str = "http://localhost:5173"
    ai_provider: str = "deterministic"
    expensive_rate_limit: int = Field(default=20, ge=1, le=1_000)
    expensive_rate_window_seconds: int = Field(default=60, ge=1, le=3_600)

    @property
    def cors_origin_list(self) -> tuple[str, ...]:
        """Return a normalized, immutable CORS allowlist."""

        return tuple(origin.strip() for origin in self.cors_origins.split(",") if origin.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build settings once per application process."""

    return Settings()
