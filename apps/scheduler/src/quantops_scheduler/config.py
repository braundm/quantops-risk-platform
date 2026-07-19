"""Typed offline job configuration and deterministic configuration hashing."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

_REVISION = re.compile(r"^[0-9a-f]{7,64}$")


def _path_text(value: Path) -> str:
    if not isinstance(value, Path):
        raise TypeError("job paths must be pathlib.Path values")
    return value.resolve(strict=False).as_posix()


def _canonical_mapping(value: dict[str, object]) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


@runtime_checkable
class JobConfig(Protocol):
    def to_mapping(self) -> dict[str, object]: ...

    def command(self, python_executable: Path) -> tuple[str, ...]: ...


def config_hash(config: JobConfig) -> str:
    return hashlib.sha256(_canonical_mapping(config.to_mapping()).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DatasetGenerateConfig:
    generator_config: Path
    output_dir: Path

    def __post_init__(self) -> None:
        _path_text(self.generator_config)
        _path_text(self.output_dir)

    def to_mapping(self) -> dict[str, object]:
        return {
            "generator_config": _path_text(self.generator_config),
            "output_dir": _path_text(self.output_dir),
        }

    def command(self, python_executable: Path) -> tuple[str, ...]:
        return (
            str(python_executable),
            "-m",
            "quantops_pipelines",
            "generate",
            "--config",
            str(self.generator_config),
            "--output",
            str(self.output_dir),
        )


@dataclass(frozen=True, slots=True)
class DatasetVerifyConfig:
    dataset_dir: Path

    def __post_init__(self) -> None:
        _path_text(self.dataset_dir)

    def to_mapping(self) -> dict[str, object]:
        return {"dataset_dir": _path_text(self.dataset_dir)}

    def command(self, python_executable: Path) -> tuple[str, ...]:
        return (
            str(python_executable),
            "-m",
            "quantops_pipelines",
            "verify",
            "--dataset",
            str(self.dataset_dir),
        )


@dataclass(frozen=True, slots=True)
class MlLifecycleConfig:
    prices_path: Path
    manifest_path: Path
    output_dir: Path
    code_revision: str | None = None

    def __post_init__(self) -> None:
        _path_text(self.prices_path)
        _path_text(self.manifest_path)
        _path_text(self.output_dir)
        if self.code_revision is not None and _REVISION.fullmatch(self.code_revision) is None:
            raise ValueError("code_revision must be a lowercase 7-64 character hexadecimal SHA")

    def to_mapping(self) -> dict[str, object]:
        return {
            "prices_path": _path_text(self.prices_path),
            "manifest_path": _path_text(self.manifest_path),
            "output_dir": _path_text(self.output_dir),
            "code_revision": self.code_revision,
            "mlflow_enabled": False,
        }

    def command(self, python_executable: Path) -> tuple[str, ...]:
        values = [
            str(python_executable),
            "-m",
            "quantops_ml",
            "run",
            "--prices",
            str(self.prices_path),
            "--manifest",
            str(self.manifest_path),
            "--output",
            str(self.output_dir),
        ]
        if self.code_revision is not None:
            values.extend(("--code-revision", self.code_revision))
        return tuple(values)


@dataclass(frozen=True, slots=True)
class AiEvaluationConfig:
    cases_path: Path
    output_path: Path | None = None

    def __post_init__(self) -> None:
        _path_text(self.cases_path)
        if self.output_path is not None:
            _path_text(self.output_path)

    def to_mapping(self) -> dict[str, object]:
        return {
            "cases_path": _path_text(self.cases_path),
            "output_path": None if self.output_path is None else _path_text(self.output_path),
        }

    def command(self, python_executable: Path) -> tuple[str, ...]:
        values = [
            str(python_executable),
            "-m",
            "quantops_ai",
            "evaluate",
            "--cases",
            str(self.cases_path),
        ]
        if self.output_path is not None:
            values.extend(("--output", str(self.output_path)))
        return tuple(values)
