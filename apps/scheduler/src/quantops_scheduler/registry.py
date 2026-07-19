"""Typed immutable job registry and deterministic plan construction."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from quantops_scheduler.config import (
    AiEvaluationConfig,
    DatasetGenerateConfig,
    DatasetVerifyConfig,
    JobConfig,
    MlLifecycleConfig,
    config_hash,
)
from quantops_scheduler.models import JobDefinition, JobName, JobPlan

_NAMESPACE = uuid5(NAMESPACE_URL, "https://quantops.dev/scheduler/run/v1")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("scheduled_for must be timezone-aware UTC")
    return value.astimezone(UTC)


class JobRegistry:
    def __init__(self, definitions: Sequence[JobDefinition]) -> None:
        values = {item.name: item for item in definitions}
        if len(values) != len(definitions):
            raise ValueError("job registry contains duplicate names")
        if not values:
            raise ValueError("job registry must not be empty")
        self._definitions = values

    def definition(self, name: JobName) -> JobDefinition:
        try:
            return self._definitions[name]
        except KeyError as error:
            raise KeyError(f"unregistered job: {name}") from error

    @property
    def definitions(self) -> tuple[JobDefinition, ...]:
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    def plan(
        self,
        name: JobName,
        config: JobConfig,
        *,
        scheduled_for: datetime,
        dry_run: bool = False,
        python_executable: Path | None = None,
    ) -> JobPlan:
        definition = self.definition(name)
        if not isinstance(config, definition.config_type):
            raise TypeError(
                f"job {name.value} requires {definition.config_type.__name__}, "
                f"received {type(config).__name__}"
            )
        normalized_time = _utc(scheduled_for)
        digest = config_hash(config)
        identity = json.dumps(
            {
                "config_hash": digest,
                "dry_run": dry_run,
                "job_name": name.value,
                "scheduled_for": normalized_time.isoformat().replace("+00:00", "Z"),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        command = config.command(python_executable or Path(sys.executable))
        return JobPlan(
            run_id=uuid5(_NAMESPACE, identity),
            definition=definition,
            config=config,
            config_hash=digest,
            scheduled_for=normalized_time,
            dry_run=dry_run,
            command=command,
        )


def default_registry() -> JobRegistry:
    return JobRegistry(
        (
            JobDefinition(
                JobName.GENERATE_DEMO_DATASET,
                "Generate deterministic synthetic dataset artifacts through quantops_pipelines.",
                DatasetGenerateConfig,
                180.0,
                None,
            ),
            JobDefinition(
                JobName.VERIFY_DEMO_DATASET,
                "Verify the deterministic dataset manifest and hashes through quantops_pipelines.",
                DatasetVerifyConfig,
                60.0,
                "0 3 * * *",
            ),
            JobDefinition(
                JobName.RUN_ML_LIFECYCLE,
                "Run the offline risk-regime lifecycle through quantops_ml with MLflow disabled.",
                MlLifecycleConfig,
                900.0,
                "0 4 * * 1",
            ),
            JobDefinition(
                JobName.EVALUATE_AI_WORKFLOW,
                "Run deterministic grounded-AI evaluations through quantops_ai.",
                AiEvaluationConfig,
                300.0,
                "0 5 * * 1",
            ),
        )
    )


def default_job_configs(workspace_root: Path) -> dict[JobName, JobConfig]:
    root = workspace_root.resolve(strict=False)
    dataset = root / "data" / "synthetic"
    return {
        JobName.GENERATE_DEMO_DATASET: DatasetGenerateConfig(
            dataset / "generator_config.json",
            dataset,
        ),
        JobName.VERIFY_DEMO_DATASET: DatasetVerifyConfig(dataset),
        JobName.RUN_ML_LIFECYCLE: MlLifecycleConfig(
            dataset / "canonical" / "price_bars.csv",
            dataset / "manifest.json",
            root / "ml" / "artifacts" / "demo",
        ),
        JobName.EVALUATE_AI_WORKFLOW: AiEvaluationConfig(
            root / "packages" / "ai_engine" / "evals" / "v1" / "cases.jsonl",
            root / "packages" / "ai_engine" / "artifacts" / "evaluation-report.json",
        ),
    }


def config_from_mapping(name: JobName, raw: Mapping[str, object]) -> JobConfig:
    def path(key: str) -> Path:
        value = raw.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{key} must be a non-empty path string")
        return Path(value)

    if name is JobName.GENERATE_DEMO_DATASET:
        _exact_keys(raw, {"generator_config", "output_dir"})
        return DatasetGenerateConfig(path("generator_config"), path("output_dir"))
    if name is JobName.VERIFY_DEMO_DATASET:
        _exact_keys(raw, {"dataset_dir"})
        return DatasetVerifyConfig(path("dataset_dir"))
    if name is JobName.RUN_ML_LIFECYCLE:
        _exact_keys(
            raw,
            {"prices_path", "manifest_path", "output_dir", "code_revision", "mlflow_enabled"},
        )
        if raw.get("mlflow_enabled") is not False:
            raise ValueError("scheduled MLflow integration is unavailable in the offline slice")
        revision = raw.get("code_revision")
        if revision is not None and not isinstance(revision, str):
            raise ValueError("code_revision must be a string or null")
        return MlLifecycleConfig(
            path("prices_path"),
            path("manifest_path"),
            path("output_dir"),
            revision,
        )
    _exact_keys(raw, {"cases_path", "output_path"})
    output = raw.get("output_path")
    if output is not None and not isinstance(output, str):
        raise ValueError("output_path must be a string or null")
    return AiEvaluationConfig(path("cases_path"), None if output is None else Path(output))


def _exact_keys(raw: Mapping[str, object], expected: set[str]) -> None:
    if set(raw) != expected:
        raise ValueError("job configuration fields do not match the registered schema")
