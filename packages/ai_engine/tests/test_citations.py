"""Exhaustive citation-validator behavior and branch coverage."""

from __future__ import annotations

from datetime import UTC, datetime

from quantops_ai.citations import validate_citations
from quantops_ai.models import (
    ClaimType,
    EvidenceKind,
    EvidencePackage,
    MainFactor,
    RefusalDetail,
    RiskBrief,
    Uncertainty,
)

from .helpers import brief, factor, item, package


def test_valid_metric_citation_has_full_precision_and_coverage() -> None:
    result = validate_citations(brief(factor()), package(item()))
    assert result.valid
    assert result.precision == 1.0
    assert result.required_coverage == 1.0
    assert result.cited_ids == ("RISK-METRIC-001",)
    assert result.issues == ()


def test_refusal_needs_no_citations() -> None:
    refusal = RiskBrief(
        answer_type="refusal",
        summary="Cannot answer.",
        refusal=RefusalDetail(category="unsupported", safe_alternative="Ask about risk."),
    )
    result = validate_citations(refusal, package(item()))
    assert result.valid
    assert result.precision == result.required_coverage == 1.0


def test_empty_citation_is_rejected() -> None:
    empty_factor = MainFactor.model_construct(
        statement="Unsupported fact.",
        claim_type=ClaimType.GENERAL,
        metric=None,
        value=None,
        unit=None,
        evidence_ids=(),
    )
    result = validate_citations(brief(empty_factor), package(item()))
    assert not result.valid
    assert result.required_coverage == 0.0
    assert {issue.code for issue in result.issues} == {"missing_citation"}


def test_unknown_and_duplicate_citations_reduce_precision() -> None:
    duplicated = MainFactor(
        statement="Fact with bad citations.",
        claim_type=ClaimType.GENERAL,
        evidence_ids=("RISK-UNKNOWN", "RISK-METRIC-001", "RISK-UNKNOWN"),
    )
    result = validate_citations(brief(duplicated), package(item()))
    assert not result.valid
    assert result.precision == 1 / 3
    assert {issue.code for issue in result.issues} == {
        "duplicate_citation",
        "unknown_evidence_id",
        "unstable_citation_order",
    }


def test_unstable_known_citation_order_is_rejected() -> None:
    left = item("RISK-ZZZ-001")
    right = item("RISK-AAA-001")
    general = MainFactor(
        statement="Two cited facts.",
        claim_type=ClaimType.GENERAL,
        evidence_ids=(left.evidence_id, right.evidence_id),
    )
    result = validate_citations(brief(general), package(left, right))
    assert not result.valid
    assert [issue.code for issue in result.issues] == ["unstable_citation_order"]
    assert result.cited_ids == (right.evidence_id, left.evidence_id)


def test_claim_kind_and_metric_mismatches_are_rejected() -> None:
    risk = item()
    wrong_kind = MainFactor(
        statement="Purported document claim.",
        claim_type=ClaimType.DOCUMENT,
        evidence_ids=(risk.evidence_id,),
    )
    wrong_metric = factor(metric="risk.es_95")
    result = validate_citations(brief(wrong_kind, wrong_metric), package(risk))
    codes = {issue.code for issue in result.issues}
    assert codes == {"citation_kind_mismatch", "citation_metric_mismatch"}
    assert result.required_coverage == 0.5


def test_document_quality_scenario_and_methodology_kinds_validate() -> None:
    document = item(
        "DOC-APPROVED-001",
        kind=EvidenceKind.DOCUMENT,
        metric=None,
        value=None,
        unit=None,
        document_id="DOC-001",
    )
    quality = item(
        "QUALITY-STALE-001",
        kind=EvidenceKind.QUALITY,
        metric=None,
        value=None,
        unit=None,
    )
    scenario = item(
        "SCENARIO-SHOCK-001",
        kind=EvidenceKind.SCENARIO,
        metric=None,
        value=None,
        unit=None,
    )
    methodology = item(
        "METHOD-VAR-001",
        kind=EvidenceKind.METHODOLOGY,
        metric=None,
        value=None,
        unit=None,
    )
    factors = (
        MainFactor(
            statement="Document fact.",
            claim_type=ClaimType.DOCUMENT,
            evidence_ids=(document.evidence_id,),
        ),
        MainFactor(
            statement="Quality fact.",
            claim_type=ClaimType.QUALITY,
            evidence_ids=(quality.evidence_id,),
        ),
        MainFactor(
            statement="Scenario fact.",
            claim_type=ClaimType.SCENARIO,
            evidence_ids=(scenario.evidence_id,),
        ),
        MainFactor(
            statement="Methodology fact.",
            claim_type=ClaimType.METHODOLOGY,
            evidence_ids=(methodology.evidence_id,),
        ),
    )
    result = validate_citations(
        brief(*factors),
        package(document, quality, scenario, methodology),
    )
    assert result.valid


def test_uncertainty_citations_are_checked_for_unknown_and_order() -> None:
    first = item("QUALITY-AAA-001", kind=EvidenceKind.QUALITY, metric=None, value=None, unit=None)
    second = item("QUALITY-ZZZ-001", kind=EvidenceKind.QUALITY, metric=None, value=None, unit=None)
    answer = RiskBrief(
        answer_type="risk_explanation",
        summary="Qualified answer.",
        uncertainties=(
            Uncertainty(
                statement="Quality uncertainty.",
                evidence_ids=(second.evidence_id, first.evidence_id, "QUALITY-UNKNOWN"),
            ),
        ),
    )
    result = validate_citations(answer, package(first, second))
    assert not result.valid
    assert result.required_coverage == 1.0
    assert {issue.code for issue in result.issues} == {
        "unknown_evidence_id",
        "unstable_citation_order",
    }


def test_uncertainty_without_any_known_citation_is_uncovered() -> None:
    answer = RiskBrief(
        answer_type="risk_explanation",
        summary="Uncovered uncertainty.",
        uncertainties=(
            Uncertainty(
                statement="Unknown quality source.",
                evidence_ids=("QUALITY-UNKNOWN",),
            ),
        ),
    )
    result = validate_citations(answer, package(item()))
    assert not result.valid
    assert result.required_coverage == 0.0
    assert [issue.code for issue in result.issues] == ["unknown_evidence_id"]


def test_cross_portfolio_citation_is_defensively_rejected() -> None:
    foreign = item(portfolio_id="PORT-002")
    unsafe_package = EvidencePackage.model_construct(
        schema_version="1.0.0",
        package_id="PKG-UNSAFE-001",
        portfolio_id="PORT-001",
        items=(foreign,),
        created_at=datetime(2026, 1, 15, tzinfo=UTC),
        max_content_characters=24_000,
    )
    result = validate_citations(brief(factor()), unsafe_package)
    assert not result.valid
    assert result.required_coverage == 0.0
    assert [issue.code for issue in result.issues] == ["cross_portfolio_evidence"]


def test_non_refusal_with_no_factual_claims_is_vacuously_valid() -> None:
    answer = RiskBrief(answer_type="risk_explanation", summary="No factual claims supplied.")
    result = validate_citations(answer, package(item()))
    assert result.valid
    assert result.cited_ids == ()
    assert result.precision == result.required_coverage == 1.0
