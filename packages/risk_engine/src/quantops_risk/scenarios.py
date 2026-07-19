"""Typed, immutable, deterministic hypothetical scenario revaluation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal

from ._validation import strict_decimal
from .exceptions import DuplicateInstrumentError, InvalidInputError
from .methodology import METHODOLOGY_VERSION
from .valuation import normalize_currency


def _nonempty(value: str, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInputError(f"{name} must be non-empty")
    return value.strip()


def _percentage(value: Decimal, *, name: str, allow_total_loss: bool = True) -> Decimal:
    result = strict_decimal(value, name=name)
    minimum_valid = result >= Decimal("-1") if allow_total_loss else result > Decimal("-1")
    if not minimum_valid:
        relation = "at least -1" if allow_total_loss else "greater than -1"
        raise InvalidInputError(f"{name} must be {relation}")
    return result


@dataclass(frozen=True, slots=True)
class ScenarioPosition:
    instrument_id: str
    asset_class: str
    quantity: Decimal
    price: Decimal
    price_currency: str
    base_currency: str
    fx_rate_to_base: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        _nonempty(self.instrument_id, name="instrument_id")
        _nonempty(self.asset_class, name="asset_class")
        strict_decimal(self.quantity, name="quantity")
        price = strict_decimal(self.price, name="price")
        fx_rate = strict_decimal(self.fx_rate_to_base, name="fx_rate_to_base")
        if price < 0:
            raise InvalidInputError("price must be nonnegative")
        if fx_rate <= 0:
            raise InvalidInputError("fx_rate_to_base must be positive")
        price_currency = normalize_currency(self.price_currency, name="price_currency")
        base_currency = normalize_currency(self.base_currency, name="base_currency")
        if price_currency == base_currency and fx_rate != Decimal("1"):
            raise InvalidInputError("same-currency scenario positions require an FX rate of 1")


@dataclass(frozen=True, slots=True)
class InstrumentPriceShock:
    instrument_id: str
    percentage: Decimal

    def __post_init__(self) -> None:
        _nonempty(self.instrument_id, name="instrument_id")
        _percentage(self.percentage, name="percentage")


@dataclass(frozen=True, slots=True)
class AssetClassShock:
    asset_class: str
    percentage: Decimal

    def __post_init__(self) -> None:
        _nonempty(self.asset_class, name="asset_class")
        _percentage(self.percentage, name="percentage")


@dataclass(frozen=True, slots=True)
class FXShock:
    currency: str
    percentage: Decimal

    def __post_init__(self) -> None:
        normalize_currency(self.currency, name="currency")
        _percentage(self.percentage, name="percentage", allow_total_loss=False)


@dataclass(frozen=True, slots=True)
class VolatilityMultiplier:
    multiplier: Decimal

    def __post_init__(self) -> None:
        value = strict_decimal(self.multiplier, name="multiplier")
        if value <= 0:
            raise InvalidInputError("volatility multiplier must be positive")


@dataclass(frozen=True, slots=True)
class CorrelationOverride:
    left_instrument_id: str
    right_instrument_id: str
    correlation: Decimal

    def __post_init__(self) -> None:
        left = _nonempty(self.left_instrument_id, name="left_instrument_id")
        right = _nonempty(self.right_instrument_id, name="right_instrument_id")
        if left == right:
            raise InvalidInputError("correlation override requires two different instruments")
        value = strict_decimal(self.correlation, name="correlation")
        if not Decimal("-1") <= value <= Decimal("1"):
            raise InvalidInputError("correlation must be between -1 and 1")

    @property
    def canonical_pair(self) -> tuple[str, str]:
        left, right = sorted((self.left_instrument_id, self.right_instrument_id))
        return left, right


type ScenarioShock = (
    InstrumentPriceShock | AssetClassShock | FXShock | VolatilityMultiplier | CorrelationOverride
)


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    key: str
    title: str
    version: str
    shocks: tuple[ScenarioShock, ...]
    assumptions: tuple[str, ...]
    hypothetical: bool = True

    def __post_init__(self) -> None:
        _nonempty(self.key, name="key")
        _nonempty(self.title, name="title")
        if not re.fullmatch(r"\d+\.\d+\.\d+", self.version):
            raise InvalidInputError("scenario version must be semantic version x.y.z")
        if not isinstance(self.shocks, tuple):
            raise InvalidInputError("scenario shocks must be an immutable tuple")
        if not self.assumptions or not isinstance(self.assumptions, tuple):
            raise InvalidInputError("scenario assumptions must be an immutable non-empty tuple")
        if not self.shocks:
            raise InvalidInputError("scenario must contain at least one shock")
        allowed_shock_types = (
            InstrumentPriceShock,
            AssetClassShock,
            FXShock,
            VolatilityMultiplier,
            CorrelationOverride,
        )
        if any(not isinstance(shock, allowed_shock_types) for shock in self.shocks):
            raise InvalidInputError("scenario contains an unsupported shock type")
        if any(not isinstance(item, str) or not item.strip() for item in self.assumptions):
            raise InvalidInputError("scenario assumptions must be explicit and non-empty")
        if self.hypothetical is not True:
            raise InvalidInputError("risk-engine scenarios must be labelled hypothetical")


@dataclass(frozen=True, slots=True)
class ScenarioPositionResult:
    instrument_id: str
    base_market_value: Decimal
    stressed_market_value: Decimal
    pnl: Decimal
    applied_price_multiplier: Decimal
    applied_fx_multiplier: Decimal


@dataclass(frozen=True, slots=True)
class ScenarioRun:
    scenario_key: str
    scenario_version: str
    deterministic_run_id: str
    base_currency: str
    base_value: Decimal
    stressed_value: Decimal
    pnl: Decimal
    positions: tuple[ScenarioPositionResult, ...]
    volatility_multiplier: Decimal
    correlation_overrides: tuple[CorrelationOverride, ...]
    assumptions: tuple[str, ...]
    hypothetical: bool = True
    methodology_version: str = METHODOLOGY_VERSION


def _shock_sort_key(shock: ScenarioShock) -> tuple[object, ...]:
    if isinstance(shock, InstrumentPriceShock):
        return (0, shock.instrument_id, str(shock.percentage))
    if isinstance(shock, AssetClassShock):
        return (1, shock.asset_class, str(shock.percentage))
    if isinstance(shock, FXShock):
        return (2, shock.currency, str(shock.percentage))
    if isinstance(shock, VolatilityMultiplier):
        return (3, str(shock.multiplier))
    left, right = shock.canonical_pair
    return (4, left, right, str(shock.correlation))


def _canonical_shock(shock: ScenarioShock) -> tuple[str, ...]:
    if isinstance(shock, InstrumentPriceShock):
        return "instrument_price", shock.instrument_id, str(shock.percentage)
    if isinstance(shock, AssetClassShock):
        return "asset_class", shock.asset_class, str(shock.percentage)
    if isinstance(shock, FXShock):
        return "fx", normalize_currency(shock.currency, name="currency"), str(shock.percentage)
    if isinstance(shock, VolatilityMultiplier):
        return "volatility_multiplier", str(shock.multiplier)
    left, right = shock.canonical_pair
    return "correlation_override", left, right, str(shock.correlation)


def run_scenario(
    definition: ScenarioDefinition, positions: tuple[ScenarioPosition, ...]
) -> ScenarioRun:
    """Apply a definition in canonical phase order without mutating inputs.

    Price and FX shocks compound multiplicatively. Volatility and correlation changes
    are analytical outputs; they do not manufacture a P&L path. Duplicate correlation
    overrides are rejected rather than silently applying last-write-wins behavior.
    """

    ordered_positions = tuple(sorted(positions, key=lambda item: item.instrument_id))
    identifiers = tuple(item.instrument_id for item in ordered_positions)
    if len(set(identifiers)) != len(identifiers):
        raise DuplicateInstrumentError("scenario positions contain a duplicate instrument_id")
    if not ordered_positions:
        raise InvalidInputError("scenario requires at least one position")
    base_currencies = {
        normalize_currency(item.base_currency, name="base_currency") for item in ordered_positions
    }
    if len(base_currencies) != 1:
        raise InvalidInputError("scenario positions must share one base currency")
    base_currency = next(iter(base_currencies))

    price_multipliers = {identifier: Decimal("1") for identifier in identifiers}
    fx_multipliers = {identifier: Decimal("1") for identifier in identifiers}
    volatility_multiplier = Decimal("1")
    correlations: dict[tuple[str, str], CorrelationOverride] = {}
    known_asset_classes = {position.asset_class for position in ordered_positions}
    known_currencies = {
        normalize_currency(position.price_currency, name="price_currency")
        for position in ordered_positions
    }

    for shock in sorted(definition.shocks, key=_shock_sort_key):
        if isinstance(shock, InstrumentPriceShock):
            if shock.instrument_id not in price_multipliers:
                raise InvalidInputError(f"unknown scenario instrument: {shock.instrument_id}")
            price_multipliers[shock.instrument_id] *= Decimal("1") + shock.percentage
        elif isinstance(shock, AssetClassShock):
            if shock.asset_class not in known_asset_classes:
                raise InvalidInputError(f"unknown scenario asset class: {shock.asset_class}")
            for position in ordered_positions:
                if position.asset_class == shock.asset_class:
                    price_multipliers[position.instrument_id] *= Decimal("1") + shock.percentage
        elif isinstance(shock, FXShock):
            currency = normalize_currency(shock.currency, name="currency")
            if currency == base_currency:
                raise InvalidInputError("cannot apply an FX shock to the portfolio base currency")
            if currency not in known_currencies:
                raise InvalidInputError(f"unknown scenario currency: {currency}")
            for position in ordered_positions:
                if normalize_currency(position.price_currency, name="price_currency") == currency:
                    fx_multipliers[position.instrument_id] *= Decimal("1") + shock.percentage
        elif isinstance(shock, VolatilityMultiplier):
            volatility_multiplier *= shock.multiplier
        else:
            pair = shock.canonical_pair
            if not set(pair).issubset(set(identifiers)):
                raise InvalidInputError(f"correlation override references unknown pair: {pair}")
            if pair in correlations:
                raise InvalidInputError(f"duplicate correlation override for pair: {pair}")
            correlations[pair] = CorrelationOverride(pair[0], pair[1], shock.correlation)

    results: list[ScenarioPositionResult] = []
    for position in ordered_positions:
        base_value = position.quantity * position.price * position.fx_rate_to_base
        stressed_value = (
            base_value
            * price_multipliers[position.instrument_id]
            * fx_multipliers[position.instrument_id]
        )
        results.append(
            ScenarioPositionResult(
                position.instrument_id,
                base_value,
                stressed_value,
                stressed_value - base_value,
                price_multipliers[position.instrument_id],
                fx_multipliers[position.instrument_id],
            )
        )
    position_results = tuple(results)
    base_total = sum((item.base_market_value for item in position_results), Decimal("0"))
    stressed_total = sum((item.stressed_market_value for item in position_results), Decimal("0"))
    ordered_correlations = tuple(correlations[pair] for pair in sorted(correlations))
    canonical = {
        "base_currency": base_currency,
        "methodology_version": METHODOLOGY_VERSION,
        "definition": {
            "assumptions": list(definition.assumptions),
            "hypothetical": definition.hypothetical,
            "shocks": [
                list(_canonical_shock(shock))
                for shock in sorted(definition.shocks, key=_shock_sort_key)
            ],
            "title": definition.title,
        },
        "positions": [
            {
                "base": str(item.base_market_value),
                "id": item.instrument_id,
                "stressed": str(item.stressed_market_value),
            }
            for item in position_results
        ],
        "scenario_key": definition.key,
        "scenario_version": definition.version,
        "volatility_multiplier": str(volatility_multiplier),
        "correlations": [
            [item.left_instrument_id, item.right_instrument_id, str(item.correlation)]
            for item in ordered_correlations
        ],
    }
    run_id = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return ScenarioRun(
        definition.key,
        definition.version,
        run_id,
        base_currency,
        base_total,
        stressed_total,
        stressed_total - base_total,
        position_results,
        volatility_multiplier,
        ordered_correlations,
        definition.assumptions,
    )


SYSTEM_SCENARIOS: tuple[ScenarioDefinition, ...] = (
    ScenarioDefinition(
        "equity_selloff_15pct",
        "Equity selloff 15%",
        "1.0.0",
        (AssetClassShock("equity_index", Decimal("-0.15")),),
        ("all equity prices fall 15% instantaneously", "no position rebalancing"),
    ),
    ScenarioDefinition(
        "oil_spike_25pct",
        "Oil spike 25%",
        "1.0.0",
        (InstrumentPriceShock("QWTI", Decimal("0.25")),),
        ("QWTI rises 25% instantaneously", "hypothetical engineering scenario"),
    ),
    ScenarioDefinition(
        "gold_down_10pct",
        "Gold down 10%",
        "1.0.0",
        (InstrumentPriceShock("QGOLD", Decimal("-0.10")),),
        ("QGOLD falls 10% instantaneously", "hypothetical engineering scenario"),
    ),
    ScenarioDefinition(
        "cross_asset_correlation_breakdown",
        "Cross-asset correlation breakdown",
        "1.0.0",
        (
            CorrelationOverride("QTECH", "QGOLD", Decimal("0.80")),
            CorrelationOverride("QTECH", "QWTI", Decimal("0.80")),
            VolatilityMultiplier(Decimal("1.25")),
        ),
        (
            "selected cross-asset correlations become +0.80",
            "volatility scales 1.25x for analytical comparison",
            "correlation is not a deterministic revaluation P&L",
        ),
    ),
    ScenarioDefinition(
        "combined_liquidity_stress",
        "Combined liquidity stress",
        "1.0.0",
        (
            AssetClassShock("equity_index", Decimal("-0.20")),
            InstrumentPriceShock("QWTI", Decimal("-0.15")),
            InstrumentPriceShock("QGOLD", Decimal("-0.05")),
            VolatilityMultiplier(Decimal("1.80")),
            CorrelationOverride("QTECH", "QGOLD", Decimal("0.70")),
        ),
        (
            "instantaneous deterministic price shocks",
            "volatility scales 1.80x for analytical comparison",
            "positions and quantities remain unchanged",
        ),
    ),
)


def system_scenario(key: str) -> ScenarioDefinition:
    """Resolve a versioned built-in scenario by stable key."""

    try:
        return next(item for item in SYSTEM_SCENARIOS if item.key == key)
    except StopIteration as exc:
        raise InvalidInputError(f"unknown system scenario: {key}") from exc
