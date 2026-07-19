"""Run strict mypy checks in isolated repository namespaces.

The workspace contains several independent ``tests`` packages and src-layout
projects.  Passing every root to one mypy process aliases those modules and can
produce false duplicate-module failures.  This orchestrator keeps each package's
configuration and cache isolated while preserving one developer-facing command.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class TypecheckGroup:
    """One independently configured strict mypy invocation."""

    name: str
    config: str
    targets: tuple[str, ...]


GROUPS: tuple[TypecheckGroup, ...] = (
    TypecheckGroup("tooling", "pyproject.toml", ("scripts", "tests")),
    TypecheckGroup(
        "domain",
        "pyproject.toml",
        ("packages/domain/quantops_domain", "packages/domain/tests"),
    ),
    TypecheckGroup(
        "risk",
        "pyproject.toml",
        ("packages/risk_engine/src/quantops_risk", "packages/risk_engine/tests"),
    ),
    TypecheckGroup("api", "pyproject.toml", ("apps/api",)),
    TypecheckGroup(
        "pipelines",
        "pipelines/pyproject.toml",
        ("pipelines/src/quantops_pipelines", "pipelines/tests"),
    ),
    TypecheckGroup(
        "contracts",
        "packages/data_contracts/pyproject.toml",
        ("-p", "quantops_contracts", "-p", "packages.data_contracts.tests"),
    ),
    TypecheckGroup(
        "stream",
        "apps/stream_worker/pyproject.toml",
        ("apps/stream_worker/src", "apps/stream_worker/tests"),
    ),
    TypecheckGroup(
        "scheduler",
        "apps/scheduler/pyproject.toml",
        ("apps/scheduler/src", "apps/scheduler/tests"),
    ),
    TypecheckGroup(
        "ml",
        "ml/pyproject.toml",
        ("-p", "quantops_ml", "-p", "ml.tests"),
    ),
    TypecheckGroup(
        "ai",
        "packages/ai_engine/pyproject.toml",
        ("-p", "quantops_ai", "-p", "packages.ai_engine.tests"),
    ),
    TypecheckGroup(
        "mcp",
        "apps/mcp_server/pyproject.toml",
        ("-p", "quantops_mcp", "-p", "apps.mcp_server.tests"),
    ),
)

GROUP_BY_NAME = {group.name: group for group in GROUPS}


def command_for(group: TypecheckGroup, *, python: str = sys.executable) -> tuple[str, ...]:
    """Build one stable strict command with a namespace-specific cache."""

    return (
        python,
        "-m",
        "mypy",
        "--strict",
        "--config-file",
        group.config,
        "--cache-dir",
        f".mypy_cache/typecheck/{group.name}",
        *group.targets,
    )


def selected_groups(names: Sequence[str] | None) -> tuple[TypecheckGroup, ...]:
    """Return all groups or the requested deduplicated subset in request order."""

    if not names:
        return GROUPS
    return tuple(GROUP_BY_NAME[name] for name in dict.fromkeys(names))


def run_typechecks(groups: Sequence[TypecheckGroup], *, root: Path = ROOT) -> int:
    """Run groups sequentially and stop at the first actionable failure."""

    for group in groups:
        command = command_for(group)
        print(f"[{group.name}] {shlex.join(command)}", flush=True)
        result = subprocess.run(command, cwd=root, check=False)  # noqa: S603
        if result.returncode != 0:
            print(f"Typecheck group '{group.name}' failed with exit {result.returncode}.")
            return result.returncode
    print(f"Strict typechecks passed for {len(groups)} isolated groups.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group",
        action="append",
        choices=tuple(GROUP_BY_NAME),
        help="Run only this group; repeat to select more than one.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the commands without running mypy.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    groups = selected_groups(args.group)
    if args.list:
        for group in groups:
            print(f"[{group.name}] {shlex.join(command_for(group))}")
        return 0
    return run_typechecks(groups)


if __name__ == "__main__":
    raise SystemExit(main())
