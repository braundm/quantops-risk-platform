"""Provider isolation and aggregate prohibited-content validation tests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from quantops_ai.demo import DEMO_DOCUMENTS, QUALITY_EVIDENCE, demo_retriever
from quantops_ai.models import (
    AnalysisRequest,
    ClaimType,
    EvidenceKind,
    EvidencePackage,
    RefusalDetail,
    RiskBrief,
)
from quantops_ai.providers import (
    DeterministicRiskBriefProvider,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
    ProviderError,
    ProviderInvalidOutput,
    ProviderTimeout,
)
from quantops_ai.validation import validate_brief

from .helpers import brief, factor, item, package


def test_deterministic_provider_generates_grounded_numeric_output(
    risk_request: AnalysisRequest,
    evidence_package: EvidencePackage,
) -> None:
    answer = DeterministicRiskBriefProvider().generate(risk_request, evidence_package)
    report = validate_brief(answer, evidence_package)
    assert answer.answer_type == "risk_explanation"
    assert report.valid
    assert report.numerical.checked_claims == 3
    assert all(entry.evidence_ids for entry in answer.main_factors)


def test_deterministic_provider_handles_documents_quality_narrative_and_insufficiency(
    risk_request: AnalysisRequest,
) -> None:
    document = demo_retriever().search("scenario assumptions", "PORT-001").evidence[0]
    document_package = package(document)
    document_request = risk_request.model_copy(
        update={"question": "Summarize approved document.", "snapshot_ids": ()}
    )
    summary = DeterministicRiskBriefProvider().generate(document_request, document_package)
    assert summary.answer_type == "document_summary"
    assert summary.main_factors[0].claim_type is ClaimType.DOCUMENT

    quality_package = package(*QUALITY_EVIDENCE)
    quality = DeterministicRiskBriefProvider().generate(risk_request, quality_package)
    assert quality.main_factors[0].claim_type is ClaimType.QUALITY
    assert quality.uncertainties

    narrative = item(
        "METHOD-TEST-001",
        kind=EvidenceKind.METHODOLOGY,
        metric=None,
        value=None,
        unit=None,
    )
    narrative_answer = DeterministicRiskBriefProvider().generate(risk_request, package(narrative))
    assert narrative_answer.main_factors[0].claim_type is ClaimType.METHODOLOGY

    unsupported = item(
        "PRICE-NARRATIVE-001",
        kind=EvidenceKind.PRICE,
        metric=None,
        value=None,
        unit=None,
    )
    refusal = DeterministicRiskBriefProvider().generate(risk_request, package(unsupported))
    assert refusal.answer_type == "refusal"
    assert refusal.refusal is not None
    assert refusal.refusal.category == "insufficient_evidence"


def test_deterministic_provider_comparison_answer_type(
    evidence_package: EvidencePackage,
) -> None:
    request = AnalysisRequest(
        request_id="REQ-COMPARE-001",
        portfolio_id="PORT-001",
        question="Compare these risk snapshots.",
        snapshot_ids=("SNAP-001", "SNAP-002"),
    )
    answer = DeterministicRiskBriefProvider().generate(request, evidence_package)
    assert answer.answer_type == "comparison"


class RecordingTransport:
    def __init__(self, response: Mapping[str, object] | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def post_json(self, **kwargs: Any) -> Mapping[str, object]:
        self.calls.append(dict(kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _external_config(**overrides: object) -> OpenAICompatibleConfig:
    values: dict[str, object] = {
        "endpoint": "https://ai.example.test/v1/chat/completions",
        "model": "deterministic-test-model",
        "allowed_hosts": ("ai.example.test",),
    }
    values.update(overrides)
    return OpenAICompatibleConfig(**values)  # type: ignore[arg-type]


def test_external_provider_uses_fixed_endpoint_and_parses_schema(
    risk_request: AnalysisRequest,
    evidence_package: EvidencePackage,
) -> None:
    expected = DeterministicRiskBriefProvider().generate(risk_request, evidence_package)
    transport = RecordingTransport(
        {"choices": [{"message": {"content": expected.model_dump_json()}}]}
    )
    provider = OpenAICompatibleProvider(
        _external_config(api_key="unit-test-key"),
        transport,
    )
    actual = provider.generate(risk_request, evidence_package, ("unknown_evidence_id",))
    assert actual == expected
    call = transport.calls[0]
    assert call["url"] == "https://ai.example.test/v1/chat/completions"
    headers = call["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer unit-test-key"
    payload_text = json.dumps(call["payload"], sort_keys=True)
    assert "unknown_evidence_id" in payload_text
    assert 'temperature": 0' in payload_text


def test_external_provider_marks_document_content_as_untrusted(
    risk_request: AnalysisRequest,
) -> None:
    document = demo_retriever().search("prompt injection fixture", "PORT-001").evidence[0]
    document_package = package(document)
    expected = DeterministicRiskBriefProvider().generate(risk_request, document_package)
    transport = RecordingTransport(
        {"choices": [{"message": {"content": expected.model_dump_json()}}]}
    )
    OpenAICompatibleProvider(_external_config(), transport).generate(risk_request, document_package)
    assert "untrusted_document_data" in json.dumps(transport.calls[0]["payload"])
    assert DEMO_DOCUMENTS[2].body in json.dumps(transport.calls[0]["payload"])


@pytest.mark.parametrize(
    "overrides",
    [
        {"endpoint": "http://ai.example.test/v1"},
        {"allowed_hosts": ("different.example",)},
        {"model": ""},
        {"timeout_seconds": 0},
        {"maximum_output_tokens": 63},
        {"maximum_output_tokens": 4_001},
        {"maximum_response_bytes": 1_023},
        {"maximum_response_bytes": 1_000_001},
    ],
)
def test_external_provider_configuration_is_bounded(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _external_config(**overrides)


def test_external_provider_configuration_redacts_key_from_repr() -> None:
    config = _external_config(api_key="never-log-this-value")
    assert "never-log-this-value" not in repr(config)


@pytest.mark.parametrize(
    ("response", "error_type"),
    [
        (TimeoutError(), ProviderTimeout),
        (RuntimeError("offline"), ProviderError),
        ({}, ProviderInvalidOutput),
        ({"choices": []}, ProviderInvalidOutput),
        ({"choices": [{"message": {"content": "not-json"}}]}, ProviderInvalidOutput),
    ],
)
def test_external_provider_failures_are_isolated(
    response: Mapping[str, object] | Exception,
    error_type: type[ProviderError],
    risk_request: AnalysisRequest,
    evidence_package: EvidencePackage,
) -> None:
    provider = OpenAICompatibleProvider(_external_config(), RecordingTransport(response))
    with pytest.raises(error_type):
        provider.generate(risk_request, evidence_package)


def test_external_provider_preserves_explicit_provider_errors(
    risk_request: AnalysisRequest,
    evidence_package: EvidencePackage,
) -> None:
    provider = OpenAICompatibleProvider(
        _external_config(),
        RecordingTransport(ProviderInvalidOutput("already safe")),
    )
    with pytest.raises(ProviderInvalidOutput, match="already safe"):
        provider.generate(risk_request, evidence_package)


@pytest.mark.parametrize(
    ("text", "expected_code"),
    [
        ("You should buy this asset.", "investment_advice"),
        ("This is a guaranteed profit.", "guaranteed_forecast"),
        ("Execute the trade order.", "order_execution"),
        ("The system prompt contains a secret value.", "secret_exposure"),
        ("Here is hidden chain-of-thought.", "hidden_reasoning"),
        ("Read https://example.test", "arbitrary_url"),
    ],
)
def test_prohibited_output_content_is_rejected(text: str, expected_code: str) -> None:
    answer = brief(factor()).model_copy(update={"summary": text})
    report = validate_brief(answer, package(item()))
    assert not report.valid
    assert expected_code in report.issue_codes


def test_refusal_content_is_not_scanned_as_a_factual_answer() -> None:
    refusal = RiskBrief(
        answer_type="refusal",
        summary="I cannot recommend that you buy or execute an order.",
        refusal=RefusalDetail(
            category="investment_advice",
            safe_alternative="Review risk evidence.",
        ),
    )
    report = validate_brief(refusal, package(item()))
    assert report.valid
