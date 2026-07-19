"""CLI for the deterministic offline risk-regime lifecycle."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from quantops_ml.lifecycle import run_lifecycle

_GIT_REVISION = re.compile(r"^[0-9a-f]{7,64}$")


def _default_code_revision() -> str:
    github_revision = os.environ.get("GITHUB_SHA", "").lower()
    if _GIT_REVISION.fullmatch(github_revision):
        return github_revision
    return "not_recorded_git_cli_unavailable"


def _parse_code_revision(value: str) -> str:
    revision = value.lower()
    if not _GIT_REVISION.fullmatch(revision):
        raise argparse.ArgumentTypeError("code revision must be a 7-64 character hexadecimal SHA")
    return revision


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quantops-ml",
        description="Run deterministic synthetic risk-regime lifecycle artifacts.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Build features, evaluate, gate, and monitor drift.")
    run.add_argument(
        "--prices",
        type=Path,
        default=Path("data/synthetic/canonical/price_bars.csv"),
    )
    run.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/synthetic/manifest.json"),
    )
    run.add_argument("--output", type=Path, default=Path("ml/artifacts/demo"))
    run.add_argument("--enable-mlflow", action="store_true")
    run.add_argument("--mlflow-tracking-uri")
    run.add_argument(
        "--code-revision",
        type=_parse_code_revision,
        help="Git commit SHA recorded in reproducibility artifacts (defaults to GITHUB_SHA).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "run":
        raise AssertionError(f"unhandled command: {args.command}")
    result = run_lifecycle(
        args.prices,
        args.manifest,
        args.output,
        enable_mlflow=args.enable_mlflow,
        mlflow_tracking_uri=args.mlflow_tracking_uri,
        code_revision=args.code_revision or _default_code_revision(),
    )
    sys.stdout.write(json.dumps(result.to_mapping(), sort_keys=True) + "\n")
    return 0
