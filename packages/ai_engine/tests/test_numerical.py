"""Exhaustive numerical consistency, unit, and rounding tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from quantops_ai.models import (
    CanonicalUnit,
    ClaimType,
    EvidenceItem,
    EvidencePackage,
    MainFactor,
    RiskBrief,
)
from quantops_ai.numerical import validate_numerical_consistency

from .helpers import brief, factor, item, package


@pytest.mark.parametrize(
    ("evidence_unit", "evidence_value", "display_unit", "display", "precision"),
    [
        (CanonicalUnit.RATIO, Decimal("0.03456"), CanonicalUnit.PERCENT, "3.46%", 2),
        (CanonicalUnit.RATIO, Decimal("0.01234"), CanonicalUnit.BASIS_POINTS, "123.40 bps", 2),
        (CanonicalUnit.RATIO, Decimal("0.25"), CanonicalUnit.RATIO, "0.25", 2),
        (CanonicalUnit.PERCENT, Decimal("4.875"), CanonicalUnit.PERCENT, "4.88%", 2),
        (CanonicalUnit.USD, Decimal("1234.50"), CanonicalUnit.USD, "$1,234.50", 2),
        (CanonicalUnit.DAYS, Decimal("2"), CanonicalUnit.DAYS, "2", 0),
        (CanonicalUnit.COUNT, Decimal("7"), CanonicalUnit.COUNT, "7", 0),
    ],
)
def test_compatible_units_and_display_formats_validate(
    evidence_unit: CanonicalUnit,
    evidence_value: Decimal,
    display_unit: CanonicalUnit,
    display: str,
    precision: int,
) -> None:
    evidence = item(value=evidence_value, unit=evidence_unit, precision=precision)
    claim = factor(value=display, unit=display_unit)
    result = validate_numerical_consistency(brief(claim), package(evidence))
    assert result.valid
    assert result.checked_claims == 1


def test_rounding_boundary_is_inclusive_but_fabrication_is_rejected() -> None:
    evidence = item(value=Decimal("0.04875"), precision=2)
    at_boundary = factor(value="4.87%")
    outside = factor(value="4.86%")
    assert validate_numerical_consistency(brief(at_boundary), package(evidence)).valid
    report = validate_numerical_consistency(brief(outside), package(evidence))
    assert not report.valid
    assert [issue.code for issue in report.issues] == ["numerical_mismatch"]


def test_non_numeric_factor_is_not_checked() -> None:
    general = MainFactor(
        statement="Narrative claim.",
        claim_type=ClaimType.GENERAL,
        evidence_ids=("RISK-METRIC-001",),
    )
    report = validate_numerical_consistency(brief(general), package(item()))
    assert report.valid
    assert report.checked_claims == 0


def test_incomplete_numeric_claim_is_rejected_defensively() -> None:
    partial = MainFactor.model_construct(
        statement="Partial.",
        claim_type=ClaimType.METRIC,
        metric="risk.var_95",
        value=None,
        unit=None,
        evidence_ids=("RISK-METRIC-001",),
    )
    unsafe_brief = RiskBrief.model_construct(
        schema_version="1.0.0",
        answer_type="risk_explanation",
        summary="Partial claim.",
        main_factors=(partial,),
        uncertainties=(),
        recommended_checks=(),
        limitations=(),
        refusal=None,
    )
    report = validate_numerical_consistency(unsafe_brief, package(item()))
    assert not report.valid
    assert report.checked_claims == 0
    assert [issue.code for issue in report.issues] == ["incomplete_numeric_claim"]


@pytest.mark.parametrize(
    ("display", "unit"),
    [
        ("not-a-number", CanonicalUnit.PERCENT),
        ("3.46%", CanonicalUnit.RATIO),
        ("346 bps", CanonicalUnit.PERCENT),
    ],
)
def test_invalid_numeric_syntax_or_suffix_is_rejected(
    display: str,
    unit: CanonicalUnit,
) -> None:
    claim = factor(value=display, unit=unit)
    report = validate_numerical_consistency(brief(claim), package(item()))
    assert not report.valid
    assert [issue.code for issue in report.issues] == ["invalid_numeric_value"]


def test_empty_numeric_value_is_defensively_rejected() -> None:
    empty = MainFactor.model_construct(
        statement="Empty value.",
        claim_type=ClaimType.METRIC,
        metric="risk.var_95",
        value="",
        unit=CanonicalUnit.PERCENT,
        evidence_ids=("RISK-METRIC-001",),
    )
    unsafe_brief = RiskBrief.model_construct(
        schema_version="1.0.0",
        answer_type="risk_explanation",
        summary="Empty claim.",
        main_factors=(empty,),
        uncertainties=(),
        recommended_checks=(),
        limitations=(),
        refusal=None,
    )
    report = validate_numerical_consistency(unsafe_brief, package(item()))
    assert [issue.code for issue in report.issues] == ["invalid_numeric_value"]


def test_missing_metric_evidence_is_rejected() -> None:
    report = validate_numerical_consistency(
        brief(factor(metric="risk.es_95")),
        package(item()),
    )
    assert not report.valid
    assert [issue.code for issue in report.issues] == ["missing_metric_evidence"]


def test_incompatible_unit_family_is_rejected() -> None:
    report = validate_numerical_consistency(
        brief(factor(value="3.46", unit=CanonicalUnit.USD)),
        package(item()),
    )
    assert not report.valid
    assert [issue.code for issue in report.issues] == ["incompatible_unit"]


def test_any_matching_cited_metric_may_support_the_claim() -> None:
    wrong = item("RISK-METRIC-002", value=Decimal("0.90"))
    correct = item("RISK-METRIC-001", value=Decimal("0.03456"))
    claim = factor(evidence_ids=(correct.evidence_id, wrong.evidence_id))
    report = validate_numerical_consistency(brief(claim), package(correct, wrong))
    assert report.valid


def test_missing_canonical_fields_are_defensively_rejected() -> None:
    malformed = EvidenceItem.model_construct(
        evidence_id="RISK-METRIC-001",
        kind="risk",
        portfolio_id="PORT-001",
        source_timestamp=None,
        title="Malformed",
        content="Malformed",
        metric_name="risk.var_95",
        canonical_value=None,
        canonical_unit=None,
        display_precision=2,
        document_id=None,
        section=None,
        synthetic=True,
    )
    unsafe_package = EvidencePackage.model_construct(
        schema_version="1.0.0",
        package_id="PKG-MALFORMED-001",
        portfolio_id="PORT-001",
        items=(malformed,),
        created_at=None,
        max_content_characters=24_000,
    )
    report = validate_numerical_consistency(brief(factor()), unsafe_package)
    assert not report.valid
    assert [issue.code for issue in report.issues] == ["incompatible_unit"]
