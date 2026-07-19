"""Finite-state, bounded grounded-risk workflow with one repair and safe fallback."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pydantic import ValidationError

from quantops_ai.classifier import RequestClass, classify_request, refusal_for
from quantops_ai.models import (
    AnalysisRequest,
    EvidenceItem,
    EvidencePackage,
    RefusalDetail,
    RiskBrief,
)
from quantops_ai.providers import (
    DeterministicRiskBriefProvider,
    ProviderError,
    ProviderInvalidOutput,
    ProviderTimeout,
    RiskBriefProvider,
)
from quantops_ai.retrieval import KeywordRetriever
from quantops_ai.tools import (
    ReadOnlyToolBroker,
    ToolArguments,
    ToolBudgetExceeded,
    ToolCall,
    ToolError,
    ToolName,
    ToolNotFoundError,
)
from quantops_ai.validation import OutputValidationReport, validate_brief


class WorkflowState(StrEnum):
    RECEIVED = "received"
    CLASSIFIED = "classified"
    CONTEXT_VALIDATED = "context_validated"
    TOOLS_SELECTED = "tools_selected"
    EVIDENCE_RETRIEVED = "evidence_retrieved"
    PACKAGE_BUILT = "package_built"
    GENERATED = "generated"
    VALIDATED = "validated"
    REPAIRED = "repaired"
    FALLBACK = "fallback"
    REFUSED = "refused"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class SafeTraceSummary:
    trace_version: str
    request_fingerprint: str
    states: tuple[str, ...]
    tool_names: tuple[str, ...]
    tool_call_count: int
    evidence_ids: tuple[str, ...]
    provider_attempts: tuple[str, ...]
    validation_issue_codes: tuple[str, ...]
    repair_attempted: bool
    fallback_used: bool
    elapsed_ms: float

    def to_mapping(self) -> dict[str, object]:
        return {
            "trace_version": self.trace_version,
            "request_fingerprint": self.request_fingerprint,
            "states": list(self.states),
            "tool_names": list(self.tool_names),
            "tool_call_count": self.tool_call_count,
            "evidence_ids": list(self.evidence_ids),
            "provider_attempts": list(self.provider_attempts),
            "validation_issue_codes": list(self.validation_issue_codes),
            "repair_attempted": self.repair_attempted,
            "fallback_used": self.fallback_used,
            "elapsed_ms": self.elapsed_ms,
            "contains_prompt_or_document_body": False,
            "contains_chain_of_thought": False,
        }


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    brief: RiskBrief
    trace: SafeTraceSummary
    validation: OutputValidationReport | None


class GroundedRiskAnalyst:
    def __init__(
        self,
        provider: RiskBriefProvider,
        broker_factory: Callable[[], ReadOnlyToolBroker],
        retriever: KeywordRetriever,
        *,
        fallback_provider: RiskBriefProvider | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._provider = provider
        self._broker_factory = broker_factory
        self._retriever = retriever
        self._fallback = fallback_provider or DeterministicRiskBriefProvider()
        self._clock = clock

    def run(self, request: AnalysisRequest) -> AnalysisResult:
        started = self._clock()
        states = [WorkflowState.RECEIVED]
        attempts: list[str] = []
        issue_codes: list[str] = []
        repair_attempted = False
        fallback_used = False
        classification = classify_request(request)
        states.append(WorkflowState.CLASSIFIED)
        if classification.request_class is not RequestClass.SUPPORTED:
            states.append(WorkflowState.REFUSED)
            return self._result(
                request,
                refusal_for(classification),
                states,
                (),
                (),
                attempts,
                issue_codes,
                repair_attempted,
                fallback_used,
                started,
                None,
            )
        states.append(WorkflowState.CONTEXT_VALIDATED)
        try:
            calls = _select_calls(request)
        except ValueError:
            states.append(WorkflowState.REFUSED)
            refusal = _context_refusal()
            return self._result(
                request,
                refusal,
                states,
                (),
                (),
                attempts,
                ("invalid_context",),
                repair_attempted,
                fallback_used,
                started,
                None,
            )
        states.append(WorkflowState.TOOLS_SELECTED)
        broker = self._broker_factory()
        evidence: list[EvidenceItem] = []
        try:
            for call in calls:
                evidence.extend(broker.call(call))
            if request.document_query:
                evidence.extend(
                    self._retriever.search(request.document_query, request.portfolio_id).evidence
                )
        except (ToolNotFoundError, ToolBudgetExceeded, ToolError):
            states.append(WorkflowState.REFUSED)
            refusal = _context_refusal()
            return self._result(
                request,
                refusal,
                states,
                tuple(event.tool_name for event in broker.events),
                (),
                attempts,
                ("tool_or_context_failure",),
                repair_attempted,
                fallback_used,
                started,
                None,
            )
        states.append(WorkflowState.EVIDENCE_RETRIEVED)
        deduplicated = {item.evidence_id: item for item in evidence}
        scoped = tuple(deduplicated[key] for key in sorted(deduplicated))
        if not scoped:
            states.append(WorkflowState.REFUSED)
            refusal = _insufficient_evidence_refusal()
            return self._result(
                request,
                refusal,
                states,
                tuple(event.tool_name for event in broker.events),
                (),
                attempts,
                ("insufficient_evidence",),
                repair_attempted,
                fallback_used,
                started,
                None,
            )
        try:
            package = EvidencePackage(
                package_id=f"PKG-{request.request_id}",
                portfolio_id=request.portfolio_id,
                items=scoped,
                created_at=max(item.source_timestamp for item in scoped),
            )
        except ValidationError:
            states.append(WorkflowState.REFUSED)
            return self._result(
                request,
                _context_refusal(),
                states,
                tuple(event.tool_name for event in broker.events),
                (),
                attempts,
                ("invalid_evidence_package",),
                repair_attempted,
                fallback_used,
                started,
                None,
            )
        states.append(WorkflowState.PACKAGE_BUILT)
        brief: RiskBrief | None = None
        report: OutputValidationReport | None = None
        try:
            attempts.append(f"{self._provider.name}:generate")
            brief = self._provider.generate(request, package)
            states.append(WorkflowState.GENERATED)
            report = validate_brief(brief, package)
            issue_codes.extend(report.issue_codes)
            states.append(WorkflowState.VALIDATED)
            if not report.valid:
                repair_attempted = True
                attempts.append(f"{self._provider.name}:repair")
                brief = self._provider.generate(request, package, report.issue_codes)
                states.append(WorkflowState.REPAIRED)
                report = validate_brief(brief, package)
                issue_codes.extend(report.issue_codes)
        except ProviderInvalidOutput:
            repair_attempted = True
            attempts.append(f"{self._provider.name}:repair_after_invalid_output")
            try:
                brief = self._provider.generate(request, package, ("schema_invalid",))
                states.append(WorkflowState.REPAIRED)
                report = validate_brief(brief, package)
                issue_codes.extend(report.issue_codes)
            except ProviderError:
                brief = None
        except (ProviderTimeout, ProviderError):
            brief = None
        if brief is None or report is None or not report.valid:
            fallback_used = True
            states.append(WorkflowState.FALLBACK)
            attempts.append(f"{self._fallback.name}:fallback")
            brief = self._fallback.generate(request, package, tuple(sorted(set(issue_codes))))
            report = validate_brief(brief, package)
            issue_codes.extend(report.issue_codes)
        if not report.valid:
            states.append(WorkflowState.REFUSED)
            brief = RiskBrief(
                answer_type="refusal",
                summary="A grounded answer could not pass deterministic safety validation.",
                refusal=RefusalDetail(
                    category="validation_failure",
                    safe_alternative="Review the cited synthetic evidence directly.",
                ),
            )
        else:
            states.append(WorkflowState.COMPLETED)
        return self._result(
            request,
            brief,
            states,
            tuple(event.tool_name for event in broker.events),
            tuple(item.evidence_id for item in scoped),
            attempts,
            tuple(sorted(set(issue_codes))),
            repair_attempted,
            fallback_used,
            started,
            report,
        )

    def _result(
        self,
        request: AnalysisRequest,
        brief: RiskBrief,
        states: list[WorkflowState],
        tool_names: tuple[str, ...],
        evidence_ids: tuple[str, ...],
        attempts: list[str],
        issue_codes: tuple[str, ...] | list[str],
        repair_attempted: bool,
        fallback_used: bool,
        started: float,
        validation: OutputValidationReport | None,
    ) -> AnalysisResult:
        elapsed = max(0.0, (self._clock() - started) * 1_000)
        fingerprint = hashlib.sha256(
            f"{request.request_id}|{request.portfolio_id}".encode()
        ).hexdigest()[:20]
        trace = SafeTraceSummary(
            trace_version="1.0.0",
            request_fingerprint=fingerprint,
            states=tuple(state.value for state in states),
            tool_names=tool_names,
            tool_call_count=len(tool_names),
            evidence_ids=evidence_ids,
            provider_attempts=tuple(attempts),
            validation_issue_codes=tuple(sorted(set(issue_codes))),
            repair_attempted=repair_attempted,
            fallback_used=fallback_used,
            elapsed_ms=round(elapsed, 3),
        )
        return AnalysisResult(brief, trace, validation)


def _select_calls(request: AnalysisRequest) -> tuple[ToolCall, ...]:
    text = request.question.lower()
    base = ToolArguments(portfolio_id=request.portfolio_id)
    if request.document_query and not request.snapshot_ids:
        return ()
    if "compare" in text:
        if len(request.snapshot_ids) != 2:
            raise ValueError("comparison requires exactly two snapshots")
        return (
            ToolCall(
                name=ToolName.COMPARE_RISK_SNAPSHOTS,
                arguments=base.model_copy(
                    update={
                        "left_snapshot_id": request.snapshot_ids[0],
                        "right_snapshot_id": request.snapshot_ids[1],
                    }
                ),
            ),
        )
    if "scenario" in text:
        if request.scenario_run_id is None:
            raise ValueError("scenario question requires scenario context")
        return (
            ToolCall(
                name=ToolName.GET_SCENARIO_RESULT,
                arguments=base.model_copy(update={"scenario_run_id": request.scenario_run_id}),
            ),
        )
    if not request.snapshot_ids:
        if "methodology" in text or "var" in text or "expected shortfall" in text:
            return (
                ToolCall(
                    name=ToolName.GET_METHODOLOGY_DEFINITION,
                    arguments=base.model_copy(update={"methodology_version": "METHODOLOGY-V1"}),
                ),
            )
        raise ValueError("risk question requires snapshot context")
    snapshot_id = request.snapshot_ids[0]
    if "quality" in text or "stale" in text:
        name = ToolName.GET_DATA_QUALITY_ISSUES
    elif "contribution" in text or "concentration" in text or "position" in text:
        name = ToolName.GET_RISK_CONTRIBUTIONS
    else:
        name = ToolName.GET_PORTFOLIO_SNAPSHOT
    return (
        ToolCall(
            name=name,
            arguments=base.model_copy(update={"snapshot_id": snapshot_id}),
        ),
    )


def _context_refusal() -> RiskBrief:
    return RiskBrief(
        answer_type="refusal",
        summary="The requested portfolio, snapshot, or scenario context is unavailable.",
        refusal=RefusalDetail(
            category="unknown_context",
            safe_alternative="Select an available synthetic portfolio and evidence context.",
        ),
    )


def _insufficient_evidence_refusal() -> RiskBrief:
    return RiskBrief(
        answer_type="refusal",
        summary="No approved evidence matched the bounded request.",
        refusal=RefusalDetail(
            category="insufficient_evidence",
            safe_alternative="Use a valid snapshot or a more specific approved-document query.",
        ),
    )
