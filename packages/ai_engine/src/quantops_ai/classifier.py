"""Deterministic request classification and safe refusal construction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from quantops_ai.models import AnalysisRequest, RefusalDetail, RiskBrief


class RequestClass(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"
    UNSAFE = "unsafe"


@dataclass(frozen=True, slots=True)
class Classification:
    request_class: RequestClass
    category: str
    reason: str
    safe_alternative: str


_RULES: tuple[tuple[RequestClass, str, re.Pattern[str], str], ...] = (
    (
        RequestClass.UNSAFE,
        "order_execution",
        re.compile(r"\b(place|execute|submit|route|cancel)\b.{0,24}\b(order|trade)\b", re.I),
        "I can explain current exposures and scenario impacts without executing anything.",
    ),
    (
        RequestClass.UNSAFE,
        "secret_or_hidden_prompt",
        re.compile(
            r"\b(secret|api[ -]?key|password|credential|system prompt|hidden prompt|"
            r"chain[- ]of[- ]thought)\b",
            re.I,
        ),
        "I can describe the public safety controls and evidence-validation policy.",
    ),
    (
        RequestClass.UNSAFE,
        "arbitrary_url_or_browsing",
        re.compile(r"https?://|\b(fetch|browse|open)\b.{0,24}\b(url|website|internet|web)\b", re.I),
        "I can search only the approved synthetic document collection.",
    ),
    (
        RequestClass.UNSAFE,
        "prompt_injection",
        re.compile(
            r"ignore (all |any )?(previous|prior|system)|override (the )?"
            r"(rules|instructions)|developer mode|do anything now",
            re.I,
        ),
        "I can answer a supported risk question using the supplied evidence.",
    ),
    (
        RequestClass.UNSAFE,
        "excessive_context_or_tool_loop",
        re.compile(r"\b(loop|repeat|recursive|unlimited|every tool|all tools)\b", re.I),
        "I can perform one bounded risk analysis with a fixed read-only tool budget.",
    ),
    (
        RequestClass.UNSUPPORTED,
        "investment_advice",
        re.compile(
            r"\b(buy|sell|short|long)\b.{0,40}\b(recommend|should|position|stock|asset)?\b", re.I
        ),
        "I can show current exposures, risk contributions, and scenario impacts.",
    ),
    (
        RequestClass.UNSUPPORTED,
        "guaranteed_forecast",
        re.compile(
            r"\b(guarantee|certain|definitely|will)\b.{0,35}\b(price|return|profit|market|rise|fall)\b",
            re.I,
        ),
        (
            "I can explain observed risk indicators and their limitations without "
            "forecasting direction."
        ),
    ),
    (
        RequestClass.UNSUPPORTED,
        "mutation_request",
        re.compile(
            r"\b(change|modify|delete|create|update)\b.{0,35}\b(portfolio|model|pipeline|data|permission)\b",
            re.I,
        ),
        "I can inspect the current read-only risk state.",
    ),
)

_SUPPORTED = re.compile(
    r"\b(risk|volatility|contribution|concentration|scenario|quality|snapshot|var|"
    r"expected shortfall|document|methodology|exposure)\b",
    re.I,
)


def classify_request(request: AnalysisRequest) -> Classification:
    if request.portfolio_name and re.search(
        r"ignore (all |any )?(previous|prior|system)|override (the )?(rules|instructions)|"
        r"developer mode|do anything now",
        request.portfolio_name,
        re.I,
    ):
        return Classification(
            RequestClass.UNSAFE,
            "prompt_injection",
            "untrusted portfolio metadata contains an instruction-like pattern",
            "I can answer a supported risk question using the supplied evidence.",
        )
    text = " ".join(value for value in (request.question, request.portfolio_name or "") if value)
    for request_class, category, pattern, alternative in _RULES:
        if pattern.search(text):
            return Classification(
                request_class, category, f"matched bounded rule: {category}", alternative
            )
    if _SUPPORTED.search(text):
        return Classification(
            RequestClass.SUPPORTED,
            "risk_analysis",
            "request matches the supported risk-analysis scope",
            "",
        )
    return Classification(
        RequestClass.AMBIGUOUS,
        "ambiguous_request",
        "request does not identify a supported risk-analysis task",
        (
            "Ask about risk, contributions, scenarios, data quality, methodology, or "
            "approved documents."
        ),
    )


def refusal_for(classification: Classification) -> RiskBrief:
    return RiskBrief(
        answer_type="refusal",
        summary=(
            "I can provide evidence-grounded portfolio risk analysis, but I cannot fulfill "
            f"this {classification.category.replace('_', ' ')} request."
        ),
        refusal=RefusalDetail(
            category=classification.category,
            safe_alternative=classification.safe_alternative,
        ),
    )
