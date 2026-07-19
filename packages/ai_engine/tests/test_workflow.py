"""Finite-state repair, fallback, refusal, and safe-trace tests."""

from __future__ import annotations

import json

from quantops_ai.demo import DemoToolExecutor, demo_retriever
from quantops_ai.models import AnalysisRequest, EvidencePackage, RiskBrief
from quantops_ai.providers import (
    DeterministicRiskBriefProvider,
    ProviderError,
    ProviderInvalidOutput,
    ProviderTimeout,
)
from quantops_ai.tools import ReadOnlyToolBroker, ToolBudget
from quantops_ai.workflow import GroundedRiskAnalyst


class BadCitationProvider:
    name = "bad-citation-provider"

    def generate(
        self,
        request: AnalysisRequest,
        package: EvidencePackage,
        validation_feedback: tuple[str, ...] = (),
    ) -> RiskBrief:
        answer = DeterministicRiskBriefProvider().generate(request, package, validation_feedback)
        first = answer.main_factors[0].model_copy(update={"evidence_ids": ("RISK-UNKNOWN",)})
        return answer.model_copy(update={"main_factors": (first, *answer.main_factors[1:])})


class RepairingProvider:
    name = "repairing-provider"

    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        request: AnalysisRequest,
        package: EvidencePackage,
        validation_feedback: tuple[str, ...] = (),
    ) -> RiskBrief:
        self.calls += 1
        if validation_feedback:
            return DeterministicRiskBriefProvider().generate(request, package)
        return BadCitationProvider().generate(request, package)


class InvalidThenValidProvider:
    name = "invalid-then-valid-provider"

    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        request: AnalysisRequest,
        package: EvidencePackage,
        validation_feedback: tuple[str, ...] = (),
    ) -> RiskBrief:
        self.calls += 1
        if self.calls == 1:
            raise ProviderInvalidOutput("invalid JSON")
        return DeterministicRiskBriefProvider().generate(request, package, validation_feedback)


class RaisingProvider:
    name = "raising-provider"

    def __init__(self, error: ProviderError) -> None:
        self.error = error

    def generate(
        self,
        request: AnalysisRequest,
        package: EvidencePackage,
        validation_feedback: tuple[str, ...] = (),
    ) -> RiskBrief:
        del request, package, validation_feedback
        raise self.error


class UnsafeFallbackProvider:
    name = "unsafe-fallback-provider"

    def generate(
        self,
        request: AnalysisRequest,
        package: EvidencePackage,
        validation_feedback: tuple[str, ...] = (),
    ) -> RiskBrief:
        answer = DeterministicRiskBriefProvider().generate(request, package, validation_feedback)
        return answer.model_copy(update={"summary": "You should buy this asset."})


def _analyst(
    provider: object,
    *,
    fallback: object | None = None,
    budget: ToolBudget | None = None,
) -> GroundedRiskAnalyst:
    configured_budget = budget or ToolBudget()
    return GroundedRiskAnalyst(
        provider,  # type: ignore[arg-type]
        lambda: ReadOnlyToolBroker(DemoToolExecutor(), configured_budget),
        demo_retriever(),
        fallback_provider=fallback,  # type: ignore[arg-type]
    )


def test_supported_workflow_is_bounded_validated_and_safely_traced(
    risk_request: AnalysisRequest,
) -> None:
    result = _analyst(DeterministicRiskBriefProvider()).run(risk_request)
    assert result.brief.answer_type == "risk_explanation"
    assert result.validation is not None and result.validation.valid
    assert result.trace.tool_call_count == 1
    assert result.trace.tool_names == ("get_portfolio_snapshot",)
    assert result.trace.states[-1] == "completed"
    assert not result.trace.repair_attempted
    assert not result.trace.fallback_used
    serialized = json.dumps(result.trace.to_mapping(), sort_keys=True)
    assert risk_request.question not in serialized
    assert 'chain_of_thought": false' in serialized
    assert 'prompt_or_document_body": false' in serialized


def test_invalid_grounding_is_repaired_once_without_fallback(
    risk_request: AnalysisRequest,
) -> None:
    provider = RepairingProvider()
    result = _analyst(provider).run(risk_request)
    assert provider.calls == 2
    assert result.trace.repair_attempted
    assert not result.trace.fallback_used
    assert "unknown_evidence_id" in result.trace.validation_issue_codes
    assert "repaired" in result.trace.states
    assert result.brief.answer_type != "refusal"


def test_persistently_invalid_grounding_uses_deterministic_fallback(
    risk_request: AnalysisRequest,
) -> None:
    result = _analyst(BadCitationProvider()).run(risk_request)
    assert result.trace.repair_attempted
    assert result.trace.fallback_used
    assert result.trace.provider_attempts == (
        "bad-citation-provider:generate",
        "bad-citation-provider:repair",
        "deterministic-risk-brief-v1:fallback",
    )
    assert result.validation is not None and result.validation.valid


def test_invalid_provider_output_gets_one_repair_then_completes(
    risk_request: AnalysisRequest,
) -> None:
    provider = InvalidThenValidProvider()
    result = _analyst(provider).run(risk_request)
    assert provider.calls == 2
    assert result.trace.repair_attempted
    assert not result.trace.fallback_used
    assert result.brief.answer_type != "refusal"


def test_invalid_output_and_timeout_fall_back_without_network(
    risk_request: AnalysisRequest,
) -> None:
    invalid = _analyst(RaisingProvider(ProviderInvalidOutput("bad"))).run(risk_request)
    assert invalid.trace.repair_attempted
    assert invalid.trace.fallback_used
    timeout = _analyst(RaisingProvider(ProviderTimeout("slow"))).run(risk_request)
    assert not timeout.trace.repair_attempted
    assert timeout.trace.fallback_used
    generic = _analyst(RaisingProvider(ProviderError("offline"))).run(risk_request)
    assert generic.trace.fallback_used


def test_unsafe_fallback_results_in_deterministic_refusal(
    risk_request: AnalysisRequest,
) -> None:
    result = _analyst(
        RaisingProvider(ProviderTimeout("slow")),
        fallback=UnsafeFallbackProvider(),
    ).run(risk_request)
    assert result.brief.answer_type == "refusal"
    assert result.brief.refusal is not None
    assert result.brief.refusal.category == "validation_failure"
    assert result.trace.states[-1] == "refused"


def test_unknown_context_invalid_context_and_tool_budget_refuse_safely() -> None:
    unknown = AnalysisRequest(
        request_id="REQ-UNKNOWN-001",
        portfolio_id="PORT-001",
        question="Explain risk.",
        snapshot_ids=("SNAP-999",),
    )
    unknown_result = _analyst(DeterministicRiskBriefProvider()).run(unknown)
    assert unknown_result.brief.answer_type == "refusal"
    assert "tool_or_context_failure" in unknown_result.trace.validation_issue_codes

    invalid_compare = AnalysisRequest(
        request_id="REQ-COMPARE-INVALID",
        portfolio_id="PORT-001",
        question="Compare risk snapshots.",
        snapshot_ids=("SNAP-001",),
    )
    compare_result = _analyst(DeterministicRiskBriefProvider()).run(invalid_compare)
    assert "invalid_context" in compare_result.trace.validation_issue_codes

    constrained = _analyst(
        DeterministicRiskBriefProvider(),
        budget=ToolBudget(maximum_result_bytes=256),
    ).run(
        AnalysisRequest(
            request_id="REQ-BUDGET-001",
            portfolio_id="PORT-001",
            question="Explain risk.",
            snapshot_ids=("SNAP-001",),
        )
    )
    assert constrained.brief.answer_type == "refusal"
    assert constrained.trace.states[-1] == "refused"


def test_document_injection_is_data_and_never_enters_safe_trace() -> None:
    request = AnalysisRequest(
        request_id="REQ-DOC-001",
        portfolio_id="PORT-001",
        question="Summarize approved document evidence.",
        document_query="prompt injection test fixture",
    )
    result = _analyst(DeterministicRiskBriefProvider()).run(request)
    assert result.brief.answer_type == "document_summary"
    serialized = json.dumps(result.trace.to_mapping()).lower()
    assert "ignore previous instructions" not in serialized
    assert "system prompt" not in serialized
    assert result.trace.tool_call_count == 0


def test_classifier_refusal_skips_tools_and_provider() -> None:
    request = AnalysisRequest(
        request_id="REQ-EXECUTE-001",
        portfolio_id="PORT-001",
        question="Execute a trade order.",
    )
    result = _analyst(RaisingProvider(ProviderError("must not be called"))).run(request)
    assert result.brief.answer_type == "refusal"
    assert result.trace.tool_call_count == 0
    assert result.trace.provider_attempts == ()
