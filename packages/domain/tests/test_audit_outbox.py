from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime, timedelta
from uuid import UUID

from quantops_domain import (
    AuditAction,
    AuditEvent,
    DomainValidationError,
    InvalidStateTransitionError,
    OutboxEvent,
    OutboxStatus,
    canonical_json,
)

NOW = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
EVENT_ID = UUID("11111111-1111-4111-8111-111111111111")
AGGREGATE_ID = UUID("22222222-2222-4222-8222-222222222222")
CORRELATION_ID = UUID("33333333-3333-4333-8333-333333333333")


def make_outbox(**overrides: object) -> OutboxEvent:
    arguments: dict[str, object] = {
        "event_id": EVENT_ID,
        "aggregate_type": "Portfolio",
        "aggregate_id": AGGREGATE_ID,
        "event_type": "portfolio.changed",
        "schema_version": 1,
        "producer": "QuantOps-API",
        "idempotency_key": "portfolio:2222:v2",
        "occurred_at": NOW,
        "correlation_id": CORRELATION_ID,
        "payload": {"portfolio_version": 2, "changes": ["name"]},
    }
    arguments.update(overrides)
    return OutboxEvent.pending(**arguments)  # type: ignore[arg-type]


class AuditEventTests(unittest.TestCase):
    def test_audit_details_are_safe_and_deeply_immutable(self) -> None:
        event = AuditEvent.create(
            audit_id=EVENT_ID,
            action=AuditAction.PORTFOLIO_UPDATED,
            aggregate_type="Portfolio",
            aggregate_id=AGGREGATE_ID,
            actor_id="demo-user",
            occurred_at=NOW,
            correlation_id=CORRELATION_ID,
            details={"changed_fields": ["name"]},
        )

        self.assertEqual(event.aggregate_type, "portfolio")
        self.assertEqual(event.details["changed_fields"], ("name",))
        with self.assertRaises(TypeError):
            event.details["extra"] = True  # type: ignore[index]

    def test_audit_rejects_sensitive_keys_at_any_depth(self) -> None:
        for details in (
            {"authorization": "Bearer value"},
            {"nested": {"refreshToken": "value"}},
            {"request": {"user_password_hash": "value"}},
        ):
            with (
                self.subTest(details=details),
                self.assertRaisesRegex(DomainValidationError, "sensitive key"),
            ):
                AuditEvent.create(
                    action=AuditAction.DATA_IMPORTED,
                    aggregate_type="pipeline_run",
                    aggregate_id=AGGREGATE_ID,
                    actor_id="system",
                    occurred_at=NOW,
                    details=details,
                )


class OutboxEventTests(unittest.TestCase):
    def test_pending_event_has_standard_deterministic_envelope(self) -> None:
        event = make_outbox()
        envelope = event.event_envelope

        self.assertEqual(event.status, OutboxStatus.PENDING)
        self.assertEqual(envelope["event_id"], str(EVENT_ID))
        self.assertEqual(envelope["schema_version"], 1)
        self.assertEqual(envelope["occurred_at"], "2026-02-01T09:00:00Z")
        self.assertEqual(envelope["correlation_id"], str(CORRELATION_ID))
        self.assertIsNone(envelope["causation_id"])
        self.assertEqual(json.loads(event.serialized_envelope), envelope)

    def test_payload_and_hash_are_stable_across_mapping_order(self) -> None:
        left = make_outbox(payload={"b": 2, "a": {"z": 1, "x": 3}})
        right = make_outbox(payload={"a": {"x": 3, "z": 1}, "b": 2})

        self.assertEqual(left.payload_hash, right.payload_hash)
        self.assertEqual(left.serialized_envelope, right.serialized_envelope)
        with self.assertRaises(TypeError):
            left.payload["new"] = "value"  # type: ignore[index]

    def test_failure_schedules_a_bounded_retry_then_dead_letters(self) -> None:
        retry_at = NOW + timedelta(seconds=10)
        retry = make_outbox().record_failure(
            error_summary="broker unavailable",
            max_attempts=2,
            retry_at=retry_at,
        )

        self.assertEqual(retry.status, OutboxStatus.RETRY_SCHEDULED)
        self.assertEqual(retry.attempts, 1)
        self.assertFalse(retry.is_available(NOW))
        self.assertTrue(retry.is_available(retry_at))

        terminal = retry.record_failure(
            error_summary="broker still unavailable",
            max_attempts=2,
        )
        self.assertEqual(terminal.status, OutboxStatus.DEAD_LETTER)
        self.assertEqual(terminal.attempts, 2)

    def test_failure_requires_retry_time_while_attempts_remain(self) -> None:
        with self.assertRaisesRegex(DomainValidationError, "retry_at"):
            make_outbox().record_failure(error_summary="temporary", max_attempts=3)

    def test_publish_clears_retry_error_and_counts_successful_attempt(self) -> None:
        retry = make_outbox().record_failure(
            error_summary="temporary",
            max_attempts=3,
            retry_at=NOW + timedelta(seconds=1),
        )
        published = retry.mark_published(published_at=NOW + timedelta(seconds=2))

        self.assertEqual(published.status, OutboxStatus.PUBLISHED)
        self.assertEqual(published.attempts, 2)
        self.assertEqual(published.published_at, NOW + timedelta(seconds=2))
        self.assertIsNone(published.error_summary)

    def test_terminal_events_cannot_transition_again(self) -> None:
        published = make_outbox().mark_published(published_at=NOW)

        with self.assertRaises(InvalidStateTransitionError):
            published.mark_published(published_at=NOW)
        with self.assertRaises(InvalidStateTransitionError):
            published.record_failure(error_summary="too late", max_attempts=3)

    def test_outbox_rejects_secrets_and_invalid_event_names(self) -> None:
        with self.assertRaisesRegex(DomainValidationError, "sensitive key"):
            make_outbox(payload={"apiKey": "never persist me"})
        with self.assertRaisesRegex(DomainValidationError, "dotted event name"):
            make_outbox(event_type="Portfolio Changed")

    def test_canonical_domain_serialization_preserves_decimal_scale_elsewhere(self) -> None:
        self.assertEqual(
            canonical_json({"b": [2, 1], "a": "first"}),
            '{"a":"first","b":[2,1]}',
        )


if __name__ == "__main__":
    unittest.main()
