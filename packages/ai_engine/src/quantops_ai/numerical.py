"""Unit-aware validation of authoritative numerical claims against evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from quantops_ai.models import CanonicalUnit, EvidenceItem, EvidencePackage, RiskBrief

_NUMBER = re.compile(r"^\s*\$?\s*([-+]?(?:\d+(?:,\d{3})*|\d*)(?:\.\d+)?)\s*(%|bps)?\s*$", re.I)


@dataclass(frozen=True, slots=True)
class NumericalIssue:
    code: str
    path: str
    detail: str


@dataclass(frozen=True, slots=True)
class NumericalReport:
    valid: bool
    issues: tuple[NumericalIssue, ...]
    checked_claims: int


def validate_numerical_consistency(
    brief: RiskBrief,
    package: EvidencePackage,
) -> NumericalReport:
    issues: list[NumericalIssue] = []
    checked = 0
    evidence_by_id = package.by_id()
    for index, factor in enumerate(brief.main_factors):
        path = f"main_factors[{index}]"
        supplied = (factor.metric, factor.value, factor.unit)
        if all(value is None for value in supplied):
            continue
        if any(value is None for value in supplied):
            issues.append(
                NumericalIssue(
                    "incomplete_numeric_claim", path, "metric, value, and unit are required"
                )
            )
            continue
        checked += 1
        metric = cast(str, factor.metric)
        value = cast(str, factor.value)
        unit = cast(CanonicalUnit, factor.unit)
        parsed = _parse_display_value(value, unit)
        if parsed is None:
            issues.append(NumericalIssue("invalid_numeric_value", path, value))
            continue
        candidates = tuple(
            evidence_by_id[evidence_id]
            for evidence_id in factor.evidence_ids
            if evidence_id in evidence_by_id and evidence_by_id[evidence_id].metric_name == metric
        )
        if not candidates:
            issues.append(
                NumericalIssue(
                    "missing_metric_evidence",
                    path,
                    f"no cited evidence contains {metric}",
                )
            )
            continue
        if not _compatible_units(unit, candidates):
            issues.append(
                NumericalIssue("incompatible_unit", path, f"unit {unit.value} is incompatible")
            )
            continue
        if not any(_within_rounding_tolerance(parsed, unit, evidence) for evidence in candidates):
            issues.append(
                NumericalIssue(
                    "numerical_mismatch",
                    path,
                    "displayed value is outside evidence rounding tolerance",
                )
            )
    return NumericalReport(not issues, tuple(issues), checked)


def _parse_display_value(value: str, declared_unit: CanonicalUnit) -> Decimal | None:
    match = _NUMBER.fullmatch(value)
    if match is None or not match.group(1):
        return None
    suffix = (match.group(2) or "").lower()
    if suffix == "%" and declared_unit is not CanonicalUnit.PERCENT:
        return None
    if suffix == "bps" and declared_unit is not CanonicalUnit.BASIS_POINTS:
        return None
    return Decimal(match.group(1).replace(",", ""))


def _compatible_units(unit: CanonicalUnit, evidence: tuple[EvidenceItem, ...]) -> bool:
    family = _unit_family(unit)
    return all(
        item.canonical_value is not None
        and item.canonical_unit is not None
        and _unit_family(item.canonical_unit) == family
        for item in evidence
    )


def _unit_family(unit: CanonicalUnit) -> str:
    if unit in {CanonicalUnit.RATIO, CanonicalUnit.PERCENT, CanonicalUnit.BASIS_POINTS}:
        return "ratio"
    return unit.value


def _within_rounding_tolerance(
    displayed: Decimal,
    display_unit: CanonicalUnit,
    evidence: EvidenceItem,
) -> bool:
    canonical_value = cast(Decimal, evidence.canonical_value)
    canonical_unit = cast(CanonicalUnit, evidence.canonical_unit)
    displayed_base = _to_base(displayed, display_unit)
    evidence_base = _to_base(canonical_value, canonical_unit)
    quantum = Decimal(1).scaleb(-evidence.display_precision)
    base_quantum = abs(_to_base(quantum, display_unit))
    tolerance = base_quantum / Decimal(2) + Decimal("1e-12")
    return abs(displayed_base - evidence_base) <= tolerance


def _to_base(value: Decimal, unit: CanonicalUnit) -> Decimal:
    if unit is CanonicalUnit.PERCENT:
        return value / Decimal(100)
    if unit is CanonicalUnit.BASIS_POINTS:
        return value / Decimal(10_000)
    return value
