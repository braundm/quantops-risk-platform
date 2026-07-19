"""Deterministic in-memory grounded-AI application service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from threading import RLock
from uuid import NAMESPACE_URL, UUID, uuid5

from quantops_ai.demo import DEMO_DOCUMENTS
from quantops_ai.evaluator import (
    EvaluationReport,
    default_cases_path,
    load_evaluation_cases,
    run_evaluation,
)
from quantops_ai.models import (
    AnalysisRequest,
    CanonicalUnit,
    EvidenceItem,
    EvidenceKind,
)
from quantops_ai.providers import DeterministicRiskBriefProvider
from quantops_ai.retrieval import ApprovedDocumentChunk, KeywordRetriever
from quantops_ai.tools import (
    ReadOnlyToolBroker,
    ToolCall,
    ToolExecutor,
    ToolName,
    ToolNotFoundError,
)
from quantops_ai.workflow import AnalysisResult, GroundedRiskAnalyst

from quantops_api.application.demo_service import (
    DEMO_AS_OF,
    DemoQuantOpsService,
    IdempotentResult,
    RiskSnapshotRecord,
)
from quantops_api.application.errors import ConflictError, NotFoundError

_AI_NAMESPACE = uuid5(NAMESPACE_URL, "https://quantops.dev/deterministic-grounded-ai/v1")


@dataclass(frozen=True, slots=True)
class RiskBriefApplicationRecord:
    id: UUID
    portfolio_id: UUID
    snapshot_ids: tuple[UUID, ...]
    source_evidence_ids: tuple[str, ...]
    created_at: datetime
    correlation_id: UUID
    provider: str
    result: AnalysisResult
    evidence: tuple[EvidenceItem, ...]
    deterministic: bool = True
    synthetic: bool = True


@dataclass(frozen=True, slots=True)
class AiEvaluationApplicationRecord:
    id: UUID
    created_at: datetime
    correlation_id: UUID
    report: EvaluationReport
    deterministic: bool = True
    external_provider_used: bool = False


def _portfolio_scope(portfolio_id: UUID) -> str:
    return f"PORT-{portfolio_id.hex.upper()}"


def _snapshot_scope(snapshot_id: UUID) -> str:
    return f"SNAP-{snapshot_id.hex.upper()}"


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _evidence_id(prefix: str, metric: str, snapshot_id: UUID) -> str:
    normalized = metric.upper().replace(".", "-").replace("_", "-")
    return f"{prefix}-{normalized}-{snapshot_id.hex.upper()}"


def _snapshot_evidence(snapshot: RiskSnapshotRecord) -> tuple[EvidenceItem, ...]:
    portfolio_scope = _portfolio_scope(snapshot.portfolio_id)
    values: tuple[tuple[str, str, Decimal | None, CanonicalUnit], ...] = (
        (
            "portfolio.value",
            "Portfolio value",
            snapshot.portfolio_value,
            CanonicalUnit.USD,
        ),
        ("portfolio.daily_pnl", "Daily portfolio P&L", snapshot.daily_pnl, CanonicalUnit.USD),
        (
            "risk.var_historical",
            "Historical VaR",
            None if snapshot.var_historical is None else Decimal(str(snapshot.var_historical)),
            CanonicalUnit.USD,
        ),
        (
            "risk.var_parametric",
            "Parametric VaR",
            None if snapshot.var_parametric is None else Decimal(str(snapshot.var_parametric)),
            CanonicalUnit.USD,
        ),
        (
            "risk.expected_shortfall",
            "Expected Shortfall",
            None
            if snapshot.expected_shortfall is None
            else Decimal(str(snapshot.expected_shortfall)),
            CanonicalUnit.USD,
        ),
        (
            "risk.volatility_annualized",
            "Annualized volatility",
            (
                None
                if snapshot.volatility_annualized is None
                else Decimal(str(snapshot.volatility_annualized))
            ),
            CanonicalUnit.RATIO,
        ),
        (
            "risk.max_drawdown",
            "Maximum drawdown",
            None if snapshot.max_drawdown is None else Decimal(str(snapshot.max_drawdown)),
            CanonicalUnit.RATIO,
        ),
        (
            "risk.concentration_hhi",
            "Concentration HHI",
            None
            if snapshot.concentration_hhi is None
            else Decimal(str(snapshot.concentration_hhi)),
            CanonicalUnit.RATIO,
        ),
        (
            "risk.largest_absolute_weight",
            "Largest absolute portfolio weight",
            (
                None
                if snapshot.largest_absolute_weight is None
                else Decimal(str(snapshot.largest_absolute_weight))
            ),
            CanonicalUnit.RATIO,
        ),
    )
    evidence: list[EvidenceItem] = []
    for metric, title, value, unit in values:
        if value is None:
            continue
        evidence.append(
            EvidenceItem(
                evidence_id=_evidence_id("RISK", metric, snapshot.id),
                kind=EvidenceKind.RISK,
                portfolio_id=portfolio_scope,
                source_timestamp=snapshot.as_of,
                title=title,
                content=(
                    "Authoritative deterministic synthetic value computed by quantops-risk for "
                    f"snapshot {_snapshot_scope(snapshot.id)}."
                ),
                metric_name=metric,
                canonical_value=value,
                canonical_unit=unit,
                display_precision=2,
                synthetic=True,
            )
        )
    return tuple(evidence)


def _quality_evidence(snapshot: RiskSnapshotRecord) -> tuple[EvidenceItem, ...]:
    return (
        EvidenceItem(
            evidence_id=f"QUALITY-SNAPSHOT-{snapshot.id.hex.upper()}",
            kind=EvidenceKind.QUALITY,
            portfolio_id=_portfolio_scope(snapshot.portfolio_id),
            source_timestamp=snapshot.as_of,
            title=f"Snapshot quality status: {snapshot.quality_status}",
            content=(
                f"Synthetic snapshot completeness is {snapshot.data_completeness:.6f}; "
                f"observation count is {snapshot.observation_count}."
            ),
            synthetic=True,
        ),
    )


def _methodology_evidence(portfolio_id: UUID, snapshot: RiskSnapshotRecord) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"METHOD-RISK-{snapshot.methodology_version.replace('.', '-')}",
        kind=EvidenceKind.METHODOLOGY,
        portfolio_id=_portfolio_scope(portfolio_id),
        source_timestamp=snapshot.as_of,
        title=f"QuantOps risk methodology {snapshot.methodology_version}",
        content="Historical and parametric risk figures use the snapshot's recorded assumptions.",
        synthetic=True,
    )


class _ApiRiskToolExecutor(ToolExecutor):
    def __init__(
        self,
        risk_service: DemoQuantOpsService,
        portfolio_id: UUID,
        snapshots: tuple[RiskSnapshotRecord, ...],
        retriever: KeywordRetriever,
    ) -> None:
        self._risk_service = risk_service
        self._portfolio_id = portfolio_id
        self._portfolio_scope = _portfolio_scope(portfolio_id)
        self._snapshots = {_snapshot_scope(item.id): item for item in snapshots}
        self._retriever = retriever
        self.returned: dict[str, EvidenceItem] = {}

    def execute(self, call: ToolCall) -> tuple[EvidenceItem, ...]:
        if call.arguments.portfolio_id != self._portfolio_scope:
            raise ToolNotFoundError("portfolio is outside the bounded AI scope")
        result = self._execute_scoped(call)
        self.returned.update((item.evidence_id, item) for item in result)
        return result

    def _execute_scoped(self, call: ToolCall) -> tuple[EvidenceItem, ...]:
        args = call.arguments
        if call.name is ToolName.GET_PORTFOLIO_SNAPSHOT:
            return _snapshot_evidence(self._snapshot(args.snapshot_id))
        if call.name is ToolName.COMPARE_RISK_SNAPSHOTS:
            return _snapshot_evidence(self._snapshot(args.left_snapshot_id)) + _snapshot_evidence(
                self._snapshot(args.right_snapshot_id)
            )
        if call.name is ToolName.GET_RISK_CONTRIBUTIONS:
            evidence = _snapshot_evidence(self._snapshot(args.snapshot_id))
            return tuple(
                item
                for item in evidence
                if "concentration" in (item.metric_name or "")
                or "weight" in (item.metric_name or "")
            )
        if call.name is ToolName.GET_DATA_QUALITY_ISSUES:
            return _quality_evidence(self._snapshot(args.snapshot_id))
        if call.name in {ToolName.GET_METHODOLOGY_DEFINITION, ToolName.EXPLAIN_METRIC}:
            snapshot = next(iter(self._snapshots.values()), None)
            if snapshot is None:
                snapshot = self._risk_service.latest_risk(self._portfolio_id)
            return (_methodology_evidence(self._portfolio_id, snapshot),)
        if call.name in {ToolName.SEARCH_APPROVED_DOCUMENTS, ToolName.GET_DOCUMENT_EVIDENCE}:
            return self._retriever.search(args.query or "", self._portfolio_scope).evidence
        raise ToolNotFoundError(f"{call.name.value} is unavailable in deterministic API scope")

    def _snapshot(self, scoped_id: str | None) -> RiskSnapshotRecord:
        if scoped_id is None or scoped_id not in self._snapshots:
            raise ToolNotFoundError("snapshot is outside the bounded AI scope")
        return self._snapshots[scoped_id]


def _retriever_for(portfolio_id: UUID) -> KeywordRetriever:
    scope = _portfolio_scope(portfolio_id)
    return KeywordRetriever(
        tuple(
            ApprovedDocumentChunk(
                evidence_id=item.evidence_id,
                portfolio_id=scope,
                document_id=item.document_id,
                title=item.title,
                body=item.body,
                section=item.section,
                source_timestamp=item.source_timestamp,
                source_url=item.source_url,
                publication_date=item.publication_date,
                approved=item.approved,
                synthetic=item.synthetic,
            )
            for item in DEMO_DOCUMENTS
        )
    )


class DeterministicAiApplicationService:
    """Process-local AI state with synchronous, idempotent completed results."""

    def __init__(self, risk_service: DemoQuantOpsService) -> None:
        self._risk_service = risk_service
        self._lock = RLock()
        self._sequence = 0
        self._briefs: dict[UUID, RiskBriefApplicationRecord] = {}
        self._evaluations: dict[UUID, AiEvaluationApplicationRecord] = {}
        self._idempotency: dict[tuple[str, str], tuple[str, UUID]] = {}

    def _next_time(self) -> datetime:
        self._sequence += 1
        return DEMO_AS_OF + timedelta(seconds=10_000 + self._sequence)

    def create_risk_brief(
        self,
        portfolio_id: UUID,
        *,
        question: str,
        snapshot_ids: tuple[UUID, ...],
        document_query: str | None,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> IdempotentResult[RiskBriefApplicationRecord]:
        portfolio = self._risk_service.get_portfolio(portfolio_id)
        canonical = {
            "portfolio_id": str(portfolio_id),
            "question": question,
            "snapshot_ids": [str(item) for item in snapshot_ids],
            "document_query": document_query,
        }
        fingerprint = _fingerprint(canonical)
        identity = ("risk-brief", idempotency_key)
        with self._lock:
            existing = self._idempotency.get(identity)
            if existing is not None:
                stored_fingerprint, record_id = existing
                if stored_fingerprint != fingerprint:
                    raise ConflictError(
                        "idempotency key was already used with different risk-brief parameters"
                    )
                return IdempotentResult(self._briefs[record_id], True)
            selected = snapshot_ids
            if not selected and document_query is None:
                selected = (self._risk_service.latest_risk(portfolio_id).id,)
            snapshots: list[RiskSnapshotRecord] = []
            for snapshot_id in selected:
                snapshot = self._risk_service.get_snapshot(snapshot_id)
                if snapshot.portfolio_id != portfolio_id:
                    raise NotFoundError(
                        "risk snapshot was not found in the requested portfolio scope"
                    )
                snapshots.append(snapshot)
            record_id = uuid5(_AI_NAMESPACE, f"risk-brief:{idempotency_key}")
            retriever = _retriever_for(portfolio_id)
            executor = _ApiRiskToolExecutor(
                self._risk_service,
                portfolio_id,
                tuple(snapshots),
                retriever,
            )
            broker = ReadOnlyToolBroker(executor)
            analyst = GroundedRiskAnalyst(
                DeterministicRiskBriefProvider(),
                lambda: broker,
                retriever,
            )
            request = AnalysisRequest(
                request_id=f"REQ-{record_id.hex.upper()}",
                portfolio_id=_portfolio_scope(portfolio_id),
                question=question,
                snapshot_ids=tuple(_snapshot_scope(item) for item in selected),
                portfolio_name=portfolio.name,
                document_query=document_query,
            )
            result = analyst.run(request)
            evidence = dict(executor.returned)
            if document_query:
                evidence.update(
                    (
                        item.evidence_id,
                        item,
                    )
                    for item in retriever.search(
                        document_query, _portfolio_scope(portfolio_id)
                    ).evidence
                )
            cited = set(result.trace.evidence_ids)
            record = RiskBriefApplicationRecord(
                id=record_id,
                portfolio_id=portfolio_id,
                snapshot_ids=selected,
                source_evidence_ids=tuple(item.evidence_id for item in snapshots),
                created_at=self._next_time(),
                correlation_id=correlation_id,
                provider=DeterministicRiskBriefProvider.name,
                result=result,
                evidence=tuple(evidence[key] for key in sorted(cited) if key in evidence),
            )
            self._briefs[record.id] = record
            self._idempotency[identity] = (fingerprint, record.id)
            return IdempotentResult(record, False)

    def get_risk_brief(self, brief_id: UUID) -> RiskBriefApplicationRecord:
        with self._lock:
            try:
                return self._briefs[brief_id]
            except KeyError as error:
                raise NotFoundError(f"risk brief {brief_id} was not found") from error

    def run_evaluation(
        self,
        *,
        suite_version: str,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> IdempotentResult[AiEvaluationApplicationRecord]:
        fingerprint = _fingerprint({"suite_version": suite_version})
        identity = ("ai-evaluation", idempotency_key)
        with self._lock:
            existing = self._idempotency.get(identity)
            if existing is not None:
                stored_fingerprint, record_id = existing
                if stored_fingerprint != fingerprint:
                    raise ConflictError(
                        "idempotency key was already used with a different evaluation suite"
                    )
                return IdempotentResult(self._evaluations[record_id], True)
            record_id = uuid5(_AI_NAMESPACE, f"ai-evaluation:{idempotency_key}")
            report = run_evaluation(load_evaluation_cases(default_cases_path()))
            record = AiEvaluationApplicationRecord(
                id=record_id,
                created_at=self._next_time(),
                correlation_id=correlation_id,
                report=report,
            )
            self._evaluations[record.id] = record
            self._idempotency[identity] = (fingerprint, record.id)
            return IdempotentResult(record, False)
