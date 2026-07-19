"""Deterministic content-addressed lifecycle artifact persistence."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ArtifactWriteResult:
    artifact_hash: str
    files_written: int
    files_unchanged: int
    manifest_path: Path

    def to_mapping(self) -> dict[str, object]:
        return {
            "artifact_hash": self.artifact_hash,
            "files_written": self.files_written,
            "files_unchanged": self.files_unchanged,
            "manifest_path": str(self.manifest_path),
        }


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            _primitive(value),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def write_lifecycle_artifacts(
    output_dir: Path,
    json_artifacts: Mapping[str, object],
    text_artifacts: Mapping[str, str],
) -> ArtifactWriteResult:
    payloads: dict[str, bytes] = {
        path: canonical_json_bytes(value) for path, value in json_artifacts.items()
    }
    payloads.update({path: text.encode("utf-8") for path, text in text_artifacts.items()})
    metadata = [
        {
            "path": path,
            "bytes": len(payloads[path]),
            "sha256": _sha256(payloads[path]),
        }
        for path in sorted(payloads)
    ]
    artifact_hash = _sha256(
        canonical_json_bytes(
            [{"path": item["path"], "sha256": item["sha256"]} for item in metadata]
        )
    )
    manifest = {
        "artifact_manifest_version": "1.0.0",
        "artifact_hash": artifact_hash,
        "hash_algorithm": "sha256",
        "artifacts": metadata,
        "deterministic": True,
        "wall_clock_metadata_persisted": False,
    }
    payloads["manifest.json"] = canonical_json_bytes(manifest)
    written = 0
    unchanged = 0
    for relative_path in sorted(payloads):
        if _write_if_changed(output_dir / relative_path, payloads[relative_path]):
            written += 1
        else:
            unchanged += 1
    return ArtifactWriteResult(
        artifact_hash=artifact_hash,
        files_written=written,
        files_unchanged=unchanged,
        manifest_path=output_dir / "manifest.json",
    )


def _primitive(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("artifact JSON cannot contain a non-finite float")
        return round(value, 12)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("artifact mappings require string keys")
        return {key: _primitive(value[key]) for key in sorted(value)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_primitive(item) for item in value]
    raise TypeError(f"unsupported artifact value: {type(value).__name__}")


def _write_if_changed(path: Path, content: bytes) -> bool:
    if path.is_file() and path.read_bytes() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return True


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
