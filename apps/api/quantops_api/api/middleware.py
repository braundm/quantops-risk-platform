"""Request identity, safe access logging, and demo rate limiting."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from threading import Lock
from uuid import UUID, uuid4

from fastapi import Request, Response

from quantops_api.application.errors import RateLimitError

logger = logging.getLogger("quantops_api.access")


def _normalized_uuid(value: str | None) -> str:
    if value is not None:
        try:
            return str(UUID(value))
        except ValueError:
            pass
    return str(uuid4())


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Install IDs and emit an access event containing only bounded safe fields."""

    request_id = _normalized_uuid(request.headers.get("X-Request-ID"))
    correlation_id = _normalized_uuid(request.headers.get("X-Correlation-ID"))
    request.state.request_id = request_id
    request.state.correlation_id = correlation_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Correlation-ID"] = correlation_id
    logger.info(
        "request_complete",
        extra={
            "request_id": request_id,
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    )
    return response


class FixedWindowRateLimiter:
    """Thread-safe in-memory limiter for the single-process demo boundary."""

    def __init__(self, *, capacity: int, window_seconds: int) -> None:
        self._capacity = capacity
        self._window_seconds = window_seconds
        self._events: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, identity: str) -> None:
        now = time.monotonic()
        boundary = now - self._window_seconds
        with self._lock:
            events = self._events[identity]
            while events and events[0] <= boundary:
                events.popleft()
            if len(events) >= self._capacity:
                retry_after = max(1, int(self._window_seconds - (now - events[0])) + 1)
                raise RateLimitError(
                    "the demo limit for this expensive operation has been reached",
                    retry_after=retry_after,
                )
            events.append(now)
