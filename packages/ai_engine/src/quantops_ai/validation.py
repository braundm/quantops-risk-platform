"""Aggregate schema-adjacent, citation, numerical, content, and scope checks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from quantops_ai.citations import CitationReport, validate_citations
from quantops_ai.models import EvidencePackage, RiskBrief
from quantops_ai.numerical import NumericalReport, validate_numerical_consistency

_PROHIBITED = {
    "investment_advice": re.compile(
        r"\b(you should|i recommend)\b.{0,30}\b(buy|sell|short|trade)\b", re.I
    ),
    "guaranteed_forecast": re.compile(r"\b(guaranteed|certain profit|will definitely)\b", re.I),
    "order_execution": re.compile(r"\b(execute|place|submit)\b.{0,20}\b(order|trade)\b", re.I),
    "secret_exposure": re.compile(r"\b(api key|password|secret value|system prompt)\b", re.I),
    "hidden_reasoning": re.compile(r"\b(chain[- ]of[- ]thought|hidden reasoning)\b", re.I),
    "arbitrary_url": re.compile(r"https?://", re.I),
}


@dataclass(frozen=True, slots=True)
class OutputValidationReport:
    valid: bool
    issue_codes: tuple[str, ...]
    citation: CitationReport
    numerical: NumericalReport


def validate_brief(brief: RiskBrief, package: EvidencePackage) -> OutputValidationReport:
    citation = validate_citations(brief, package)
    numerical = validate_numerical_consistency(brief, package)
    codes = [issue.code for issue in citation.issues]
    codes.extend(issue.code for issue in numerical.issues)
    text = " ".join(
        (
            brief.summary,
            *(factor.statement for factor in brief.main_factors),
            *(uncertainty.statement for uncertainty in brief.uncertainties),
            *brief.recommended_checks,
            *brief.limitations,
        )
    )
    if brief.answer_type != "refusal":
        for code, pattern in _PROHIBITED.items():
            if pattern.search(text):
                codes.append(code)
    codes = sorted(set(codes))
    return OutputValidationReport(not codes, tuple(codes), citation, numerical)
