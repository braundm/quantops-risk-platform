"""Deterministic lexical retrieval over approved synthetic document chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from quantops_ai.models import EvidenceItem, EvidenceKind

_TOKEN = re.compile(r"[a-z0-9]{2,}", re.I)


@dataclass(frozen=True, slots=True)
class ApprovedDocumentChunk:
    evidence_id: str
    portfolio_id: str
    document_id: str
    title: str
    body: str
    section: str
    source_timestamp: datetime
    source_url: str
    publication_date: date
    approved: bool = True
    synthetic: bool = True


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    evidence: tuple[EvidenceItem, ...]
    query_tokens: tuple[str, ...]
    considered_chunks: int


class KeywordRetriever:
    def __init__(self, chunks: tuple[ApprovedDocumentChunk, ...]) -> None:
        self._chunks = chunks

    def search(
        self,
        query: str,
        portfolio_id: str,
        *,
        limit: int = 4,
        minimum_score: float = 0.15,
    ) -> RetrievalResult:
        if not 1 <= limit <= 8:
            raise ValueError("retrieval limit must be between one and eight")
        if not 0.0 <= minimum_score <= 1.0:
            raise ValueError("minimum score must be between zero and one")
        query_tokens = tuple(sorted(set(_tokens(query))))
        if not query_tokens:
            return RetrievalResult((), (), 0)
        candidates: list[tuple[float, ApprovedDocumentChunk]] = []
        considered = 0
        for chunk in self._chunks:
            if not chunk.approved or chunk.portfolio_id != portfolio_id:
                continue
            considered += 1
            document_tokens = set(_tokens(f"{chunk.title} {chunk.section} {chunk.body}"))
            overlap = len(set(query_tokens) & document_tokens)
            score = overlap / len(set(query_tokens))
            if score >= minimum_score:
                candidates.append((score, chunk))
        candidates.sort(key=lambda entry: (-entry[0], entry[1].evidence_id))
        seen: set[str] = set()
        evidence: list[EvidenceItem] = []
        for _score, chunk in candidates:
            if chunk.evidence_id in seen:
                continue
            seen.add(chunk.evidence_id)
            evidence.append(
                EvidenceItem(
                    evidence_id=chunk.evidence_id,
                    kind=EvidenceKind.DOCUMENT,
                    portfolio_id=chunk.portfolio_id,
                    source_timestamp=chunk.source_timestamp,
                    title=chunk.title,
                    content=chunk.body,
                    document_id=chunk.document_id,
                    section=chunk.section,
                    source_url=chunk.source_url,
                    publication_date=chunk.publication_date,
                    synthetic=chunk.synthetic,
                )
            )
            if len(evidence) == limit:
                break
        return RetrievalResult(tuple(evidence), query_tokens, considered)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(match.group(0).lower() for match in _TOKEN.finditer(value))
