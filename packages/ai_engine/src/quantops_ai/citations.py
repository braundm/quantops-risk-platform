"""Deterministic citation validation for every factual output claim."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from quantops_ai.models import ClaimType, EvidenceKind, EvidencePackage, RiskBrief


@dataclass(frozen=True, slots=True)
class CitationIssue:
    code: str
    path: str
    detail: str


@dataclass(frozen=True, slots=True)
class CitationReport:
    valid: bool
    issues: tuple[CitationIssue, ...]
    precision: float
    required_coverage: float
    cited_ids: tuple[str, ...]


_EXPECTED_KINDS: dict[ClaimType, frozenset[EvidenceKind]] = {
    ClaimType.METRIC: frozenset(
        {EvidenceKind.RISK, EvidenceKind.PRICE, EvidenceKind.SCENARIO, EvidenceKind.MODEL}
    ),
    ClaimType.DOCUMENT: frozenset({EvidenceKind.DOCUMENT}),
    ClaimType.QUALITY: frozenset({EvidenceKind.QUALITY}),
    ClaimType.SCENARIO: frozenset({EvidenceKind.SCENARIO}),
    ClaimType.METHODOLOGY: frozenset({EvidenceKind.METHODOLOGY}),
    ClaimType.GENERAL: frozenset(EvidenceKind),
}


def validate_citations(brief: RiskBrief, package: EvidencePackage) -> CitationReport:
    if brief.answer_type == "refusal":
        return CitationReport(True, (), 1.0, 1.0, ())
    known = package.by_id()
    issues: list[CitationIssue] = []
    all_citations: list[str] = []
    covered_claims = 0
    total_claims = len(brief.main_factors) + len(brief.uncertainties)

    for index, factor in enumerate(brief.main_factors):
        path = f"main_factors[{index}].evidence_ids"
        citations = tuple(factor.evidence_ids)
        all_citations.extend(citations)
        claim_has_valid_citation = _validate_id_list(citations, known, package, path, issues)
        if citations != tuple(sorted(citations)):
            issues.append(
                CitationIssue("unstable_citation_order", path, "citations must be sorted")
            )
        matching_kind = False
        for evidence_id in citations:
            evidence = known.get(evidence_id)
            if evidence is None:
                continue
            if evidence.kind in _EXPECTED_KINDS[factor.claim_type]:
                matching_kind = True
            else:
                issues.append(
                    CitationIssue(
                        "citation_kind_mismatch",
                        path,
                        f"{evidence_id} cannot support {factor.claim_type.value}",
                    )
                )
            if factor.metric is not None and evidence.metric_name != factor.metric:
                issues.append(
                    CitationIssue(
                        "citation_metric_mismatch",
                        path,
                        f"{evidence_id} does not contain metric {factor.metric}",
                    )
                )
        if claim_has_valid_citation and matching_kind:
            covered_claims += 1

    for index, uncertainty in enumerate(brief.uncertainties):
        path = f"uncertainties[{index}].evidence_ids"
        citations = tuple(uncertainty.evidence_ids)
        all_citations.extend(citations)
        if _validate_id_list(citations, known, package, path, issues):
            covered_claims += 1
        if citations != tuple(sorted(citations)):
            issues.append(
                CitationIssue("unstable_citation_order", path, "citations must be sorted")
            )

    known_count = sum(evidence_id in known for evidence_id in all_citations)
    precision = 1.0 if not all_citations else known_count / len(all_citations)
    coverage = 1.0 if total_claims == 0 else covered_claims / total_claims
    return CitationReport(
        valid=not issues and coverage == 1.0,
        issues=tuple(issues),
        precision=precision,
        required_coverage=coverage,
        cited_ids=tuple(sorted(set(all_citations))),
    )


def _validate_id_list(
    citations: tuple[str, ...],
    known: Mapping[str, object],
    package: EvidencePackage,
    path: str,
    issues: list[CitationIssue],
) -> bool:
    if not citations:
        issues.append(CitationIssue("missing_citation", path, "factual claim requires evidence"))
        return False
    if len(citations) != len(set(citations)):
        issues.append(
            CitationIssue("duplicate_citation", path, "duplicate citations are forbidden")
        )
    valid = False
    evidence_by_id = package.by_id()
    for evidence_id in citations:
        if evidence_id not in known:
            issues.append(CitationIssue("unknown_evidence_id", path, evidence_id))
            continue
        evidence = evidence_by_id[evidence_id]
        if evidence.portfolio_id != package.portfolio_id:
            issues.append(CitationIssue("cross_portfolio_evidence", path, evidence_id))
            continue
        valid = True
    return valid
