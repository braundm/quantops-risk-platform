"""Typed test constructors."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from quantops_ai.models import (
    CanonicalUnit,
    ClaimType,
    EvidenceItem,
    EvidenceKind,
    EvidencePackage,
    MainFactor,
    RiskBrief,
)


def item(
    evidence_id: str = "RISK-METRIC-001",
    *,
    portfolio_id: str = "PORT-001",
    kind: EvidenceKind = EvidenceKind.RISK,
    metric: str | None = "risk.var_95",
    value: Decimal | None = Decimal("0.03456"),
    unit: CanonicalUnit | None = CanonicalUnit.RATIO,
    precision: int = 2,
    document_id: str | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        kind=kind,
        portfolio_id=portfolio_id,
        source_timestamp=datetime(2026, 1, 15, tzinfo=UTC),
        title="Synthetic metric",
        content="Synthetic evidence content.",
        metric_name=metric,
        canonical_value=value,
        canonical_unit=unit,
        display_precision=precision,
        document_id=document_id,
        source_url=(
            "https://docs.quantops.invalid/unit-document" if kind is EvidenceKind.DOCUMENT else None
        ),
        publication_date=date(2026, 1, 5) if kind is EvidenceKind.DOCUMENT else None,
    )


def package(*items: EvidenceItem, portfolio_id: str = "PORT-001") -> EvidencePackage:
    return EvidencePackage(
        package_id="PKG-TEST-001",
        portfolio_id=portfolio_id,
        items=items,
        created_at=datetime(2026, 1, 15, tzinfo=UTC),
    )


def factor(
    evidence_ids: tuple[str, ...] = ("RISK-METRIC-001",),
    *,
    claim_type: ClaimType = ClaimType.METRIC,
    metric: str | None = "risk.var_95",
    value: str | None = "3.46%",
    unit: CanonicalUnit | None = CanonicalUnit.PERCENT,
) -> MainFactor:
    return MainFactor(
        statement="The synthetic metric is reported by cited evidence.",
        claim_type=claim_type,
        metric=metric,
        value=value,
        unit=unit,
        evidence_ids=evidence_ids,
    )


def brief(*factors: MainFactor) -> RiskBrief:
    return RiskBrief(
        answer_type="risk_explanation",
        summary="Grounded synthetic risk explanation.",
        main_factors=factors,
        limitations=("Synthetic evidence only.",),
    )
