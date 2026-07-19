"""Bounded deterministic replay that respects per-partition commit barriers."""

from __future__ import annotations

from collections.abc import Sequence

from quantops_stream_worker.consumer import EventConsumer
from quantops_stream_worker.models import BrokerRecord, DeliveryResult, DeliveryStatus

_BLOCKING = {DeliveryStatus.RETRY_EXHAUSTED, DeliveryStatus.COMMIT_DEFERRED}


class ReplayService:
    def __init__(self, consumer: EventConsumer) -> None:
        self._consumer = consumer

    async def replay(self, records: Sequence[BrokerRecord]) -> tuple[DeliveryResult, ...]:
        ordered = tuple(sorted(records, key=lambda item: item.coordinate))
        coordinates = tuple(item.coordinate for item in ordered)
        if len(set(coordinates)) != len(coordinates):
            raise ValueError("replay input contains a duplicate broker coordinate")
        blocked: set[tuple[str, int]] = set()
        results: list[DeliveryResult] = []
        for record in ordered:
            partition = (record.topic, record.partition)
            if partition in blocked:
                results.append(DeliveryResult(record.coordinate, DeliveryStatus.PARTITION_BLOCKED))
                continue
            result = await self._consumer.consume(record)
            results.append(result)
            if result.status in _BLOCKING:
                blocked.add(partition)
        return tuple(results)
