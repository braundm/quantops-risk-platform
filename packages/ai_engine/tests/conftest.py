"""Shared immutable synthetic fixtures."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from quantops_ai.demo import DEMO_PORTFOLIO_ID, SNAPSHOT_EVIDENCE
from quantops_ai.models import AnalysisRequest, EvidencePackage


@pytest.fixture
def evidence_package() -> EvidencePackage:
    return EvidencePackage(
        package_id="PKG-UNIT-001",
        portfolio_id=DEMO_PORTFOLIO_ID,
        items=SNAPSHOT_EVIDENCE["SNAP-001"],
        created_at=datetime(2026, 1, 15, tzinfo=UTC),
    )


@pytest.fixture
def risk_request() -> AnalysisRequest:
    return AnalysisRequest(
        request_id="REQ-UNIT-001",
        portfolio_id=DEMO_PORTFOLIO_ID,
        question="Explain current portfolio risk.",
        snapshot_ids=("SNAP-001",),
    )
