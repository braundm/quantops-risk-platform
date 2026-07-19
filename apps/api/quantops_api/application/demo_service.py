"""Framework-independent deterministic application service for the no-database demo."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from threading import RLock
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from quantops_contracts import RiskQualityStatus
from quantops_domain import (
    AssetClass,
    AuditAction,
    AuditEvent,
    Currency,
    DomainValidationError,
    Instrument,
    Portfolio,
    Position,
)
from quantops_risk import (
    METHODOLOGY_VERSION,
    SYSTEM_SCENARIOS,
    AssetClassShock,
    CorrelationOverride,
    FXShock,
    InstrumentPriceShock,
    PositionInput,
    ScenarioDefinition,
    ScenarioPosition,
    ScenarioRun,
    VolatilityMultiplier,
    arithmetic_returns,
    build_evidence_manifest,
    evidence_item,
    herfindahl_hirschman,
    historical_expected_shortfall,
    historical_var,
    maximum_drawdown,
    parametric_var_from_returns,
    run_scenario,
    sample_volatility,
    value_portfolio,
)
from quantops_risk.scenarios import ScenarioShock

from quantops_api.application.errors import ConflictError, NotFoundError

DEMO_AS_OF = datetime(2024, 12, 31, 21, 2, tzinfo=UTC)
DEMO_PORTFOLIO_ID = UUID("11111111-1111-4111-8111-111111111111")
_DEMO_NAMESPACE = uuid5(NAMESPACE_URL, "https://quantops.dev/deterministic-demo/v1")
_MONEY_QUANTUM = Decimal("0.0000000001")


@dataclass(frozen=True, slots=True)
class PriceBarRecord:
    instrument_id: UUID
    observed_at: datetime
    interval: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    currency: str
    source: str = "quantops-synthetic-v1"
    quality_status: str = "accepted"
    is_synthetic: bool = True


@dataclass(frozen=True, slots=True)
class RiskSnapshotRecord:
    id: UUID
    portfolio_id: UUID
    portfolio_version: int
    as_of: datetime
    created_at: datetime
    methodology_version: str
    window_start: datetime
    window_end: datetime
    confidence_level: float
    base_currency: str
    portfolio_value: Decimal
    daily_pnl: Decimal
    volatility_annualized: float | None
    var_historical: float | None
    var_parametric: float | None
    expected_shortfall: float | None
    max_drawdown: float | None
    data_completeness: float
    quality_status: str
    observation_count: int
    concentration_hhi: float | None
    largest_absolute_weight: float | None
    evidence_id: str
    assumptions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScenarioRunRecord:
    id: str
    portfolio_id: UUID
    portfolio_version: int
    run_at: datetime
    result: ScenarioRun


@dataclass(frozen=True, slots=True)
class PipelineRunRecord:
    id: UUID
    pipeline_name: str
    code_version: str
    started_at: datetime
    finished_at: datetime
    status: str
    records_read: int
    accepted: int
    updated: int
    duplicated: int
    rejected: int
    late: int
    watermark_after: datetime
    is_synthetic: bool = True


@dataclass(frozen=True, slots=True)
class DataQualityIssueRecord:
    id: UUID
    pipeline_run_id: UUID
    entity_type: str
    entity_reference: str
    rule_code: str
    severity: str
    observed_value: str
    expected_constraint: str
    created_at: datetime
    resolved_at: datetime | None
    intentional_fixture: bool = True


@dataclass(frozen=True, slots=True)
class CustomShockCommand:
    kind: str
    target: str
    value: Decimal


@dataclass(frozen=True, slots=True)
class IdempotentResult[T]:
    value: T
    replayed: bool


def _stable_uuid(kind: str, identity: str) -> UUID:
    return uuid5(_DEMO_NAMESPACE, f"{kind}:{identity}")


def _business_dates_ending(end: date, count: int) -> tuple[date, ...]:
    values: list[date] = []
    current = end
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current)
        current -= timedelta(days=1)
    return tuple(reversed(values))


def _scaled_prices(
    target: Decimal,
    returns: Sequence[Decimal],
) -> tuple[Decimal, ...]:
    raw = [Decimal("1")]
    for item in returns:
        raw.append(raw[-1] * (Decimal("1") + item))
    scale = target / raw[-1]
    result = [(item * scale).quantize(_MONEY_QUANTUM) for item in raw]
    result[-1] = target
    return tuple(result)


def _canonical_fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


class DemoQuantOpsService:
    """Deterministic mutable demo state behind application-oriented methods."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._event_sequence = 0
        self._portfolio_sequence = 0
        self._instruments = self._build_instruments()
        self._prices = self._build_prices()
        portfolio, positions = self._build_demo_portfolio()
        self._portfolios: dict[UUID, Portfolio] = {portfolio.id: portfolio}
        self._positions: dict[UUID, tuple[Position, ...]] = {portfolio.id: positions}
        self._snapshots: dict[UUID, RiskSnapshotRecord] = {}
        self._snapshot_history: dict[UUID, list[UUID]] = {portfolio.id: []}
        self._evidence: dict[UUID, dict[str, Any]] = {}
        self._scenario_definitions = {item.key: item for item in SYSTEM_SCENARIOS}
        self._scenario_runs: dict[str, ScenarioRunRecord] = {}
        self._audit_events: list[AuditEvent] = []
        self._idempotency: dict[tuple[str, str], tuple[str, object]] = {}
        self._pipeline_runs, self._quality_issues = self._build_pipeline_records()
        self._record_audit(
            AuditAction.DATA_IMPORTED,
            "pipeline_run",
            self._pipeline_runs[0].id,
            {"dataset": "quantops-synthetic-v1", "records": 164},
        )
        self._compute_snapshot(portfolio.id)

    @staticmethod
    def _build_instruments() -> dict[UUID, Instrument]:
        specs = (
            ("QTECH", "QuantOps Technology Index", AssetClass.EQUITY_INDEX, 10),
            ("QGOLD", "QuantOps Gold Reference", AssetClass.COMMODITY, 10),
            ("QWTI", "QuantOps Crude Oil Reference", AssetClass.COMMODITY, 10),
            ("QCASH", "QuantOps USD Cash", AssetClass.CASH, 4),
        )
        values: dict[UUID, Instrument] = {}
        for symbol, name, asset_class, scale in specs:
            instrument = Instrument.create(
                instrument_id=_stable_uuid("instrument", symbol),
                source="quantops-synthetic-v1",
                symbol=symbol,
                name=name,
                asset_class=asset_class,
                quote_currency="USD",
                price_scale=scale,
                timezone="UTC",
                calendar="WEEKDAY",
                is_demo=True,
                now=DEMO_AS_OF - timedelta(days=180),
                metadata={"synthetic": True, "dataset_version": "1.0.0"},
            )
            values[instrument.id] = instrument
        return values

    def _instrument_by_symbol(self, symbol: str) -> Instrument:
        return next(item for item in self._instruments.values() if item.symbol.value == symbol)

    def _build_prices(self) -> dict[UUID, tuple[PriceBarRecord, ...]]:
        dates = _business_dates_ending(DEMO_AS_OF.date(), 41)
        patterns: dict[str, tuple[Decimal, ...]] = {
            "QTECH": tuple(
                Decimal(value)
                for value in (
                    "0.006",
                    "-0.004",
                    "0.009",
                    "0.003",
                    "-0.007",
                    "0.005",
                    "0.011",
                    "-0.003",
                    "0.004",
                    "-0.012",
                    "0.006",
                    "0.002",
                    "-0.005",
                    "0.008",
                    "-0.004",
                    "0.007",
                    "0.003",
                    "-0.009",
                    "0.005",
                    "0.010",
                    "-0.006",
                    "0.004",
                    "-0.003",
                    "0.007",
                    "-0.055",
                    "-0.028",
                    "0.018",
                    "-0.012",
                    "0.021",
                    "0.014",
                    "-0.008",
                    "0.012",
                    "0.006",
                    "-0.004",
                    "0.009",
                    "0.003",
                    "-0.006",
                    "0.008",
                    "0.004",
                    "-0.002",
                )
            ),
            "QGOLD": tuple(
                Decimal(value)
                for value in (
                    "-0.002",
                    "0.004",
                    "-0.003",
                    "0.002",
                    "0.006",
                    "-0.001",
                    "0.003",
                    "0.004",
                    "-0.002",
                    "0.005",
                    "-0.004",
                    "0.003",
                    "0.002",
                    "-0.001",
                    "0.004",
                    "-0.003",
                    "0.002",
                    "0.005",
                    "-0.002",
                    "0.003",
                    "0.006",
                    "-0.004",
                    "0.002",
                    "0.001",
                    "0.018",
                    "0.011",
                    "-0.006",
                    "0.009",
                    "-0.004",
                    "0.002",
                    "0.005",
                    "-0.003",
                    "0.004",
                    "0.002",
                    "-0.001",
                    "0.003",
                    "-0.002",
                    "0.004",
                    "0.001",
                    "0.002",
                )
            ),
            "QWTI": tuple(
                Decimal(value)
                for value in (
                    "0.010",
                    "-0.012",
                    "0.016",
                    "-0.008",
                    "0.013",
                    "-0.019",
                    "0.009",
                    "0.015",
                    "-0.011",
                    "0.007",
                    "-0.014",
                    "0.018",
                    "-0.006",
                    "0.012",
                    "-0.017",
                    "0.011",
                    "0.006",
                    "-0.010",
                    "0.014",
                    "-0.009",
                    "0.019",
                    "-0.013",
                    "0.008",
                    "-0.005",
                    "-0.042",
                    "-0.031",
                    "0.025",
                    "-0.018",
                    "0.029",
                    "0.017",
                    "-0.012",
                    "0.021",
                    "-0.009",
                    "0.013",
                    "-0.007",
                    "0.016",
                    "-0.011",
                    "0.014",
                    "0.006",
                    "-0.008",
                )
            ),
            "QCASH": (Decimal("0"),) * 40,
        }
        targets = {
            "QTECH": Decimal("582.2889139"),
            "QGOLD": Decimal("3791.088413"),
            "QWTI": Decimal("74.5039828"),
            "QCASH": Decimal("1"),
        }
        result: dict[UUID, tuple[PriceBarRecord, ...]] = {}
        for symbol, pattern in patterns.items():
            instrument = self._instrument_by_symbol(symbol)
            closes = _scaled_prices(targets[symbol], pattern)
            bars: list[PriceBarRecord] = []
            for index, (day, close) in enumerate(zip(dates, closes, strict=True)):
                opening = closes[index - 1] if index else close
                high = (max(opening, close) * Decimal("1.003")).quantize(_MONEY_QUANTUM)
                low = (min(opening, close) * Decimal("0.997")).quantize(_MONEY_QUANTUM)
                if symbol == "QCASH":
                    opening = high = low = close = Decimal("1")
                bars.append(
                    PriceBarRecord(
                        instrument_id=instrument.id,
                        observed_at=datetime(
                            day.year,
                            day.month,
                            day.day,
                            21,
                            2,
                            tzinfo=UTC,
                        ),
                        interval="1d",
                        open=opening,
                        high=high,
                        low=low,
                        close=close,
                        volume=Decimal(0 if symbol == "QCASH" else 1_000_000 + index * 1_000),
                        currency="USD",
                    )
                )
            result[instrument.id] = tuple(bars)
        return result

    def _build_demo_portfolio(self) -> tuple[Portfolio, tuple[Position, ...]]:
        portfolio = Portfolio.create(
            portfolio_id=DEMO_PORTFOLIO_ID,
            name="QuantOps Multi-Asset Demo",
            base_currency="USD",
            description="Deterministic synthetic equity-index, gold, oil, and cash exposures.",
            is_demo=True,
            now=DEMO_AS_OF - timedelta(days=180),
        )
        specifications = (
            ("QTECH", Decimal("1000"), Decimal("510")),
            ("QGOLD", Decimal("100"), Decimal("3500")),
            ("QWTI", Decimal("3000"), Decimal("70")),
            ("QCASH", Decimal("318298.7465"), Decimal("1")),
        )
        positions = tuple(
            Position.create(
                position_id=_stable_uuid("position", f"{portfolio.id}:{symbol}"),
                portfolio_id=portfolio.id,
                instrument_id=self._instrument_by_symbol(symbol).id,
                quantity=quantity,
                average_cost=cost,
                currency="USD",
                as_of=DEMO_AS_OF,
                tags={"book": "demo", "synthetic": "true"},
            )
            for symbol, quantity, cost in specifications
        )
        return portfolio, positions

    @staticmethod
    def _build_pipeline_records() -> tuple[
        tuple[PipelineRunRecord, ...], tuple[DataQualityIssueRecord, ...]
    ]:
        run_id = _stable_uuid("pipeline", "synthetic-market-seed-v1")
        run = PipelineRunRecord(
            id=run_id,
            pipeline_name="synthetic-market-seed",
            code_version="0.1.0",
            started_at=DEMO_AS_OF - timedelta(minutes=2),
            finished_at=DEMO_AS_OF - timedelta(minutes=1),
            status="succeeded",
            records_read=165,
            accepted=164,
            updated=0,
            duplicated=1,
            rejected=0,
            late=0,
            watermark_after=DEMO_AS_OF,
        )
        issue = DataQualityIssueRecord(
            id=_stable_uuid("quality", "intentional-duplicate-v1"),
            pipeline_run_id=run_id,
            entity_type="price_bar",
            entity_reference="fixture:duplicate:QTECH",
            rule_code="DUPLICATE_SOURCE_EVENT",
            severity="warning",
            observed_value="one intentional duplicate fixture event",
            expected_constraint="unique source and source_event_id",
            created_at=run.finished_at,
            resolved_at=run.finished_at,
        )
        return (run,), (issue,)

    def _next_event_time(self) -> datetime:
        self._event_sequence += 1
        return DEMO_AS_OF + timedelta(seconds=self._event_sequence)

    def _record_audit(
        self,
        action: AuditAction,
        aggregate_type: str,
        aggregate_id: UUID | None,
        details: Mapping[str, Any],
        *,
        correlation_id: UUID | None = None,
    ) -> None:
        sequence = len(self._audit_events) + 1
        event = AuditEvent.create(
            audit_id=_stable_uuid("audit", str(sequence)),
            action=action,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            actor_id="demo-user" if action is not AuditAction.DATA_IMPORTED else "demo-seed",
            occurred_at=self._next_event_time(),
            correlation_id=correlation_id or _stable_uuid("correlation", str(sequence)),
            details=details,
        )
        self._audit_events.append(event)

    def list_instruments(self) -> tuple[Instrument, ...]:
        return tuple(sorted(self._instruments.values(), key=lambda item: item.symbol.value))

    def get_instrument(self, instrument_id: UUID) -> Instrument:
        try:
            return self._instruments[instrument_id]
        except KeyError as error:
            raise NotFoundError(f"instrument {instrument_id} was not found") from error

    def list_prices(
        self,
        instrument_id: UUID,
        *,
        start: date | None,
        end: date | None,
    ) -> tuple[PriceBarRecord, ...]:
        self.get_instrument(instrument_id)
        bars = self._prices[instrument_id]
        return tuple(
            item
            for item in bars
            if (start is None or item.observed_at.date() >= start)
            and (end is None or item.observed_at.date() <= end)
        )

    def list_portfolios(self) -> tuple[Portfolio, ...]:
        return tuple(sorted(self._portfolios.values(), key=lambda item: (item.name, item.id)))

    def get_portfolio(self, portfolio_id: UUID) -> Portfolio:
        try:
            return self._portfolios[portfolio_id]
        except KeyError as error:
            raise NotFoundError(f"portfolio {portfolio_id} was not found") from error

    def list_positions(self, portfolio_id: UUID) -> tuple[Position, ...]:
        self.get_portfolio(portfolio_id)
        return tuple(
            sorted(self._positions.get(portfolio_id, ()), key=lambda item: item.instrument_id)
        )

    def create_portfolio(
        self,
        *,
        name: str,
        base_currency: str,
        description: str | None,
        correlation_id: UUID,
    ) -> Portfolio:
        if Currency(base_currency) != Currency("USD"):
            raise DomainValidationError("demo portfolios currently support USD only")
        with self._lock:
            self._portfolio_sequence += 1
            portfolio = Portfolio.create(
                portfolio_id=_stable_uuid("portfolio", str(self._portfolio_sequence)),
                name=name,
                base_currency=base_currency,
                description=description,
                is_demo=True,
                now=self._next_event_time(),
            )
            self._portfolios[portfolio.id] = portfolio
            self._positions[portfolio.id] = ()
            self._snapshot_history[portfolio.id] = []
            self._record_audit(
                AuditAction.PORTFOLIO_CREATED,
                "portfolio",
                portfolio.id,
                {"version": portfolio.version},
                correlation_id=correlation_id,
            )
            return portfolio

    def patch_portfolio(
        self,
        portfolio_id: UUID,
        *,
        expected_version: int,
        name: str | None,
        description: str | None,
        description_is_set: bool,
        correlation_id: UUID,
    ) -> Portfolio:
        with self._lock:
            current = self.get_portfolio(portfolio_id)
            kwargs: dict[str, Any] = {}
            if name is not None:
                kwargs["name"] = name
            if description_is_set:
                kwargs["description"] = description
            revised = current.revise(
                expected_version=expected_version,
                updated_at=self._next_event_time(),
                **kwargs,
            )
            if revised is current:
                return current
            self._portfolios[portfolio_id] = revised
            self._record_audit(
                AuditAction.PORTFOLIO_UPDATED,
                "portfolio",
                portfolio_id,
                {"previous_version": current.version, "version": revised.version},
                correlation_id=correlation_id,
            )
            return revised

    def replace_positions(
        self,
        portfolio_id: UUID,
        *,
        expected_version: int,
        items: Sequence[tuple[UUID, Decimal, Decimal, str, Mapping[str, str]]],
        correlation_id: UUID,
    ) -> tuple[Portfolio, tuple[Position, ...]]:
        with self._lock:
            portfolio = self.get_portfolio(portfolio_id)
            portfolio.assert_version(expected_version)
            instrument_ids = [item[0] for item in items]
            if len(set(instrument_ids)) != len(instrument_ids):
                raise DomainValidationError("positions must contain unique instrument IDs")
            positions: list[Position] = []
            for instrument_id, quantity, average_cost, currency, tags in items:
                instrument = self.get_instrument(instrument_id)
                if Currency(currency) != portfolio.base_currency:
                    raise DomainValidationError(
                        "position currency must equal portfolio base currency"
                    )
                if instrument.quote_currency != portfolio.base_currency:
                    raise DomainValidationError("demo position requires same-currency instrument")
                positions.append(
                    Position.create(
                        position_id=_stable_uuid(
                            "position", f"{portfolio_id}:{expected_version + 1}:{instrument_id}"
                        ),
                        portfolio_id=portfolio_id,
                        instrument_id=instrument_id,
                        quantity=quantity,
                        average_cost=average_cost,
                        currency=currency,
                        as_of=DEMO_AS_OF,
                        tags=tags,
                    )
                )
            updated_at = self._next_event_time()
            updated = Portfolio(
                id=portfolio.id,
                name=portfolio.name,
                base_currency=portfolio.base_currency,
                description=portfolio.description,
                is_demo=portfolio.is_demo,
                version=portfolio.version + 1,
                created_at=portfolio.created_at,
                updated_at=updated_at,
            )
            self._portfolios[portfolio_id] = updated
            self._positions[portfolio_id] = tuple(positions)
            self._record_audit(
                AuditAction.PORTFOLIO_UPDATED,
                "portfolio",
                portfolio_id,
                {
                    "change": "positions_replaced",
                    "position_count": len(positions),
                    "previous_version": portfolio.version,
                    "version": updated.version,
                },
                correlation_id=correlation_id,
            )
            return updated, tuple(positions)

    def _position_inputs(
        self, portfolio_id: UUID, price_index: int = -1
    ) -> tuple[PositionInput, ...]:
        portfolio = self.get_portfolio(portfolio_id)
        return tuple(
            PositionInput(
                instrument_id=str(position.instrument_id),
                quantity=position.quantity,
                price=self._prices[position.instrument_id][price_index].close,
                price_currency=position.currency.code,
                base_currency=portfolio.base_currency.code,
                fx_rate_to_base=Decimal("1"),
                cost_basis_per_unit=position.average_cost,
            )
            for position in self.list_positions(portfolio_id)
        )

    def _compute_snapshot(
        self, portfolio_id: UUID, *, confidence_level: float = 0.95
    ) -> RiskSnapshotRecord:
        portfolio = self.get_portfolio(portfolio_id)
        positions = self.list_positions(portfolio_id)
        if not positions:
            raise ConflictError("portfolio has no positions to value")
        valuation = value_portfolio(self._position_inputs(portfolio_id))
        dates = tuple(item.observed_at for item in self._prices[positions[0].instrument_id])
        portfolio_values = tuple(
            value_portfolio(self._position_inputs(portfolio_id, index)).total_market_value
            for index in range(len(dates))
        )
        portfolio_returns = arithmetic_returns(
            tuple(float(value) for value in portfolio_values),
            dates=dates,
        )
        historical = historical_var(
            portfolio_returns.values,
            confidence_level=confidence_level,
            portfolio_value=float(valuation.total_market_value),
        )
        expected_shortfall = historical_expected_shortfall(
            portfolio_returns.values,
            confidence_level=confidence_level,
            portfolio_value=float(valuation.total_market_value),
        )
        volatility = sample_volatility(portfolio_returns.values)
        drawdown = maximum_drawdown(
            tuple(float(value) for value in portfolio_values),
            dates,
        )
        instrument_returns = tuple(
            arithmetic_returns(
                tuple(float(item.close) for item in self._prices[position.instrument_id]),
                dates=dates,
            ).values
            for position in positions
        )
        return_rows = tuple(zip(*(values for values in instrument_returns), strict=True))
        exposures = tuple(float(item.market_value) for item in valuation.components)
        parametric = parametric_var_from_returns(
            return_rows,
            exposures,
            confidence_level=confidence_level,
        )
        exposure_map = {
            component.instrument_id: float(component.market_value)
            for component in valuation.components
        }
        concentration = herfindahl_hirschman(exposure_map)
        items = [
            evidence_item(
                key=f"prices:{self._instruments[position.instrument_id].symbol.value}",
                source_kind="synthetic_price_series",
                as_of=DEMO_AS_OF.isoformat(),
                payload=[str(item.close) for item in self._prices[position.instrument_id]],
            )
            for position in positions
        ]
        items.append(
            evidence_item(
                key=f"portfolio:{portfolio.id}:v{portfolio.version}",
                source_kind="portfolio_positions",
                as_of=DEMO_AS_OF.isoformat(),
                payload=[
                    {
                        "instrument_id": str(item.instrument_id),
                        "quantity": str(item.quantity),
                    }
                    for item in positions
                ],
            )
        )
        manifest = build_evidence_manifest(
            items,
            parameters={
                "confidence_level": confidence_level,
                "methodology_version": METHODOLOGY_VERSION,
                "return_method": "arithmetic",
            },
        )
        snapshot_id = _stable_uuid(
            "risk-snapshot",
            f"{portfolio.id}:{portfolio.version}:{DEMO_AS_OF.isoformat()}:{confidence_level}",
        )
        snapshot = RiskSnapshotRecord(
            id=snapshot_id,
            portfolio_id=portfolio.id,
            portfolio_version=portfolio.version,
            as_of=DEMO_AS_OF,
            created_at=self._next_event_time(),
            methodology_version=METHODOLOGY_VERSION,
            window_start=dates[0],
            window_end=dates[-1],
            confidence_level=confidence_level,
            base_currency=portfolio.base_currency.code,
            portfolio_value=valuation.total_market_value,
            daily_pnl=portfolio_values[-1] - portfolio_values[-2],
            volatility_annualized=volatility.annualized_volatility,
            var_historical=historical.value,
            var_parametric=parametric.value,
            expected_shortfall=expected_shortfall.value,
            max_drawdown=drawdown.maximum_drawdown,
            data_completeness=1.0,
            quality_status=RiskQualityStatus.COMPLETE.value,
            observation_count=portfolio_returns.observation_count,
            concentration_hhi=concentration.hhi,
            largest_absolute_weight=concentration.largest_weight,
            evidence_id=manifest.evidence_id,
            assumptions=tuple(
                sorted(
                    set(
                        historical.assumptions
                        + expected_shortfall.assumptions
                        + parametric.assumptions
                    )
                )
            ),
        )
        self._snapshots[snapshot.id] = snapshot
        history = self._snapshot_history.setdefault(portfolio.id, [])
        if snapshot.id not in history:
            history.append(snapshot.id)
        self._evidence[snapshot.id] = json.loads(manifest.to_json())
        return snapshot

    def recompute_risk(
        self,
        portfolio_id: UUID,
        *,
        confidence_level: float,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> IdempotentResult[RiskSnapshotRecord]:
        self.get_portfolio(portfolio_id)
        fingerprint = _canonical_fingerprint(
            {"portfolio_id": str(portfolio_id), "confidence_level": confidence_level}
        )
        identity = ("risk-recompute", idempotency_key)
        with self._lock:
            existing = self._idempotency.get(identity)
            if existing is not None:
                stored_fingerprint, resource_id = existing
                if stored_fingerprint != fingerprint:
                    raise ConflictError(
                        "idempotency key was already used with different parameters"
                    )
                return IdempotentResult(self._snapshots[UUID(str(resource_id))], True)
            snapshot = self._compute_snapshot(
                portfolio_id,
                confidence_level=confidence_level,
            )
            self._idempotency[identity] = (fingerprint, snapshot.id)
            self._record_audit(
                AuditAction.RISK_RECOMPUTED,
                "risk_snapshot",
                snapshot.id,
                {
                    "portfolio_id": str(portfolio_id),
                    "portfolio_version": snapshot.portfolio_version,
                },
                correlation_id=correlation_id,
            )
            return IdempotentResult(snapshot, False)

    def latest_risk(self, portfolio_id: UUID) -> RiskSnapshotRecord:
        self.get_portfolio(portfolio_id)
        history = self._snapshot_history.get(portfolio_id, [])
        if not history:
            raise NotFoundError(f"portfolio {portfolio_id} has no risk snapshots")
        return self._snapshots[history[-1]]

    def risk_history(self, portfolio_id: UUID) -> tuple[RiskSnapshotRecord, ...]:
        self.get_portfolio(portfolio_id)
        return tuple(self._snapshots[item] for item in self._snapshot_history[portfolio_id])

    def get_snapshot(self, snapshot_id: UUID) -> RiskSnapshotRecord:
        try:
            return self._snapshots[snapshot_id]
        except KeyError as error:
            raise NotFoundError(f"risk snapshot {snapshot_id} was not found") from error

    def get_evidence(self, snapshot_id: UUID) -> dict[str, Any]:
        self.get_snapshot(snapshot_id)
        return self._evidence[snapshot_id]

    def list_scenarios(self) -> tuple[ScenarioDefinition, ...]:
        return tuple(sorted(self._scenario_definitions.values(), key=lambda item: item.key))

    def create_scenario(
        self,
        *,
        title: str,
        version: str,
        shocks: Sequence[CustomShockCommand],
        assumptions: Sequence[str],
        idempotency_key: str,
        correlation_id: UUID,
    ) -> IdempotentResult[ScenarioDefinition]:
        canonical = {
            "title": title,
            "version": version,
            "shocks": [(item.kind, item.target, str(item.value)) for item in shocks],
            "assumptions": list(assumptions),
        }
        fingerprint = _canonical_fingerprint(canonical)
        identity = ("scenario-create", idempotency_key)
        with self._lock:
            existing = self._idempotency.get(identity)
            if existing is not None:
                stored_fingerprint, scenario_key = existing
                if stored_fingerprint != fingerprint:
                    raise ConflictError(
                        "idempotency key was already used with different parameters"
                    )
                return IdempotentResult(self._scenario_definitions[str(scenario_key)], True)
            key = f"custom_{fingerprint[:16]}"
            risk_shocks: list[ScenarioShock] = []
            for item in shocks:
                if item.kind == "instrument_price":
                    risk_shocks.append(InstrumentPriceShock(item.target, item.value))
                elif item.kind == "asset_class":
                    risk_shocks.append(AssetClassShock(item.target, item.value))
                elif item.kind == "volatility_multiplier":
                    risk_shocks.append(VolatilityMultiplier(item.value))
                elif item.kind == "fx":
                    risk_shocks.append(FXShock(item.target, item.value))
                elif item.kind == "correlation_override":
                    pair = tuple(part.strip() for part in item.target.replace(",", ":").split(":"))
                    if len(pair) != 2 or not all(pair):
                        raise DomainValidationError(
                            "correlation_override target must be LEFT:RIGHT"
                        )
                    risk_shocks.append(CorrelationOverride(pair[0], pair[1], item.value))
                else:
                    raise DomainValidationError(f"unsupported custom shock kind: {item.kind}")
            definition = ScenarioDefinition(
                key=key,
                title=title,
                version=version,
                shocks=tuple(risk_shocks),
                assumptions=tuple(assumptions),
            )
            self._scenario_definitions[key] = definition
            self._idempotency[identity] = (fingerprint, key)
            self._record_audit(
                AuditAction.SCENARIO_EXECUTED,
                "scenario_definition",
                _stable_uuid("scenario-definition", key),
                {"change": "custom_scenario_created", "scenario_key": key},
                correlation_id=correlation_id,
            )
            return IdempotentResult(definition, False)

    def run_scenario(
        self,
        portfolio_id: UUID,
        scenario_id: str,
        *,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> IdempotentResult[ScenarioRunRecord]:
        portfolio = self.get_portfolio(portfolio_id)
        try:
            definition = self._scenario_definitions[scenario_id]
        except KeyError as error:
            raise NotFoundError(f"scenario {scenario_id} was not found") from error
        fingerprint = _canonical_fingerprint(
            {
                "portfolio_id": str(portfolio_id),
                "portfolio_version": portfolio.version,
                "scenario_id": scenario_id,
                "scenario_version": definition.version,
            }
        )
        identity = ("scenario-run", idempotency_key)
        with self._lock:
            existing = self._idempotency.get(identity)
            if existing is not None:
                stored_fingerprint, run_id = existing
                if stored_fingerprint != fingerprint:
                    raise ConflictError(
                        "idempotency key was already used with different parameters"
                    )
                return IdempotentResult(self._scenario_runs[str(run_id)], True)
            scenario_positions = tuple(
                ScenarioPosition(
                    instrument_id=self._instruments[position.instrument_id].symbol.value,
                    asset_class=self._instruments[position.instrument_id].asset_class.value,
                    quantity=position.quantity,
                    price=self._prices[position.instrument_id][-1].close,
                    price_currency=position.currency.code,
                    base_currency=portfolio.base_currency.code,
                )
                for position in self.list_positions(portfolio_id)
            )
            result = run_scenario(definition, scenario_positions)
            record = ScenarioRunRecord(
                id=result.deterministic_run_id,
                portfolio_id=portfolio_id,
                portfolio_version=portfolio.version,
                run_at=self._next_event_time(),
                result=result,
            )
            self._scenario_runs[record.id] = record
            self._idempotency[identity] = (fingerprint, record.id)
            self._record_audit(
                AuditAction.SCENARIO_EXECUTED,
                "scenario_run",
                _stable_uuid("scenario-run", record.id),
                {"portfolio_id": str(portfolio_id), "scenario_id": scenario_id},
                correlation_id=correlation_id,
            )
            return IdempotentResult(record, False)

    def get_scenario_run(self, run_id: str) -> ScenarioRunRecord:
        try:
            return self._scenario_runs[run_id]
        except KeyError as error:
            raise NotFoundError(f"scenario run {run_id} was not found") from error

    def list_pipeline_runs(self) -> tuple[PipelineRunRecord, ...]:
        return self._pipeline_runs

    def get_pipeline_run(self, run_id: UUID) -> PipelineRunRecord:
        try:
            return next(item for item in self._pipeline_runs if item.id == run_id)
        except StopIteration as error:
            raise NotFoundError(f"pipeline run {run_id} was not found") from error

    def list_quality_issues(self) -> tuple[DataQualityIssueRecord, ...]:
        return self._quality_issues

    def list_audit_events(self) -> tuple[AuditEvent, ...]:
        return tuple(sorted(self._audit_events, key=lambda item: (item.occurred_at, item.id)))

    def portfolio_report(self, portfolio_id: UUID) -> dict[str, Any]:
        portfolio = self.get_portfolio(portfolio_id)
        positions = self.list_positions(portfolio_id)
        risk = self.latest_risk(portfolio_id)
        components = {
            str(item.instrument_id): item.quantity * self._prices[item.instrument_id][-1].close
            for item in positions
        }
        return {
            "report_version": "1.0.0",
            "synthetic": True,
            "not_investment_advice": True,
            "portfolio": {
                "id": str(portfolio.id),
                "name": portfolio.name,
                "version": portfolio.version,
                "base_currency": portfolio.base_currency.code,
            },
            "as_of": risk.as_of.isoformat().replace("+00:00", "Z"),
            "positions": [
                {
                    "instrument_id": str(item.instrument_id),
                    "symbol": self._instruments[item.instrument_id].symbol.value,
                    "quantity": str(item.quantity),
                    "market_value": str(components[str(item.instrument_id)]),
                    "currency": item.currency.code,
                }
                for item in positions
            ],
            "risk": {
                "snapshot_id": str(risk.id),
                "methodology_version": risk.methodology_version,
                "portfolio_value": str(risk.portfolio_value),
                "var_historical": risk.var_historical,
                "var_parametric": risk.var_parametric,
                "expected_shortfall": risk.expected_shortfall,
                "volatility_annualized": risk.volatility_annualized,
                "max_drawdown": risk.max_drawdown,
                "quality_status": risk.quality_status,
                "evidence_id": risk.evidence_id,
            },
        }
