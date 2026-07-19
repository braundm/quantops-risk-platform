"""Bounded parsing of existing CLI summary contracts into scheduler counts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

from quantops_scheduler.errors import InvalidJobOutputError
from quantops_scheduler.models import JobName, ParsedJobOutput, RunCounts


def parse_job_output(name: JobName, stdout: str) -> ParsedJobOutput:
    lines = tuple(line for line in stdout.splitlines() if line.strip())
    if not lines:
        raise InvalidJobOutputError
    try:
        raw: object = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise InvalidJobOutputError from error
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise InvalidJobOutputError
    summary = cast(dict[str, Any], raw)
    counts = _counts(name, summary)
    canonical = json.dumps(
        summary,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return ParsedJobOutput(
        counts=counts,
        summary=summary,
        sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


def _counts(name: JobName, summary: dict[str, Any]) -> RunCounts:
    if name is JobName.GENERATE_DEMO_DATASET:
        return RunCounts(
            processed=_integer(summary, "price_bar_count"),
            succeeded=_integer(summary, "quality_accepted_count"),
            failed=_integer(summary, "quality_quarantined_count"),
            artifacts_written=_integer(summary, "files_written"),
        )
    if name is JobName.VERIFY_DEMO_DATASET:
        if summary.get("status") != "valid":
            raise InvalidJobOutputError
        return RunCounts(processed=1, succeeded=1)
    if name is JobName.RUN_ML_LIFECYCLE:
        artifacts = summary.get("artifacts")
        if not isinstance(artifacts, dict):
            raise InvalidJobOutputError
        return RunCounts(
            processed=_integer(summary, "feature_rows"),
            succeeded=1,
            artifacts_written=_integer(cast(dict[str, Any], artifacts), "files_written"),
        )
    processed = _integer(summary, "case_count")
    passed = _integer(summary, "passed")
    failed = _integer(summary, "failed")
    if passed + failed != processed:
        raise InvalidJobOutputError
    return RunCounts(
        processed=processed,
        succeeded=passed,
        failed=failed,
        artifacts_written=1 if summary.get("report_path") is not None else 0,
    )


def _integer(value: dict[str, Any], key: str) -> int:
    result = value.get(key)
    if isinstance(result, bool) or not isinstance(result, int) or result < 0:
        raise InvalidJobOutputError
    return result
