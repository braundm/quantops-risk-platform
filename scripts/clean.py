"""Remove only bounded, project-generated development artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov"}
TARGET_PATHS = {ROOT / "coverage.xml", ROOT / ".coverage"}


def main() -> int:
    """Delete known recoverable outputs while preserving source and fixture inputs."""

    removed: list[Path] = []
    for candidate in ROOT.rglob("*"):
        if candidate.is_dir() and candidate.name in TARGET_NAMES:
            shutil.rmtree(candidate)
            removed.append(candidate)
    for candidate in TARGET_PATHS:
        if candidate.is_file():
            candidate.unlink()
            removed.append(candidate)
    print(f"Removed {len(removed)} generated paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
