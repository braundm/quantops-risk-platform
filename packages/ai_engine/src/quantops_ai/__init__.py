"""Bounded, citation-grounded QuantOps risk analyst."""

from quantops_ai.citations import CitationReport, validate_citations
from quantops_ai.classifier import Classification, RequestClass, classify_request
from quantops_ai.models import (
    AnalysisRequest,
    CanonicalUnit,
    ClaimType,
    EvidenceItem,
    EvidenceKind,
    EvidencePackage,
    MainFactor,
    RefusalDetail,
    RiskBrief,
    Uncertainty,
)
from quantops_ai.numerical import NumericalReport, validate_numerical_consistency
from quantops_ai.providers import (
    DeterministicRiskBriefProvider,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
    ProviderError,
    ProviderInvalidOutput,
    ProviderTimeout,
)
from quantops_ai.validation import OutputValidationReport, validate_brief
from quantops_ai.workflow import AnalysisResult, GroundedRiskAnalyst, SafeTraceSummary

__all__ = [
    "AnalysisRequest",
    "AnalysisResult",
    "CanonicalUnit",
    "CitationReport",
    "ClaimType",
    "Classification",
    "DeterministicRiskBriefProvider",
    "EvidenceItem",
    "EvidenceKind",
    "EvidencePackage",
    "GroundedRiskAnalyst",
    "MainFactor",
    "NumericalReport",
    "OpenAICompatibleConfig",
    "OpenAICompatibleProvider",
    "OutputValidationReport",
    "ProviderError",
    "ProviderInvalidOutput",
    "ProviderTimeout",
    "RefusalDetail",
    "RequestClass",
    "RiskBrief",
    "SafeTraceSummary",
    "Uncertainty",
    "classify_request",
    "validate_brief",
    "validate_citations",
    "validate_numerical_consistency",
]

__version__ = "0.1.0"
