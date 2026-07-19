"""Command-line interface for deterministic generation and verification."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from quantops_pipelines.generator import generate_dataset, load_config, verify_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quantops-data",
        description="Generate and verify the offline QuantOps synthetic dataset.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="Generate canonical and quality artifacts.")
    generate.add_argument(
        "--config",
        type=Path,
        default=Path("data/synthetic/generator_config.json"),
        help="Path to deterministic JSON generator configuration.",
    )
    generate.add_argument(
        "--output",
        type=Path,
        default=Path("data/synthetic"),
        help="Dataset output directory.",
    )

    verify = commands.add_parser("verify", help="Verify the dataset manifest and SHA-256 hashes.")
    verify.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/synthetic"),
        help="Generated dataset directory.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        config = load_config(args.config)
        result = generate_dataset(config, args.output)
        sys.stdout.write(json.dumps(result.to_mapping(), sort_keys=True) + "\n")
        return 0
    if args.command == "verify":
        errors = verify_dataset(args.dataset)
        if errors:
            sys.stderr.write(json.dumps({"status": "invalid", "errors": errors}) + "\n")
            return 1
        sys.stdout.write(json.dumps({"status": "valid", "dataset": str(args.dataset)}) + "\n")
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")
