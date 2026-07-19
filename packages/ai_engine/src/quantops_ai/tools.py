"""Fixed read-only tool protocol with call, time, and response-size budgets."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from pydantic import Field, model_validator

from quantops_ai.models import EvidenceItem, FrozenModel, Identifier


class ToolName(StrEnum):
    GET_PORTFOLIO_SNAPSHOT = "get_portfolio_snapshot"
    COMPARE_RISK_SNAPSHOTS = "compare_risk_snapshots"
    GET_RISK_CONTRIBUTIONS = "get_risk_contributions"
    GET_SCENARIO_RESULT = "get_scenario_result"
    GET_DATA_QUALITY_ISSUES = "get_data_quality_issues"
    GET_METHODOLOGY_DEFINITION = "get_methodology_definition"
    SEARCH_APPROVED_DOCUMENTS = "search_approved_documents"
    GET_DOCUMENT_EVIDENCE = "get_document_evidence"
    GET_MODEL_STATUS = "get_model_status"
    EXPLAIN_METRIC = "explain_metric"


READ_ONLY_TOOL_ALLOWLIST = frozenset(ToolName)


class ToolArguments(FrozenModel):
    portfolio_id: Identifier
    snapshot_id: Identifier | None = None
    left_snapshot_id: Identifier | None = None
    right_snapshot_id: Identifier | None = None
    scenario_run_id: Identifier | None = None
    methodology_version: Identifier | None = None
    model_name: Identifier | None = None
    metric_name: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_.]{1,79}")
    query: str | None = Field(default=None, min_length=1, max_length=300)


class ToolCall(FrozenModel):
    name: ToolName
    arguments: ToolArguments

    @model_validator(mode="after")
    def validate_required_arguments(self) -> ToolCall:
        args = self.arguments
        requirements: Mapping[ToolName, tuple[str, ...]] = {
            ToolName.GET_PORTFOLIO_SNAPSHOT: ("snapshot_id",),
            ToolName.COMPARE_RISK_SNAPSHOTS: ("left_snapshot_id", "right_snapshot_id"),
            ToolName.GET_RISK_CONTRIBUTIONS: ("snapshot_id",),
            ToolName.GET_SCENARIO_RESULT: ("scenario_run_id",),
            ToolName.GET_DATA_QUALITY_ISSUES: ("snapshot_id",),
            ToolName.GET_METHODOLOGY_DEFINITION: ("methodology_version",),
            ToolName.SEARCH_APPROVED_DOCUMENTS: ("query",),
            ToolName.GET_DOCUMENT_EVIDENCE: ("query",),
            ToolName.GET_MODEL_STATUS: ("model_name",),
            ToolName.EXPLAIN_METRIC: ("metric_name",),
        }
        missing = [
            field_name for field_name in requirements[self.name] if not getattr(args, field_name)
        ]
        if missing:
            raise ValueError(f"{self.name.value} missing required arguments: {', '.join(missing)}")
        if (
            self.name is ToolName.COMPARE_RISK_SNAPSHOTS
            and args.left_snapshot_id == args.right_snapshot_id
        ):
            raise ValueError("comparison snapshot IDs must differ")
        return self


class ToolExecutor(Protocol):
    def execute(self, call: ToolCall) -> tuple[EvidenceItem, ...]: ...


class ToolError(RuntimeError):
    """Base error for bounded tool calls."""


class ToolNotFoundError(ToolError):
    """Requested scoped object was not found."""


class ToolBudgetExceeded(ToolError):
    """A call, duration, or result-size budget was exceeded."""


@dataclass(frozen=True, slots=True)
class ToolBudget:
    maximum_calls: int = 6
    maximum_result_bytes: int = 32_000
    per_call_timeout_seconds: float = 1.0
    total_timeout_seconds: float = 3.0

    def __post_init__(self) -> None:
        if self.maximum_calls < 1 or self.maximum_result_bytes < 256:
            raise ValueError("tool count and result-size budgets must be positive")
        if self.per_call_timeout_seconds <= 0 or self.total_timeout_seconds <= 0:
            raise ValueError("tool time budgets must be positive")


@dataclass(frozen=True, slots=True)
class ToolAuditEvent:
    sequence: int
    tool_name: str
    argument_fields: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    result_bytes: int
    status: str


@dataclass(slots=True)
class ReadOnlyToolBroker:
    executor: ToolExecutor
    budget: ToolBudget = field(default_factory=ToolBudget)
    clock: Callable[[], float] = time.monotonic
    _started_at: float = field(init=False)
    _calls: int = field(init=False, default=0)
    _events: list[ToolAuditEvent] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self._started_at = self.clock()

    @property
    def events(self) -> tuple[ToolAuditEvent, ...]:
        return tuple(self._events)

    def call(self, call: ToolCall) -> tuple[EvidenceItem, ...]:
        if call.name not in READ_ONLY_TOOL_ALLOWLIST:  # defensive for non-Pydantic construction
            raise ToolError("tool is not in the read-only allowlist")
        if self._calls >= self.budget.maximum_calls:
            raise ToolBudgetExceeded("tool-call budget exhausted")
        if self.clock() - self._started_at > self.budget.total_timeout_seconds:
            raise ToolBudgetExceeded("total tool-time budget exhausted")
        self._calls += 1
        before = self.clock()
        try:
            result = self.executor.execute(call)
        except ToolError:
            self._record(call, (), 0, "error")
            raise
        elapsed = self.clock() - before
        if elapsed > self.budget.per_call_timeout_seconds:
            self._record(call, (), 0, "timeout")
            raise ToolBudgetExceeded("tool call exceeded timeout")
        result_bytes = sum(len(item.model_dump_json()) for item in result)
        if result_bytes > self.budget.maximum_result_bytes:
            self._record(call, (), result_bytes, "oversized")
            raise ToolBudgetExceeded("tool result exceeded size budget")
        if any(item.portfolio_id != call.arguments.portfolio_id for item in result):
            self._record(call, (), result_bytes, "scope_violation")
            raise ToolError("tool returned cross-portfolio evidence")
        self._record(call, result, result_bytes, "ok")
        return result

    def _record(
        self,
        call: ToolCall,
        result: tuple[EvidenceItem, ...],
        result_bytes: int,
        status: str,
    ) -> None:
        fields = tuple(
            sorted(key for key, value in call.arguments.model_dump().items() if value is not None)
        )
        self._events.append(
            ToolAuditEvent(
                sequence=self._calls,
                tool_name=call.name.value,
                argument_fields=fields,
                evidence_ids=tuple(item.evidence_id for item in result),
                result_bytes=result_bytes,
                status=status,
            )
        )
