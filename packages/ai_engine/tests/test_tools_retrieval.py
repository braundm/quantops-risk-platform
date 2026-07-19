"""Read-only tool budgets, scoping, audits, and lexical retrieval tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest
from pydantic import ValidationError

from quantops_ai.demo import DEMO_DOCUMENTS, DemoToolExecutor
from quantops_ai.retrieval import ApprovedDocumentChunk, KeywordRetriever
from quantops_ai.tools import (
    READ_ONLY_TOOL_ALLOWLIST,
    ReadOnlyToolBroker,
    ToolArguments,
    ToolBudget,
    ToolBudgetExceeded,
    ToolCall,
    ToolError,
    ToolName,
    ToolNotFoundError,
)

from .helpers import item


@pytest.mark.parametrize("tool_name", tuple(ToolName))
def test_every_allowlisted_tool_requires_its_typed_arguments(tool_name: ToolName) -> None:
    assert tool_name in READ_ONLY_TOOL_ALLOWLIST
    with pytest.raises(ValidationError, match="missing required arguments"):
        ToolCall(name=tool_name, arguments=ToolArguments(portfolio_id="PORT-001"))


def test_comparison_requires_distinct_snapshot_ids() -> None:
    args = ToolArguments(
        portfolio_id="PORT-001",
        left_snapshot_id="SNAP-001",
        right_snapshot_id="SNAP-001",
    )
    with pytest.raises(ValidationError, match="must differ"):
        ToolCall(name=ToolName.COMPARE_RISK_SNAPSHOTS, arguments=args)


def test_demo_tool_returns_scoped_evidence_and_safe_audit() -> None:
    broker = ReadOnlyToolBroker(DemoToolExecutor())
    call = ToolCall(
        name=ToolName.GET_PORTFOLIO_SNAPSHOT,
        arguments=ToolArguments(portfolio_id="PORT-001", snapshot_id="SNAP-001"),
    )
    result = broker.call(call)
    assert len(result) == 3
    event = broker.events[0]
    assert event.status == "ok"
    assert event.tool_name == "get_portfolio_snapshot"
    assert event.argument_fields == ("portfolio_id", "snapshot_id")
    assert "PORT-001" not in repr(event)
    assert set(event.evidence_ids) == {item.evidence_id for item in result}


@pytest.mark.parametrize(
    "budget",
    [
        ToolBudget(maximum_calls=1, maximum_result_bytes=256),
        ToolBudget(maximum_calls=1, per_call_timeout_seconds=0.1),
    ],
)
def test_valid_tool_budgets_round_trip(budget: ToolBudget) -> None:
    assert budget.maximum_calls == 1


def test_tool_budget_configuration_validation() -> None:
    with pytest.raises(ValueError, match="positive"):
        ToolBudget(maximum_calls=0)
    with pytest.raises(ValueError, match="time budgets"):
        ToolBudget(per_call_timeout_seconds=0)


@dataclass(slots=True)
class ManualClock:
    value: float = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class StaticExecutor:
    def __init__(self, result: tuple[object, ...], error: ToolError | None = None) -> None:
        self.result = result
        self.error = error

    def execute(self, call: ToolCall) -> tuple[object, ...]:
        del call
        if self.error is not None:
            raise self.error
        return self.result


class AdvancingExecutor:
    def __init__(self, clock: ManualClock) -> None:
        self.clock = clock

    def execute(self, call: ToolCall) -> tuple[object, ...]:
        del call
        self.clock.advance(2.0)
        return (item(),)


def _snapshot_call() -> ToolCall:
    return ToolCall(
        name=ToolName.GET_PORTFOLIO_SNAPSHOT,
        arguments=ToolArguments(portfolio_id="PORT-001", snapshot_id="SNAP-001"),
    )


def test_broker_enforces_call_count_and_total_time() -> None:
    broker = ReadOnlyToolBroker(DemoToolExecutor(), ToolBudget(maximum_calls=1))
    broker.call(_snapshot_call())
    with pytest.raises(ToolBudgetExceeded, match="call budget"):
        broker.call(_snapshot_call())

    clock = ManualClock()
    timed = ReadOnlyToolBroker(DemoToolExecutor(), clock=clock)
    clock.advance(4.0)
    with pytest.raises(ToolBudgetExceeded, match="total tool-time"):
        timed.call(_snapshot_call())


def test_broker_enforces_per_call_timeout_and_size() -> None:
    clock = ManualClock()
    timed = ReadOnlyToolBroker(
        AdvancingExecutor(clock),  # type: ignore[arg-type]
        ToolBudget(per_call_timeout_seconds=1.0),
        clock,
    )
    with pytest.raises(ToolBudgetExceeded, match="exceeded timeout"):
        timed.call(_snapshot_call())
    assert timed.events[0].status == "timeout"

    oversized_item = item().model_copy(update={"content": "x" * 4_000})
    oversized = ReadOnlyToolBroker(
        StaticExecutor((oversized_item,)),  # type: ignore[arg-type]
        ToolBudget(maximum_result_bytes=256),
    )
    with pytest.raises(ToolBudgetExceeded, match="size budget"):
        oversized.call(_snapshot_call())
    assert oversized.events[0].status == "oversized"


def test_broker_rejects_executor_error_cross_scope_and_non_allowlisted_tool() -> None:
    failing = ReadOnlyToolBroker(
        StaticExecutor((), ToolNotFoundError("missing")),  # type: ignore[arg-type]
    )
    with pytest.raises(ToolNotFoundError):
        failing.call(_snapshot_call())
    assert failing.events[0].status == "error"

    foreign = item(portfolio_id="PORT-002")
    crossed = ReadOnlyToolBroker(StaticExecutor((foreign,)))  # type: ignore[arg-type]
    with pytest.raises(ToolError, match="cross-portfolio"):
        crossed.call(_snapshot_call())
    assert crossed.events[0].status == "scope_violation"

    unsafe = ToolCall.model_construct(name="delete_portfolio", arguments=_snapshot_call().arguments)
    with pytest.raises(ToolError, match="allowlist"):
        crossed.call(unsafe)


def test_keyword_retrieval_filters_scope_approval_deduplicates_and_ranks() -> None:
    duplicate = DEMO_DOCUMENTS[0]
    cross_scope = ApprovedDocumentChunk(
        evidence_id="DOC-FOREIGN-001",
        portfolio_id="PORT-002",
        document_id="DOC-FOREIGN",
        title="Scenario assumptions",
        body="rate scenario assumptions",
        section="Foreign",
        source_timestamp=duplicate.source_timestamp,
        source_url="https://docs.quantops.invalid/foreign",
        publication_date=date(2026, 1, 5),
    )
    retriever = KeywordRetriever((*DEMO_DOCUMENTS, duplicate, cross_scope))
    result = retriever.search("rate scenario assumptions", "PORT-001", limit=2)
    assert result.evidence[0].evidence_id == "DOC-SCENARIO-METHOD"
    assert len({entry.evidence_id for entry in result.evidence}) == len(result.evidence)
    assert "DOC-UNAPPROVED" not in {entry.evidence_id for entry in result.evidence}
    assert "DOC-FOREIGN-001" not in {entry.evidence_id for entry in result.evidence}
    assert result.query_tokens == ("assumptions", "rate", "scenario")
    assert result.considered_chunks == 4


def test_keyword_retrieval_empty_and_configuration_validation() -> None:
    retriever = KeywordRetriever(DEMO_DOCUMENTS)
    assert retriever.search("!", "PORT-001").evidence == ()
    with pytest.raises(ValueError, match="between one and eight"):
        retriever.search("scenario", "PORT-001", limit=0)
    with pytest.raises(ValueError, match="between zero and one"):
        retriever.search("scenario", "PORT-001", minimum_score=2.0)
