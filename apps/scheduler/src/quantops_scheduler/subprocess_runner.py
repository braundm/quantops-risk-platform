"""Bounded, cancellation-aware subprocess execution without shell expansion."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from quantops_scheduler.errors import OutputLimitError, SchedulerUnavailableError
from quantops_scheduler.models import CommandResult


class SubprocessCommandRunner:
    def __init__(self, *, max_output_bytes: int = 1_048_576, terminate_grace: float = 2.0) -> None:
        if max_output_bytes < 1:
            raise ValueError("max_output_bytes must be positive")
        if terminate_grace <= 0:
            raise ValueError("terminate_grace must be positive")
        self._max_output_bytes = max_output_bytes
        self._terminate_grace = terminate_grace

    async def run(self, command: tuple[str, ...]) -> CommandResult:
        if not command or any(not argument for argument in command):
            raise ValueError("command must contain non-empty arguments")
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, OSError) as error:
            raise SchedulerUnavailableError from error

        if process.stdout is None or process.stderr is None:
            await self._stop(process)
            raise SchedulerUnavailableError
        try:
            stdout, stderr = await self._collect(process.stdout, process.stderr)
            await process.wait()
        except asyncio.CancelledError:
            await self._stop(process)
            raise
        except OutputLimitError:
            await self._stop(process)
            raise
        return CommandResult(
            return_code=process.returncode or 0,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
        )

    async def _collect(
        self,
        stdout: asyncio.StreamReader,
        stderr: asyncio.StreamReader,
    ) -> tuple[bytes, bytes]:
        total = 0

        async def read_stream(stream: asyncio.StreamReader) -> bytes:
            nonlocal total
            chunks: list[bytes] = []
            while chunk := await stream.read(65_536):
                total += len(chunk)
                if total > self._max_output_bytes:
                    raise OutputLimitError
                chunks.append(chunk)
            return b"".join(chunks)

        stdout_task = asyncio.create_task(read_stream(stdout))
        stderr_task = asyncio.create_task(read_stream(stderr))
        try:
            return await asyncio.gather(stdout_task, stderr_task)
        finally:
            for task in (stdout_task, stderr_task):
                if not task.done():
                    task.cancel()
            for task in (stdout_task, stderr_task):
                with suppress(asyncio.CancelledError, OutputLimitError):
                    await task

    async def _stop(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        with suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=self._terminate_grace)
        except TimeoutError:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()
