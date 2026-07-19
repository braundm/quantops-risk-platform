"""Focused tests for typed price-bar quality rules and safe quarantine."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from quantops_pipelines.generator import generate_price_bars, load_config
from quantops_pipelines.quality import BatchQualityValidator, QualityContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPOSITORY_ROOT / "data" / "synthetic" / "generator_config.json"


def _validator() -> BatchQualityValidator:
    return BatchQualityValidator(
        QualityContext(
            allowed_symbols=frozenset({"QTECH", "QGOLD", "QWTI", "QCASH"}),
            allowed_regimes=frozenset(
                {
                    "normal",
                    "risk_on",
                    "volatility_shock",
                    "correlation_breakdown",
                    "partial_recovery",
                }
            ),
            max_lateness=timedelta(minutes=60),
        )
    )


def test_multiple_typed_rules_can_quarantine_one_parseable_record() -> None:
    config = load_config(CONFIG_PATH)
    raw = dict(generate_price_bars(config)[0].to_mapping())
    raw.update(
        {
            "case_id": "multi-rule",
            "is_synthetic": False,
            "high": "1.000000",
            "volume": -1,
        }
    )

    result = _validator().validate(
        [raw],
        frozenset({("QTECH", "2023-01-02")}),
        "cases/unit.json",
    )

    assert result.accepted == ()
    assert len(result.quarantined) == 1
    assert {issue.code.value for issue in result.quarantined[0].issues} == {
        "DQ_INVALID_SYNTHETIC_MARKER",
        "DQ_INVALID_OHLC",
        "DQ_NEGATIVE_VOLUME",
    }
    assert result.quarantined[0].payload_reference == "cases/unit.json#/staging_records/0"


def test_duplicate_source_event_is_rejected_without_duplicate_acceptance() -> None:
    config = load_config(CONFIG_PATH)
    raw = generate_price_bars(config)[0].to_mapping()
    duplicate = dict(raw)
    duplicate["case_id"] = "duplicate"

    result = _validator().validate(
        [raw, duplicate],
        frozenset({("QTECH", "2023-01-02")}),
        "cases/unit.json",
    )

    assert len(result.accepted) == 1
    assert len(result.quarantined) == 1
    assert result.counts_by_rule() == {"DQ_DUPLICATE_EVENT": 1}


def test_every_canonical_generated_bar_passes_the_typed_quality_rules() -> None:
    config = load_config(CONFIG_PATH)
    bars = generate_price_bars(config)
    expected_keys = frozenset((bar.symbol, bar.timestamp.date().isoformat()) for bar in bars)

    result = _validator().validate(
        [bar.to_mapping() for bar in bars],
        expected_keys,
        "canonical/price_bars.json",
    )

    assert len(result.accepted) == 2_088
    assert result.quarantined == ()
    assert result.issue_count == 0


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("open", None, "DQ_REQUIRED_FIELD"),
        ("open", "not-a-decimal", "DQ_MALFORMED_NUMBER"),
        ("volume", "not-an-integer", "DQ_MALFORMED_NUMBER"),
        ("volume", True, "DQ_MALFORMED_NUMBER"),
        ("is_synthetic", "true", "DQ_INVALID_SYNTHETIC_MARKER"),
        ("timestamp", "invalid", "DQ_MALFORMED_TIMESTAMP"),
        ("timestamp", "2023-01-02T21:00:00", "DQ_MALFORMED_TIMESTAMP"),
    ],
)
def test_unparseable_fields_receive_stable_rule_codes(
    field: str,
    value: object,
    expected_code: str,
) -> None:
    config = load_config(CONFIG_PATH)
    raw = dict(generate_price_bars(config)[0].to_mapping())
    raw[field] = value

    result = _validator().validate(
        [raw],
        frozenset({("QTECH", "2023-01-02")}),
        "cases/unit.json",
    )

    emitted_codes = {issue.code.value for record in result.quarantined for issue in record.issues}
    assert expected_code in emitted_codes


def test_symbol_regime_finite_price_and_timestamp_rules_are_explicit() -> None:
    config = load_config(CONFIG_PATH)
    raw = dict(generate_price_bars(config)[0].to_mapping())
    raw.update(
        {
            "symbol": "UNKNOWN",
            "regime": "unknown_regime",
            "open": "NaN",
            "received_at": "2023-01-02T20:00:00Z",
        }
    )

    result = _validator().validate(
        [raw],
        frozenset({("UNKNOWN", "2023-01-02")}),
        "cases/unit.json",
    )

    codes = {issue.code.value for issue in result.quarantined[0].issues}
    assert {
        "DQ_UNKNOWN_SYMBOL",
        "DQ_UNKNOWN_REGIME",
        "DQ_NON_FINITE_NUMBER",
        "DQ_RECEIVED_BEFORE_EVENT",
    }.issubset(codes)
