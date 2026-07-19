"""Real local subprocess boundary tests; no network or external service is used."""

from __future__ import annotations

import asyncio
import sys

import pytest

from quantops_scheduler.errors import OutputLimitError, SchedulerUnavailableError
from quantops_scheduler.subprocess_runner import SubprocessCommandRunner


def test_subprocess_runner_captures_utf8_without_shell() -> None:
    runner = SubprocessCommandRunner()

    result = asyncio.run(runner.run((sys.executable, "-c", 'print("scheduler-ok")')))

    assert result.return_code == 0
    assert result.stdout.strip() == "scheduler-ok"
    assert result.stderr == ""


def test_subprocess_runner_enforces_combined_output_limit() -> None:
    runner = SubprocessCommandRunner(max_output_bytes=32)

    with pytest.raises(OutputLimitError):
        asyncio.run(
            runner.run(
                (
                    sys.executable,
                    "-c",
                    'import sys; sys.stdout.write("x" * 128)',
                )
            )
        )


def test_missing_executable_is_scheduler_unavailable() -> None:
    runner = SubprocessCommandRunner()

    with pytest.raises(SchedulerUnavailableError):
        asyncio.run(runner.run(("quantops-command-that-does-not-exist-7f81",)))


def test_cancellation_terminates_sleeping_child() -> None:
    async def scenario() -> None:
        runner = SubprocessCommandRunner(terminate_grace=0.25)
        task = asyncio.create_task(
            runner.run(
                (
                    sys.executable,
                    "-c",
                    "import time; time.sleep(30)",
                )
            )
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
