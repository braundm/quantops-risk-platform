"""Deterministic repository hygiene and high-confidence secret-pattern scan."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

MAXIMUM_FILE_BYTES = 1_048_576
EXCLUDED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".terraform",
    ".uv-cache",
    ".venv",
    "dist",
    "htmlcov",
    "node_modules",
    "playwright-report",
    "test-results",
}
FALLBACK_EXCLUDED_FILES = {".env"}
DISALLOWED_FILENAMES = {".env", "credentials.json"}
ALLOWED_LARGE_FILES = {"data/synthetic/canonical/price_bars.json"}
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_fine_grained_token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    ("github_classic_token", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("openai_style_token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
)


@dataclass(frozen=True, slots=True, order=True)
class Finding:
    """One deterministic repository scan finding."""

    path: str
    line: int
    code: str

    def render(self) -> str:
        location = self.path if self.line == 0 else f"{self.path}:{self.line}"
        return f"{location}: {self.code}"


def tracked_files(root: Path) -> tuple[Path, ...]:
    """Return tracked files, with a safe filesystem fallback when Git is unavailable."""

    git = shutil.which("git")
    if git is not None and (root / ".git").exists():
        result = subprocess.run(  # noqa: S603
            [git, "ls-files", "-z"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if result.returncode == 0:
            return tuple(
                root / entry.decode("utf-8") for entry in result.stdout.split(b"\0") if entry
            )
    return tuple(
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.name not in FALLBACK_EXCLUDED_FILES
        and not EXCLUDED_DIRECTORIES.intersection(path.relative_to(root).parts)
    )


def scan_file(path: Path, root: Path) -> tuple[Finding, ...]:
    """Scan one file without ever rendering matched secret material."""

    relative = path.relative_to(root).as_posix()
    findings: list[Finding] = []
    if path.name.casefold() in DISALLOWED_FILENAMES:
        findings.append(Finding(relative, 0, "disallowed_sensitive_filename"))
    size = path.stat().st_size
    if size > MAXIMUM_FILE_BYTES and relative not in ALLOWED_LARGE_FILES:
        findings.append(Finding(relative, 0, f"file_exceeds_{MAXIMUM_FILE_BYTES}_bytes"))
        return tuple(findings)
    content = path.read_bytes()
    if b"\0" in content:
        return tuple(findings)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return tuple(findings)
    for line_number, line in enumerate(text.splitlines(), start=1):
        for code, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(Finding(relative, line_number, code))
    return tuple(findings)


def scan_paths(paths: Iterable[Path], root: Path) -> tuple[Finding, ...]:
    """Scan paths and return stable, deduplicated findings."""

    findings = {finding for path in paths if path.is_file() for finding in scan_file(path, root)}
    return tuple(sorted(findings))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    findings = scan_paths(tracked_files(root), root)
    if findings:
        for finding in findings:
            print(finding.render())
        return 1
    print("Repository security scan passed: no high-confidence secret or hygiene findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
