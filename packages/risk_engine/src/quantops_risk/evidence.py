"""Deterministic evidence manifests built outside numerical functions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from .exceptions import InvalidInputError
from .methodology import METHODOLOGY_VERSION


def _json_default(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    raise TypeError(f"unsupported evidence payload type: {type(value).__name__}")


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=_json_default,
        )
    except (TypeError, ValueError) as exc:
        raise InvalidInputError("evidence payload must be canonically serializable") from exc


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    key: str
    source_kind: str
    as_of: str
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class EvidenceManifest:
    evidence_id: str
    items: tuple[EvidenceItem, ...]
    calculation_parameters: tuple[tuple[str, str], ...]
    methodology_version: str = METHODOLOGY_VERSION

    def to_json(self) -> str:
        return _canonical_json(
            {
                "calculation_parameters": list(self.calculation_parameters),
                "evidence_id": self.evidence_id,
                "items": [
                    {
                        "as_of": item.as_of,
                        "key": item.key,
                        "payload_sha256": item.payload_sha256,
                        "source_kind": item.source_kind,
                    }
                    for item in self.items
                ],
                "methodology_version": self.methodology_version,
            }
        )


def evidence_item(*, key: str, source_kind: str, as_of: str, payload: object) -> EvidenceItem:
    """Hash one canonical source payload without assigning time- or UUID-based IDs."""

    if not key.strip() or not source_kind.strip() or not as_of.strip():
        raise InvalidInputError("evidence key, source_kind, and as_of must be non-empty")
    digest = hashlib.sha256(_canonical_json(payload).encode()).hexdigest()
    return EvidenceItem(key.strip(), source_kind.strip(), as_of.strip(), digest)


def build_evidence_manifest(
    items: Sequence[EvidenceItem], *, parameters: Mapping[str, object]
) -> EvidenceManifest:
    """Build a content-addressed, ordering-independent evidence manifest."""

    ordered_items = tuple(sorted(items, key=lambda item: (item.key, item.source_kind, item.as_of)))
    identities = [(item.key, item.source_kind, item.as_of) for item in ordered_items]
    if len(set(identities)) != len(identities):
        raise InvalidInputError("evidence items must have unique key/source/as_of identities")
    ordered_parameters = tuple(
        (key, _canonical_json(parameters[key])) for key in sorted(parameters)
    )
    canonical = _canonical_json(
        {
            "items": [
                [item.key, item.source_kind, item.as_of, item.payload_sha256]
                for item in ordered_items
            ],
            "methodology_version": METHODOLOGY_VERSION,
            "parameters": ordered_parameters,
        }
    )
    evidence_id = "evd_" + hashlib.sha256(canonical.encode()).hexdigest()
    return EvidenceManifest(evidence_id, ordered_items, ordered_parameters)
