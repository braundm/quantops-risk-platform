"""Command-line interface for the versioned deterministic AI evaluation suite."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from quantops_ai.evaluator import default_cases_path, load_evaluation_cases, run_evaluation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quantops-ai", description="Evaluate grounded AI safety.")
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("evaluate", help="Run versioned deterministic AI evaluations.")
    evaluate.add_argument("--cases", type=Path, default=default_cases_path())
    evaluate.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "evaluate":
        raise AssertionError(f"unsupported command: {args.command}")
    report = run_evaluation(load_evaluation_cases(args.cases))
    rendered = json.dumps(report.to_mapping(), indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(f".{args.output.name}.tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(args.output)
    sys.stdout.write(
        json.dumps(
            {
                "case_count": report.case_count,
                "passed": report.passed,
                "failed": report.failed,
                "report_path": None if args.output is None else str(args.output),
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0 if report.failed == 0 else 1
