"""Typed, deterministic price-bar data-quality validation and quarantine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast
from uuid import NAMESPACE_URL, uuid5

from quantops_pipelines.models import (
    PriceBar,
    RecordParseError,
    RuleCode,
    RuleViolation,
    Severity,
)


@dataclass(frozen=True, slots=True)
class QualityContext:
    """Immutable constraints supplied to every record-level rule."""

    allowed_symbols: frozenset[str]
    allowed_regimes: frozenset[str]
    max_lateness: timedelta


class DataQualityRule(Protocol):
    """Structural interface implemented by deterministic record-level rules."""

    code: RuleCode

    def evaluate(self, bar: PriceBar, context: QualityContext) -> RuleViolation | None:
        """Return one bounded violation or ``None`` when the bar passes."""


@dataclass(frozen=True, slots=True)
class SyntheticMarkerRule:
    code: RuleCode = RuleCode.INVALID_SYNTHETIC_MARKER

    def evaluate(self, bar: PriceBar, context: QualityContext) -> RuleViolation | None:
        del context
        if bar.is_synthetic:
            return None
        return _violation(
            self.code,
            "Record is not marked synthetic.",
            str(bar.is_synthetic).lower(),
            "is_synthetic must be true for the bundled dataset",
        )


@dataclass(frozen=True, slots=True)
class AllowedSymbolRule:
    code: RuleCode = RuleCode.UNKNOWN_SYMBOL

    def evaluate(self, bar: PriceBar, context: QualityContext) -> RuleViolation | None:
        if bar.symbol in context.allowed_symbols:
            return None
        return _violation(
            self.code,
            "Symbol is outside the configured synthetic universe.",
            bar.symbol,
            f"symbol must be one of {sorted(context.allowed_symbols)}",
        )


@dataclass(frozen=True, slots=True)
class AllowedRegimeRule:
    code: RuleCode = RuleCode.UNKNOWN_REGIME

    def evaluate(self, bar: PriceBar, context: QualityContext) -> RuleViolation | None:
        if bar.regime in context.allowed_regimes:
            return None
        return _violation(
            self.code,
            "Regime is not declared in the generator configuration.",
            bar.regime,
            f"regime must be one of {sorted(context.allowed_regimes)}",
        )


@dataclass(frozen=True, slots=True)
class FiniteNumberRule:
    code: RuleCode = RuleCode.NON_FINITE_NUMBER

    def evaluate(self, bar: PriceBar, context: QualityContext) -> RuleViolation | None:
        del context
        values = (bar.open, bar.high, bar.low, bar.close)
        if all(value.is_finite() for value in values):
            return None
        return _violation(
            self.code,
            "OHLC contains a non-finite decimal.",
            ",".join(str(value) for value in values),
            "open, high, low, and close must all be finite",
        )


@dataclass(frozen=True, slots=True)
class PositivePriceRule:
    code: RuleCode = RuleCode.NON_POSITIVE_PRICE

    def evaluate(self, bar: PriceBar, context: QualityContext) -> RuleViolation | None:
        del context
        values = (bar.open, bar.high, bar.low, bar.close)
        try:
            valid = all(value > Decimal(0) for value in values)
        except InvalidOperation:
            return None
        if valid:
            return None
        return _violation(
            self.code,
            "OHLC prices must be strictly positive.",
            ",".join(str(value) for value in values),
            "open, high, low, and close must each be greater than zero",
        )


@dataclass(frozen=True, slots=True)
class OhlcConsistencyRule:
    code: RuleCode = RuleCode.INVALID_OHLC

    def evaluate(self, bar: PriceBar, context: QualityContext) -> RuleViolation | None:
        del context
        try:
            valid = (
                bar.high >= max(bar.open, bar.close)
                and bar.low <= min(bar.open, bar.close)
                and bar.high >= bar.low
            )
        except InvalidOperation:
            return None
        if valid:
            return None
        return _violation(
            self.code,
            "OHLC ordering is inconsistent.",
            f"open={bar.open},high={bar.high},low={bar.low},close={bar.close}",
            "high >= max(open, close) and low <= min(open, close)",
        )


@dataclass(frozen=True, slots=True)
class NonNegativeVolumeRule:
    code: RuleCode = RuleCode.NEGATIVE_VOLUME

    def evaluate(self, bar: PriceBar, context: QualityContext) -> RuleViolation | None:
        del context
        if bar.volume >= 0:
            return None
        return _violation(
            self.code,
            "Volume cannot be negative.",
            str(bar.volume),
            "volume must be greater than or equal to zero",
        )


@dataclass(frozen=True, slots=True)
class TimestampOrderRule:
    code: RuleCode = RuleCode.RECEIVED_BEFORE_EVENT

    def evaluate(self, bar: PriceBar, context: QualityContext) -> RuleViolation | None:
        del context
        if bar.received_at >= bar.timestamp:
            return None
        return _violation(
            self.code,
            "Record was received before its event timestamp.",
            bar.received_at.isoformat(),
            "received_at must be greater than or equal to timestamp",
        )


@dataclass(frozen=True, slots=True)
class LateArrivalRule:
    code: RuleCode = RuleCode.LATE_ARRIVAL

    def evaluate(self, bar: PriceBar, context: QualityContext) -> RuleViolation | None:
        lateness = bar.received_at - bar.timestamp
        if lateness <= context.max_lateness:
            return None
        return _violation(
            self.code,
            "Record arrived after the configured watermark.",
            str(lateness),
            f"received_at - timestamp <= {context.max_lateness}",
            severity=Severity.WARNING,
        )


DEFAULT_RULES = cast(
    tuple[DataQualityRule, ...],
    (
        SyntheticMarkerRule(),
        AllowedSymbolRule(),
        AllowedRegimeRule(),
        FiniteNumberRule(),
        PositivePriceRule(),
        OhlcConsistencyRule(),
        NonNegativeVolumeRule(),
        TimestampOrderRule(),
        LateArrivalRule(),
    ),
)


@dataclass(frozen=True, slots=True)
class QuarantineRecord:
    """A safe reference to rejected input plus bounded rule findings."""

    quarantine_id: str
    case_id: str
    payload_reference: str
    issues: tuple[RuleViolation, ...]
    is_synthetic: bool = True

    def to_mapping(self) -> dict[str, object]:
        return {
            "quarantine_id": self.quarantine_id,
            "case_id": self.case_id,
            "payload_reference": self.payload_reference,
            "rule_codes": [issue.code.value for issue in self.issues],
            "issues": [issue.to_mapping() for issue in self.issues],
            "is_synthetic": self.is_synthetic,
        }


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Deterministic accepted/quarantined split for one staging batch."""

    accepted: tuple[PriceBar, ...]
    quarantined: tuple[QuarantineRecord, ...]
    input_count: int
    expected_count: int

    @property
    def issue_count(self) -> int:
        return sum(len(record.issues) for record in self.quarantined)

    def counts_by_rule(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.quarantined:
            for issue in record.issues:
                counts[issue.code.value] = counts.get(issue.code.value, 0) + 1
        return dict(sorted(counts.items()))


class BatchQualityValidator:
    """Validate records, detect at-least-once duplicates, and identify gaps."""

    def __init__(
        self,
        context: QualityContext,
        rules: Sequence[DataQualityRule] = DEFAULT_RULES,
    ) -> None:
        self._context = context
        self._rules = tuple(rules)

    def validate(
        self,
        records: Sequence[Mapping[str, object]],
        expected_keys: frozenset[tuple[str, str]],
        payload_reference: str,
    ) -> ValidationResult:
        accepted: list[PriceBar] = []
        quarantined: list[QuarantineRecord] = []
        observed_keys: set[tuple[str, str]] = set()
        seen_event_ids: set[str] = set()

        for index, raw in enumerate(records):
            case_id = _case_id(raw, index)
            reference = f"{payload_reference}#/staging_records/{index}"
            raw_key = _raw_key(raw)
            if raw_key is not None:
                observed_keys.add(raw_key)
            try:
                bar = PriceBar.from_mapping(raw)
            except RecordParseError as error:
                quarantined.append(_quarantine(case_id, reference, (error.violation,)))
                continue

            violations: list[RuleViolation] = []
            if bar.source_event_id in seen_event_ids:
                violations.append(
                    _violation(
                        RuleCode.DUPLICATE_EVENT,
                        "Duplicate source event was rejected idempotently.",
                        bar.source_event_id,
                        "source_event_id must be unique within an ingestion run",
                    )
                )
            else:
                seen_event_ids.add(bar.source_event_id)

            violations.extend(
                violation
                for rule in self._rules
                if (violation := rule.evaluate(bar, self._context)) is not None
            )
            if violations:
                quarantined.append(_quarantine(case_id, reference, tuple(violations)))
            else:
                accepted.append(bar)

        for symbol, date_text in sorted(expected_keys - observed_keys):
            case_id = f"missing-{symbol.lower()}-{date_text}"
            issue = _violation(
                RuleCode.MISSING_EXPECTED_BAR,
                "Expected business-day bar is absent from the staging batch.",
                f"{symbol}@{date_text}",
                "one daily bar is required for every configured symbol and business date",
                severity=Severity.WARNING,
            )
            reference = f"{payload_reference}#/expected_gaps/{symbol}/{date_text}"
            quarantined.append(_quarantine(case_id, reference, (issue,)))

        return ValidationResult(
            accepted=tuple(accepted),
            quarantined=tuple(quarantined),
            input_count=len(records),
            expected_count=len(expected_keys),
        )


def _raw_key(raw: Mapping[str, object]) -> tuple[str, str] | None:
    symbol = raw.get("symbol")
    timestamp = raw.get("timestamp")
    if not isinstance(symbol, str) or not isinstance(timestamp, str) or len(timestamp) < 10:
        return None
    return symbol, timestamp[:10]


def _case_id(raw: Mapping[str, object], index: int) -> str:
    candidate = raw.get("case_id")
    if isinstance(candidate, str) and candidate:
        return candidate[:120]
    return f"staging-row-{index}"


def _quarantine(
    case_id: str,
    payload_reference: str,
    issues: tuple[RuleViolation, ...],
) -> QuarantineRecord:
    identity = f"{case_id}|{payload_reference}|{'|'.join(issue.code.value for issue in issues)}"
    return QuarantineRecord(
        quarantine_id=str(uuid5(NAMESPACE_URL, f"quantops:quality:{identity}")),
        case_id=case_id,
        payload_reference=payload_reference,
        issues=issues,
    )


def _violation(
    code: RuleCode,
    message: str,
    observed_value: str,
    expected_constraint: str,
    *,
    severity: Severity = Severity.ERROR,
) -> RuleViolation:
    return RuleViolation(
        code=code,
        severity=severity,
        message=message,
        observed_value=observed_value[:160],
        expected_constraint=expected_constraint,
    )
