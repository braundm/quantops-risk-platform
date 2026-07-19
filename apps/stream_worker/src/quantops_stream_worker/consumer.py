"""Deterministic at-least-once consumer with bounded policy and safe failures."""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import ValidationError
from quantops_contracts import (
    EventContractError,
    EventEnvelope,
    MalformedEventError,
    MessageTooLargeError,
    UnsupportedEventTypeError,
    UnsupportedVersionError,
    parse_event_json,
)

from quantops_stream_worker.config import WorkerConfig
from quantops_stream_worker.errors import (
    BrokerUnavailableError,
    PermanentProcessingError,
)
from quantops_stream_worker.metrics import WorkerMetrics
from quantops_stream_worker.models import (
    BrokerRecord,
    DeadLetterRecord,
    DeliveryResult,
    DeliveryStatus,
    IdempotencyDisposition,
)
from quantops_stream_worker.ports import (
    DeadLetterSink,
    DurableEventProcessor,
    OffsetCommitter,
)

_NAMESPACE = uuid5(NAMESPACE_URL, "https://quantops.dev/stream-worker/dead-letter/v1")


@dataclass(frozen=True, slots=True)
class _Attempt[ResultT]:
    value: ResultT | None
    error: Exception | None
    attempts: int
    delays_ms: tuple[int, ...]


class EventConsumer:
    """Consumes one broker record without depending on a Kafka client or database."""

    def __init__(
        self,
        *,
        processor: DurableEventProcessor,
        dead_letters: DeadLetterSink,
        committer: OffsetCommitter,
        config: WorkerConfig,
        metrics: WorkerMetrics | None = None,
    ) -> None:
        self._processor = processor
        self._dead_letters = dead_letters
        self._committer = committer
        self._config = config
        self.metrics = metrics or WorkerMetrics()
        self._watermarks: dict[tuple[str, int], datetime] = {}

    @property
    def watermarks(self) -> dict[tuple[str, int], datetime]:
        return dict(self._watermarks)

    async def consume(self, record: BrokerRecord) -> DeliveryResult:
        try:
            envelope = parse_event_json(record.value)
        except (EventContractError, ValidationError) as error:
            return await self._reject(
                record,
                envelope=None,
                failure_code=_contract_code(error),
                failure_kind="contract",
                processing_attempts=1,
                delays=(),
            )

        expected_topic = self._config.topics.for_event(envelope.event_type)
        if record.topic != expected_topic:
            return await self._reject(
                record,
                envelope=envelope,
                failure_code="event_topic_mismatch",
                failure_kind="policy",
                processing_attempts=1,
                delays=(),
            )

        inspection = await self._attempt(lambda: self._processor.inspect(envelope))
        if inspection.error is not None:
            if isinstance(inspection.error, PermanentProcessingError):
                return await self._reject(
                    record,
                    envelope=envelope,
                    failure_code=inspection.error.code,
                    failure_kind="permanent",
                    processing_attempts=inspection.attempts,
                    delays=inspection.delays_ms,
                )
            return DeliveryResult(
                record.coordinate,
                DeliveryStatus.RETRY_EXHAUSTED,
                envelope.event_id,
                inspection.attempts,
                inspection.delays_ms,
            )
        disposition = cast(IdempotencyDisposition, inspection.value)
        if disposition is IdempotencyDisposition.CONFLICT:
            return await self._reject(
                record,
                envelope=envelope,
                failure_code="idempotency_conflict",
                failure_kind="permanent",
                processing_attempts=inspection.attempts,
                delays=inspection.delays_ms,
            )
        if disposition is IdempotencyDisposition.DUPLICATE:
            self.metrics.duplicates += 1
            return await self._commit_result(
                record,
                DeliveryStatus.DUPLICATE,
                envelope.event_id,
                inspection.attempts,
                inspection.delays_ms,
            )

        policy_code, is_late = self._lateness(record, envelope)
        if policy_code is not None:
            return await self._reject(
                record,
                envelope=envelope,
                failure_code=policy_code,
                failure_kind="policy",
                processing_attempts=inspection.attempts,
                delays=inspection.delays_ms,
            )

        processing = await self._attempt(lambda: self._processor.process(envelope, late=is_late))
        combined_delays = inspection.delays_ms + processing.delays_ms
        combined_attempts = inspection.attempts + processing.attempts
        if processing.error is not None:
            if isinstance(processing.error, PermanentProcessingError):
                return await self._reject(
                    record,
                    envelope=envelope,
                    failure_code=processing.error.code,
                    failure_kind="permanent",
                    processing_attempts=combined_attempts,
                    delays=combined_delays,
                )
            return DeliveryResult(
                record.coordinate,
                DeliveryStatus.RETRY_EXHAUSTED,
                envelope.event_id,
                combined_attempts,
                combined_delays,
            )
        final_disposition = cast(IdempotencyDisposition, processing.value)
        if final_disposition is IdempotencyDisposition.CONFLICT:
            return await self._reject(
                record,
                envelope=envelope,
                failure_code="idempotency_conflict",
                failure_kind="permanent",
                processing_attempts=combined_attempts,
                delays=combined_delays,
            )
        if final_disposition is IdempotencyDisposition.DUPLICATE:
            self.metrics.duplicates += 1
            return await self._commit_result(
                record,
                DeliveryStatus.DUPLICATE,
                envelope.event_id,
                combined_attempts,
                combined_delays,
            )

        self.metrics.processed += 1
        if is_late:
            self.metrics.late += 1
        watermark_key = (record.topic, record.partition)
        previous = self._watermarks.get(watermark_key)
        if previous is None or envelope.occurred_at > previous:
            self._watermarks[watermark_key] = envelope.occurred_at
        status = DeliveryStatus.PROCESSED_LATE if is_late else DeliveryStatus.PROCESSED
        return await self._commit_result(
            record,
            status,
            envelope.event_id,
            combined_attempts,
            combined_delays,
        )

    def _lateness(
        self,
        record: BrokerRecord,
        envelope: EventEnvelope,
    ) -> tuple[str | None, bool]:
        if envelope.occurred_at > record.received_at:
            return "future_event", False
        if record.received_at - envelope.occurred_at > self._config.max_event_age:
            return "event_too_old", False
        watermark = self._watermarks.get((record.topic, record.partition))
        if watermark is None or envelope.occurred_at >= watermark:
            return None, False
        if watermark - envelope.occurred_at > self._config.max_out_of_order:
            return "late_beyond_policy", False
        return None, True

    async def _attempt[ResultT](
        self,
        operation: Callable[[], Awaitable[ResultT]],
    ) -> _Attempt[ResultT]:
        delays: list[int] = []
        for attempt_number in range(1, self._config.retry.max_attempts + 1):
            try:
                return _Attempt(await operation(), None, attempt_number, tuple(delays))
            except PermanentProcessingError as error:
                return _Attempt(None, error, attempt_number, tuple(delays))
            except Exception as error:  # Unknown infrastructure failures default to retryable.
                if isinstance(error, BrokerUnavailableError):
                    self.metrics.broker_outages += 1
                if attempt_number >= self._config.retry.max_attempts:
                    return _Attempt(None, error, attempt_number, tuple(delays))
                delay = self._config.retry.delay_ms(attempt_number)
                delays.append(delay)
                self.metrics.retries += 1
        raise AssertionError("bounded retry loop did not return")

    async def _reject(
        self,
        record: BrokerRecord,
        *,
        envelope: EventEnvelope | None,
        failure_code: str,
        failure_kind: str,
        processing_attempts: int,
        delays: tuple[int, ...],
    ) -> DeliveryResult:
        dead_letter = _dead_letter(
            record,
            envelope=envelope,
            failure_code=failure_code,
            failure_kind=failure_kind,
            attempts=processing_attempts,
        )
        stored = await self._attempt(lambda: self._dead_letters.put(dead_letter))
        all_delays = delays + stored.delays_ms
        all_attempts = processing_attempts + stored.attempts
        if stored.error is not None:
            return DeliveryResult(
                record.coordinate,
                DeliveryStatus.RETRY_EXHAUSTED,
                envelope.event_id if envelope is not None else None,
                all_attempts,
                all_delays,
            )
        self.metrics.rejected += 1
        self.metrics.dead_lettered += 1
        return await self._commit_result(
            record,
            DeliveryStatus.REJECTED_DEAD_LETTERED,
            envelope.event_id if envelope is not None else None,
            all_attempts,
            all_delays,
        )

    async def _commit_result(
        self,
        record: BrokerRecord,
        success_status: DeliveryStatus,
        event_id: UUID | None,
        attempts: int,
        delays: tuple[int, ...],
    ) -> DeliveryResult:
        committed = await self._attempt(lambda: self._committer.commit(record))
        all_delays = delays + committed.delays_ms
        all_attempts = attempts + committed.attempts
        if committed.error is not None:
            return DeliveryResult(
                record.coordinate,
                DeliveryStatus.COMMIT_DEFERRED,
                event_id,
                all_attempts,
                all_delays,
            )
        self.metrics.commits += 1
        return DeliveryResult(
            record.coordinate,
            success_status,
            event_id,
            all_attempts,
            all_delays,
        )


def _contract_code(error: EventContractError | ValidationError) -> str:
    if isinstance(error, MessageTooLargeError):
        return "message_too_large"
    if isinstance(error, MalformedEventError):
        return "malformed_event"
    if isinstance(error, UnsupportedVersionError):
        return "unsupported_schema_version"
    if isinstance(error, UnsupportedEventTypeError):
        return "unsupported_event_type"
    return "invalid_event_contract"


def _dead_letter(
    record: BrokerRecord,
    *,
    envelope: EventEnvelope | None,
    failure_code: str,
    failure_kind: str,
    attempts: int,
) -> DeadLetterRecord:
    source_hash = hashlib.sha256(record.value).hexdigest()
    idempotency_hash = None
    if envelope is not None and envelope.idempotency_key is not None:
        idempotency_hash = hashlib.sha256(envelope.idempotency_key.encode("utf-8")).hexdigest()
    identity = f"{record.topic}:{record.partition}:{record.offset}:{source_hash}:{failure_code}"
    return DeadLetterRecord(
        id=uuid5(_NAMESPACE, identity),
        source_topic=record.topic,
        source_partition=record.partition,
        source_offset=record.offset,
        source_sha256=source_hash,
        source_size_bytes=len(record.value),
        failure_code=failure_code,
        failure_kind=failure_kind,
        created_at=record.received_at,
        attempts=max(1, attempts),
        event_id=envelope.event_id if envelope is not None else None,
        idempotency_key_sha256=idempotency_hash,
    )
