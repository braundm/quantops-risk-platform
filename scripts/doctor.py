"""Cross-platform, read-only QuantOps toolchain diagnostics."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    command: tuple[str, ...]
    required_for_core: bool
    purpose: str


TOOLS = (
    Tool("Python", (sys.executable, "--version"), True, "backend and numerical packages"),
    Tool("uv", ("uv", "--version"), True, "locked Python workspace"),
    Tool("Node", ("node", "--version"), True, "dashboard build"),
    Tool("pnpm", ("pnpm", "--version"), True, "locked JavaScript workspace"),
    Tool("Git", ("git", "--version"), True, "source history"),
    Tool("Docker", ("docker", "--version"), False, "PostgreSQL and optional profiles"),
    Tool("GitHub CLI", ("gh", "--version"), False, "final publication only"),
    Tool("Terraform", ("terraform", "version"), False, "optional P2 validation"),
)


def probe(tool: Tool) -> tuple[bool, str]:
    """Return availability and a single-line version summary."""

    executable = tool.command[0]
    if not (executable == sys.executable or shutil.which(executable)):
        return False, "not found on PATH"
    try:
        result = subprocess.run(  # noqa: S603
            tool.command,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"probe failed: {type(exc).__name__}"
    output = (result.stdout or result.stderr).strip().splitlines()
    return result.returncode == 0, output[0] if output else f"exit {result.returncode}"


def main() -> int:
    """Print actionable diagnostics without mutating the workstation."""

    print(f"QuantOps doctor on {platform.system()} {platform.release()}")
    missing_core: list[str] = []
    for tool in TOOLS:
        available, detail = probe(tool)
        state = "OK" if available else "MISSING"
        requirement = "core" if tool.required_for_core else "optional"
        print(f"[{state:7}] {tool.name:12} ({requirement}): {detail} — {tool.purpose}")
        if tool.required_for_core and not available:
            missing_core.append(tool.name)

    if missing_core:
        print(
            "\nInstall missing core tools from their official distributions: "
            + ", ".join(missing_core)
        )
        return 1
    print(
        "\nCore toolchain is available. Docker is required for integration tests and the full demo."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
