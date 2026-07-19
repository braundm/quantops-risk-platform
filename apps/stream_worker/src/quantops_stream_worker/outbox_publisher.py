"""Transactional-outbox publisher with validated envelopes and bounded backoff."""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import ValidationError
from quantops_contracts import EventContractError, parse_event_mapping
from quantops_domain import OutboxEvent, OutboxStatus

from quantops_stream_worker.config import WorkerConfig
from quantops_stream_worker.errors import BrokerUnavailableError
from quantops_stream_worker.metrics import WorkerMetrics
from quantops_stream_worker.models import (
    OutboxPublishResult,
    OutboxPublishStatus,
    Publication,
)
from quantops_stream_worker.ports import BrokerPublisher, OutboxRepository


class OutboxPublisher:
    """Publishes only contract-valid outbox records and persists every transition."""

    def __init__(
        self,
        *,
        repository: OutboxRepository,
        broker: BrokerPublisher,
        config: WorkerConfig,
        metrics: WorkerMetrics | None = None,
    ) -> None:
        self._repository = repository
        self._broker = broker
        self._config = config
        self.metrics = metrics or WorkerMetrics()

    async def publish_available(self, *, at: datetime) -> tuple[OutboxPublishResult, ...]:
        events = await self._repository.claim_available(
            at=at,
            limit=self._config.batch_size,
            worker_id=self._config.worker_id,
        )
        results: list[OutboxPublishResult] = []
        for event in events:
            results.append(await self._publish_one(event, at=at))
        return tuple(results)

    async def _publish_one(
        self,
        event: OutboxEvent,
        *,
        at: datetime,
    ) -> OutboxPublishResult:
        try:
            raw = dict(event.event_envelope)
            raw["received_at"] = at
            envelope = parse_event_mapping(raw)
        except (EventContractError, ValidationError, ValueError, TypeError):
            terminal = event.record_failure(
                error_summary="permanent:invalid_outbox_contract",
                max_attempts=1,
            )
            await self._repository.save(terminal)
            self.metrics.rejected += 1
            self.metrics.dead_lettered += 1
            return OutboxPublishResult(
                terminal.id,
                OutboxPublishStatus.DEAD_LETTERED,
                terminal.attempts,
            )

        key = envelope.idempotency_key
        if key is None:
            raise RuntimeError("validated outbox envelope has no idempotency key")
        publication = Publication(
            topic=self._config.topics.for_event(envelope.event_type),
            key=key.encode("utf-8"),
            value=envelope.to_canonical_bytes(),
            published_at=at,
            headers={
                "event_id": str(envelope.event_id).encode("ascii"),
                "correlation_id": str(envelope.correlation_id).encode("ascii"),
                "schema_version": str(envelope.schema_version).encode("ascii"),
            },
        )
        try:
            await self._broker.publish(publication)
        except Exception as error:
            if isinstance(error, BrokerUnavailableError):
                self.metrics.broker_outages += 1
                code = "broker_unavailable"
            else:
                code = "publish_failure"
            return await self._record_transient_failure(event, at=at, code=code)

        published = event.mark_published(published_at=at)
        await self._repository.save(published)
        self.metrics.processed += 1
        return OutboxPublishResult(
            published.id,
            OutboxPublishStatus.PUBLISHED,
            published.attempts,
        )

    async def _record_transient_failure(
        self,
        event: OutboxEvent,
        *,
        at: datetime,
        code: str,
    ) -> OutboxPublishResult:
        next_attempt = event.attempts + 1
        retry_at = None
        if next_attempt < self._config.retry.max_attempts:
            retry_at = at + timedelta(milliseconds=self._config.retry.delay_ms(next_attempt))
        failed = event.record_failure(
            error_summary=f"transient:{code}",
            max_attempts=self._config.retry.max_attempts,
            retry_at=retry_at,
        )
        await self._repository.save(failed)
        if failed.status is OutboxStatus.DEAD_LETTER:
            self.metrics.rejected += 1
            self.metrics.dead_lettered += 1
            return OutboxPublishResult(
                failed.id,
                OutboxPublishStatus.DEAD_LETTERED,
                failed.attempts,
            )
        self.metrics.retries += 1
        return OutboxPublishResult(
            failed.id,
            OutboxPublishStatus.RETRY_SCHEDULED,
            failed.attempts,
            failed.available_at,
        )
