from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from scripts import typecheck


def test_every_group_uses_strict_mode_and_an_isolated_cache() -> None:
    names = [group.name for group in typecheck.GROUPS]

    assert len(names) == len(set(names))
    for group in typecheck.GROUPS:
        command = typecheck.command_for(group, python="python")
        assert command[:4] == ("python", "-m", "mypy", "--strict")
        assert command[command.index("--config-file") + 1] == group.config
        assert command[command.index("--cache-dir") + 1].endswith(f"/{group.name}")


def test_selected_groups_preserve_order_and_remove_duplicates() -> None:
    selected = typecheck.selected_groups(("ai", "domain", "ai"))

    assert tuple(group.name for group in selected) == ("ai", "domain")


def test_runner_stops_after_the_first_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Sequence[str]] = []

    def fake_run(
        command: Sequence[str], *, cwd: Path, check: bool
    ) -> subprocess.CompletedProcess[str]:
        del cwd, check
        calls.append(command)
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = typecheck.run_typechecks(typecheck.GROUPS[:2], root=tmp_path)

    assert result == 7
    assert len(calls) == 1
