"""Optional MLflow boundary that is inert and truthful by default."""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class TrackingStatus:
    provider: str
    status: str
    enabled: bool
    detail: str
    run_id: str | None = None

    def to_mapping(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "status": self.status,
            "enabled": self.enabled,
            "detail": self.detail,
            "run_id": self.run_id,
        }


def track_with_optional_mlflow(
    *,
    enabled: bool,
    tracking_uri: str | None,
    experiment_name: str,
    parameters: dict[str, object],
    metrics: dict[str, float],
    artifact_dir: Path,
) -> TrackingStatus:
    """Record only when explicitly enabled; otherwise avoid imports and external state."""

    if not enabled:
        return TrackingStatus(
            provider="mlflow",
            status="disabled",
            enabled=False,
            detail=(
                "Optional MLflow tracking is disabled; deterministic local artifacts are "
                "authoritative."
            ),
        )
    if importlib.util.find_spec("mlflow") is None:
        return TrackingStatus(
            provider="mlflow",
            status="unavailable",
            enabled=True,
            detail=(
                "MLflow is not installed; lifecycle completed with deterministic local artifacts."
            ),
        )
    if not tracking_uri:
        return TrackingStatus(
            provider="mlflow",
            status="not_configured",
            enabled=True,
            detail=(
                "MLflow is installed but no explicit tracking URI was supplied; no run was created."
            ),
        )
    try:
        mlflow: Any = importlib.import_module("mlflow")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        with mlflow.start_run() as run:
            mlflow.log_params(parameters)
            mlflow.log_metrics(metrics)
            mlflow.log_artifacts(str(artifact_dir))
            run_id = str(run.info.run_id)
    except Exception as error:  # external optional boundary must degrade without breaking local ML
        return TrackingStatus(
            provider="mlflow",
            status="degraded",
            enabled=True,
            detail=f"MLflow tracking failed safely: {type(error).__name__}",
        )
    return TrackingStatus(
        provider="mlflow",
        status="recorded",
        enabled=True,
        detail=(
            "Metrics and deterministic local artifacts were recorded to the configured MLflow URI."
        ),
        run_id=run_id,
    )
