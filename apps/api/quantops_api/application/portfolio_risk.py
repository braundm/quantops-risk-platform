"""Connect imported holdings to dated history, scenarios and independent allocation copies."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator
from quantops_risk.equity_diagnostics import EquityDiagnostics, equity_diagnostics
from quantops_risk.portfolio_history import (
    AllocationRisk,
    PerformanceSummary,
    allocation_risk,
    compound_shock,
    performance_summary,
)

from quantops_api.application.xtb_book import analyze_book
from quantops_api.application.xtb_models import Positive, ReportContract, XtbBook, iso_currency
from quantops_api.application.xtb_quotes import mapped_stock, physical_catalog

Weight = Annotated[Decimal, Field(ge=0, le=1, allow_inf_nan=False)]
Shock = Annotated[Decimal, Field(gt=-1, le=5, allow_inf_nan=False)]


class RiskPrice(ReportContract):
    date: date
    close: Positive
    adjusted_close: Positive
    fx_to_base: Positive


class RiskHistory(ReportContract):
    symbol: str = Field(min_length=1, max_length=80)
    currency: str
    base_currency: str
    source: str = Field(min_length=1, max_length=200)
    source_url: str = Field(pattern=r"^https://", max_length=500)
    fx_source: str = Field(min_length=1, max_length=200)
    fetched_at: datetime
    origin: Literal["provider", "user", "synthetic"]
    price_basis: Literal["split_dividend_adjusted"] = "split_dividend_adjusted"
    rows: list[RiskPrice] = Field(min_length=2, max_length=1300)
    split_dates: list[date] = Field(default_factory=list, max_length=100)

    _currency = field_validator("currency", "base_currency")(iso_currency)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        days = [row.date for row in self.rows]
        if days != sorted(set(days)) or any(day >= datetime.now(UTC).date() for day in days):
            raise ValueError("History requires unique ordered completed dates")
        if self.fetched_at.utcoffset() is None or self.fetched_at > datetime.now(UTC):
            raise ValueError("Retrieval timestamp must be timezone aware and not future")
        if self.split_dates != sorted(set(self.split_dates)) or any(
            day >= datetime.now(UTC).date() for day in self.split_dates
        ):
            raise ValueError("Split dates must be unique, ordered and completed")
        if self.currency == self.base_currency and any(row.fx_to_base != 1 for row in self.rows):
            raise ValueError("Same-currency FX must equal one")
        return self


class CashBalance(ReportContract):
    symbol: str = Field(pattern=r"^CASH:[A-Z]{3}$")
    currency: str
    amount: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    as_of: date

    _currency = field_validator("currency")(iso_currency)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.symbol != f"CASH:{self.currency}" or self.as_of >= datetime.now(UTC).date():
            raise ValueError("Cash requires a completed balance date and matching currency symbol")
        return self


class RiskScenario(ReportContract):
    name: str = Field(min_length=1, max_length=80)
    position_shocks: dict[str, Shock] = Field(default_factory=dict, max_length=50)
    class_shocks: dict[Literal["equity", "etf", "cash"], Shock] = Field(default_factory=dict)
    fx_shocks: dict[str, Shock] = Field(default_factory=dict, max_length=10)

    @field_validator("fx_shocks")
    @classmethod
    def currencies(cls, values: dict[str, Decimal]) -> dict[str, Decimal]:
        for currency in values:
            iso_currency(currency)
        return values


class EtfHolding(ReportContract):
    issuer_id: str = Field(min_length=1, max_length=100)
    weight: Weight


class EtfComposition(ReportContract):
    symbol: str = Field(max_length=80)
    source_url: str = Field(pattern=r"^https://", max_length=500)
    as_of: date
    holdings: list[EtfHolding] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.as_of >= datetime.now(UTC).date() or sum(h.weight for h in self.holdings) > 1:
            raise ValueError("ETF composition requires a completed date and coverage at most 100%")
        if len({h.issuer_id for h in self.holdings}) != len(self.holdings):
            raise ValueError("Duplicate ETF issuer identities")
        return self


class ExposureMetadata(ReportContract):
    symbol: str = Field(max_length=80)
    sector: str | None = Field(default=None, max_length=100)
    issuer_id: str | None = Field(default=None, min_length=1, max_length=100)
    issuer_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    economic_currency: str | None = None
    source_url: str = Field(pattern=r"^https://", max_length=500)
    as_of: date

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.as_of >= datetime.now(UTC).date():
            raise ValueError("Exposure metadata cannot be future dated")
        if self.economic_currency is not None:
            iso_currency(self.economic_currency)
        return self


class RiskRequest(ReportContract):
    book: XtbBook
    scope: Literal["full_account", "securities_only"] = "full_account"
    asset_scope: Literal["all_supported", "equities_only"] = "all_supported"
    base_currency: str = "PLN"
    histories: list[RiskHistory] = Field(default_factory=list, max_length=50)
    cash: list[CashBalance] = Field(default_factory=list, max_length=10)
    cash_confirmed: bool = False
    confidence: Annotated[Decimal, Field(ge=Decimal("0.90"), le=Decimal("0.99"))] = Decimal("0.95")
    start: date | None = None
    end: date | None = None
    benchmark: str | None = Field(default=None, max_length=80)
    scenarios: list[RiskScenario] = Field(default_factory=list, max_length=10)
    variant: dict[str, Weight] | None = Field(default=None, max_length=50)
    tolerance_amount: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)] | None = None
    tolerance_fraction: Annotated[Decimal, Field(gt=0, le=1, allow_inf_nan=False)] | None = None
    etf_compositions: list[EtfComposition] = Field(default_factory=list, max_length=30)
    metadata: list[ExposureMetadata] = Field(default_factory=list, max_length=50)

    _currency = field_validator("base_currency")(iso_currency)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.asset_scope == "equities_only" and self.scope != "securities_only":
            raise ValueError("Equity-only analysis requires the explicit securities-only scope")
        if self.scope == "securities_only" and self.cash:
            raise ValueError("Securities-only analysis cannot include an account cash balance")
        if len({h.symbol for h in self.histories}) != len(self.histories):
            raise ValueError("Duplicate instrument histories")
        if len({c.symbol for c in self.cash}) != len(self.cash):
            raise ValueError("Duplicate cash currencies")
        if any(h.base_currency != self.base_currency for h in self.histories):
            raise ValueError("History FX basis differs from the selected base currency")
        if self.start and self.end and self.start >= self.end:
            raise ValueError("Analysis start must precede end")
        if self.variant is not None and sum(self.variant.values()) != 1:
            raise ValueError("Variant weights must sum exactly to 100%; no automatic normalization")
        if any(s.fx_shocks.get(self.base_currency, 0) != 0 for s in self.scenarios):
            raise ValueError("The base currency cannot be shocked relative to itself")
        if len({m.symbol for m in self.metadata}) != len(self.metadata):
            raise ValueError("Duplicate exposure metadata")
        if len({e.symbol for e in self.etf_compositions}) != len(self.etf_compositions):
            raise ValueError("Duplicate ETF compositions")
        return self


class RiskPosition(ReportContract):
    symbol: str
    name: str
    asset_class: Literal["equity", "etf", "cash"]
    currency: str | None
    listing_country: str | None
    issuer_country: str | None = None
    sector: str | None = None
    economic_currency: str | None = None
    issuer_id: str | None = None
    value: Decimal | None = None
    weight: Decimal | None = None
    status: str


class ScenarioResult(ReportContract):
    name: str
    kind: str
    status: str
    pnl: Decimal | None = None
    fraction: Decimal | None = None
    value_after: Decimal | None = None
    impacts: dict[str, Decimal] = Field(default_factory=dict)
    largest_losses: list[str] = Field(default_factory=list)
    maximum_drawdown: float | None = None
    exceeds_tolerance: bool | None = None


class AllocationResult(ReportContract):
    value: Decimal
    weights: dict[str, Decimal]
    position_values: dict[str, Decimal]
    var_amount: Decimal | None
    es_amount: Decimal | None
    largest_position: Decimal
    top_five: Decimal
    exposures: dict[str, dict[str, Decimal]]
    risk: AllocationRisk
    performance: PerformanceSummary
    curve: list[tuple[date, Decimal]]
    scenarios: list[ScenarioResult]
    diagnostics: EquityDiagnostics


class RiskResult(ReportContract):
    methodology: str = "imported-allocation-risk@1.1.0"
    scope: Literal["full_account", "securities_only"]
    asset_scope: Literal["all_supported", "equities_only"]
    out_of_scope: dict[str, str]
    status: str
    base_currency: str
    valuation_date: date | None
    quantity_date: date | None
    period_start: date | None
    period_end: date | None
    coverage_fraction: Decimal | None
    covered_value: Decimal
    excluded: dict[str, str]
    positions: list[RiskPosition]
    before: AllocationResult | None
    after: AllocationResult | None
    benchmark: PerformanceSummary | None
    benchmark_status: str
    history_dates: int
    return_dates: int
    skipped_pairs: int
    history_coverage: dict[str, int]
    etf_overlap: list[dict[str, str]]
    warnings: list[str]


def analyze_imported_risk(request: RiskRequest) -> RiskResult:
    """Value known holdings, then calculate only complete, comparable allocations."""
    analysis = analyze_book(request.book)
    histories = {h.symbol: h for h in request.histories}
    metadata = {m.symbol: m for m in request.metadata}
    universe: dict[str, RiskPosition] = {}
    excluded: dict[str, str] = {}
    out_of_scope: dict[str, str] = {}
    quantities: dict[str, Decimal] = {}
    for holding in analysis.holdings:
        symbol = holding.symbol
        if request.asset_scope == "equities_only" and holding.asset_type != "equity":
            out_of_scope[symbol] = "outside_selected_equity_scope"
            continue
        if (
            holding.status != "spot"
            or holding.side != "BUY"
            or holding.asset_type not in ("equity", "etf")
        ):
            excluded[symbol] = "unsupported_derivative_or_unclassified"
            continue
        quantities[symbol] = quantities.get(symbol, Decimal(0)) + holding.quantity
    wanted = set(quantities) | {s for s, w in (request.variant or {}).items() if w > 0}
    wanted |= {c.symbol for c in request.cash if c.amount > 0}
    if request.variant is not None:
        wanted.add(f"CASH:{request.base_currency}")
    cash_amounts = {c.symbol: c.amount for c in request.cash}
    for symbol in sorted(wanted):
        if symbol.startswith("CASH:"):
            currency = iso_currency(symbol.removeprefix("CASH:"))
            universe[symbol] = RiskPosition(
                symbol=symbol,
                name=f"Cash {currency}",
                asset_class="cash",
                currency=currency,
                listing_country=None,
                status="pending",
            )
        else:
            try:
                stock = mapped_stock(symbol)
                catalog = physical_catalog()[symbol]
                if request.asset_scope == "equities_only" and catalog.instrument_type != "equity":
                    raise ValueError("Equity-only variants require physical equities")
                if catalog.instrument_type not in ("equity", "etf"):
                    raise ValueError("Only stocks and ETFs are supported")
                universe[symbol] = RiskPosition(
                    symbol=symbol,
                    name=stock.name,
                    asset_class="equity" if catalog.instrument_type == "equity" else "etf",
                    currency=stock.currency,
                    listing_country=symbol.rsplit(".", 1)[-1],
                    status="pending",
                )
            except ValueError:
                excluded[symbol] = "unsupported_listing_or_asset_type"
                continue
        p = universe[symbol]
        if symbol in metadata:
            m = metadata[symbol]
            p.sector, p.issuer_country, p.economic_currency = (
                m.sector,
                m.issuer_country,
                m.economic_currency,
            )
            p.issuer_id = m.issuer_id
        history = histories.get(symbol)
        if not (p.asset_class == "cash" and p.currency == request.base_currency):
            if history is None:
                excluded[symbol] = p.status = "missing_history_or_fx"
            elif history.currency != p.currency:
                raise ValueError(f"History currency differs from the listing: {symbol}")
            elif p.asset_class == "cash" and any(
                r.close != 1 or r.adjusted_close != 1 for r in history.rows
            ):
                raise ValueError("Cash history prices must equal one; FX carries the return")
    relevant = wanted | ({request.benchmark} if request.benchmark else set())
    full_indexed = {
        symbol: {r.date: r for r in h.rows} for symbol, h in histories.items() if symbol in relevant
    }
    indexed = {
        symbol: {
            day: r
            for day, r in points.items()
            if (not request.start or day >= request.start)
            and (not request.end or day <= request.end)
        }
        for symbol, points in full_indexed.items()
    }
    calendars = [
        set(indexed[s])
        for s, p in universe.items()
        if s not in excluded
        and not (p.asset_class == "cash" and p.currency == request.base_currency)
    ]
    # Benchmark availability must not silently shrink the portfolio's analysis window.
    union = (
        sorted(set.union(*calendars))
        if calendars
        else sorted({day for rows in indexed.values() for day in rows})
    )
    common = sorted(set.intersection(*calendars)) if calendars else union
    valuation_calendars = [
        set(full_indexed[s])
        for s, p in universe.items()
        if s not in excluded
        and not (p.asset_class == "cash" and p.currency == request.base_currency)
    ]
    valuation_days = (
        sorted(set.intersection(*valuation_calendars))
        if valuation_calendars
        else sorted({day for rows in full_indexed.values() for day in rows})
    )
    valuation_date = valuation_days[-1] if valuation_days else None
    fill_dates = [
        r.event_at.date()
        for r in request.book.records
        if r.kind == "fill" and (request.asset_scope != "equities_only" or r.asset_type == "equity")
    ]
    quantity_anchor = (
        request.book.open_snapshot_at.date()
        if request.book.open_snapshot_at
        else min(fill_dates, default=None)
    )
    # Reconstructed quantities include every execution, not just the first purchase.
    # Later closing reports can also reduce a previously imported open snapshot.
    open_ids = {
        r.source_id
        for r in request.book.records
        if r.kind == "open" and (request.asset_scope != "equities_only" or r.asset_type == "equity")
    }
    quantity_date = max(
        [day for day in [quantity_anchor, *fill_dates] if day is not None]
        + [
            r.close_at.date()
            for r in request.book.records
            if r.kind == "closed"
            and r.close_at is not None
            and r.source_id in open_ids
            and (request.asset_scope != "equities_only" or r.asset_type == "equity")
        ],
        default=None,
    )
    for symbol, p in universe.items():
        if symbol in excluded:
            continue
        if (
            symbol in quantities
            and quantity_anchor
            and valuation_date
            and any(
                quantity_anchor < day <= valuation_date for day in histories[symbol].split_dates
            )
        ):
            excluded[symbol] = p.status = "split_requires_quantity_reconciliation"
            continue
        if p.asset_class == "cash" and p.currency == request.base_currency:
            p.value = cash_amounts.get(symbol, Decimal(0))
        elif valuation_date and valuation_date in full_indexed.get(symbol, {}):
            row = full_indexed[symbol][valuation_date]
            p.value = (
                quantities[symbol] * row.close * row.fx_to_base
                if symbol in quantities
                else (cash_amounts.get(symbol, Decimal(0)) * row.fx_to_base)
            )
        else:
            excluded[symbol] = p.status = "no_common_valuation_date"
            continue
        p.status = "valued"
    # Different instruments in one quote currency must share the same dated FX.
    rates: dict[tuple[str, date], Decimal] = {}
    for symbol, points in full_indexed.items():
        for day, row in points.items():
            key = (histories[symbol].currency, day)
            if key in rates and rates[key] != row.fx_to_base:
                raise ValueError("Contradictory FX rates for the same currency and date")
            rates[key] = row.fx_to_base
    original = {
        symbol: p.value
        for symbol, p in universe.items()
        if symbol in quantities or symbol in cash_amounts
    }
    total = sum((v for v in original.values() if v is not None), Decimal(0))
    complete = (
        not excluded
        and analysis.holdings_status not in ("unknown", "incomplete")
        and (request.scope == "securities_only" or request.cash_confirmed)
        and all(c.as_of == valuation_date for c in request.cash)
        and (
            quantity_date is None
            or (valuation_date is not None and valuation_date >= quantity_date)
        )
    )
    warnings = [
        "current_allocation_simulation_not_actual_performance",
        "buy_and_hold_no_rebalancing",
        "adjusted_total_returns_dividends_reinvested_once",
        "costs_taxes_inflation_excluded",
        "cash_balance_must_be_confirmed_not_inferred_from_flows",
        "no_proxy_substitution",
        "listing_country_is_not_issuer_country",
        "quote_currency_is_not_economic_exposure",
        "unknown_etf_holdings_are_not_invented",
        "var_is_not_maximum_loss",
        "common_calendar_no_fill_no_returns_across_missing_union_dates",
    ]
    if request.scope == "securities_only":
        warnings.remove("cash_balance_must_be_confirmed_not_inferred_from_flows")
        warnings.append("securities_only_account_cash_not_included")
    elif not request.cash_confirmed:
        warnings.append("cash_balance_unconfirmed")
    if request.asset_scope == "equities_only":
        warnings.append("equities_only_other_instruments_not_included")
    if quantity_date and valuation_date and valuation_date < quantity_date:
        warnings.append("valuation_precedes_quantity_snapshot")
    if any(c.as_of != valuation_date for c in request.cash):
        warnings.append("cash_balance_date_differs_from_valuation")
    if valuation_date and (datetime.now(UTC).date() - valuation_date).days > 7:
        warnings.append("stale_valuation_date")
    if any(h.origin == "synthetic" for h in request.histories):
        warnings.append("synthetic_history")
    before = after = None
    benchmark = None
    return_dates = 0
    skipped = 0
    if complete and total > 0 and len(common) >= 2:
        symbols = sorted(universe)
        for symbol in symbols:
            universe[symbol].weight = (original.get(symbol) or Decimal(0)) / total
        weights = {s: universe[s].weight or Decimal(0) for s in symbols}
        # Decimal division can leave a rounding residual: risk inputs are values / exact NAV;
        # put only that arithmetic residual on the largest original component.
        largest = max(weights, key=lambda s: weights[s])
        weights[largest] += 1 - sum(weights.values())
        relatives: dict[str, list[Decimal]] = {}
        for symbol in symbols:
            p = universe[symbol]
            if p.asset_class == "cash" and p.currency == request.base_currency:
                relatives[symbol] = [Decimal(1)] * len(common)
            else:
                rows = [indexed[symbol][day] for day in common]
                anchor = rows[0].adjusted_close * rows[0].fx_to_base
                relatives[symbol] = [r.adjusted_close * r.fx_to_base / anchor for r in rows]
        union_index = {day: i for i, day in enumerate(union)}
        daily_rows: list[list[float]] = []
        for i in range(1, len(common)):
            if (
                union_index[common[i]] != union_index[common[i - 1]] + 1
                or (common[i] - common[i - 1]).days > 4
            ):
                skipped += 1
                continue
            daily_rows.append([float(relatives[s][i] / relatives[s][i - 1] - 1) for s in symbols])
        return_dates = len(daily_rows)
        before = allocation_result(
            request,
            universe,
            symbols,
            weights,
            total,
            common,
            relatives,
            daily_rows,
            valuation_date,
        )
        if request.variant is not None:
            if set(request.variant) - set(universe):
                raise ValueError("Variant contains unsupported instruments")
            after_weights = {s: request.variant.get(s, Decimal(0)) for s in symbols}
            after = allocation_result(
                request,
                universe,
                symbols,
                after_weights,
                total,
                common,
                relatives,
                daily_rows,
                valuation_date,
            )
        if request.benchmark and all(day in indexed.get(request.benchmark, {}) for day in common):
            benchmark_points = [indexed[request.benchmark][day] for day in common]
            benchmark = performance_summary(
                common, [float(r.adjusted_close * r.fx_to_base) for r in benchmark_points]
            )
    overlap: list[dict[str, str]] = []
    compositions = {c.symbol: c for c in request.etf_compositions}
    for symbol, p in universe.items():
        if p.asset_class == "etf":
            composition = compositions.get(symbol)
            overlap.append(
                {
                    "symbol": symbol,
                    "status": "user_supplied_source" if composition else "unknown",
                    "coverage": str(sum(h.weight for h in composition.holdings))
                    if composition
                    else "0",
                    "source": composition.source_url if composition else "",
                    "as_of": str(composition.as_of) if composition else "",
                }
            )
    etfs = sorted(s for s in compositions if s in universe and universe[s].asset_class == "etf")
    for i, a in enumerate(etfs):
        for b in etfs[i + 1 :]:
            aa = {h.issuer_id: h.weight for h in compositions[a].holdings}
            bb = {h.issuer_id: h.weight for h in compositions[b].holdings}
            overlap.append(
                {
                    "symbol": f"{a} / {b}",
                    "status": "known_weight_overlap_lower_bound",
                    "coverage": str(
                        sum((min(w, bb.get(k, Decimal(0))) for k, w in aa.items()), Decimal(0))
                    ),
                    "source": f"{compositions[a].source_url} | {compositions[b].source_url}",
                    "as_of": f"{compositions[a].as_of} | {compositions[b].as_of}",
                }
            )
        known = {h.issuer_id: h.weight for h in compositions[a].holdings}
        for symbol, position in universe.items():
            if position.asset_class == "equity" and position.issuer_id in known:
                overlap.append(
                    {
                        "symbol": f"{a} / {symbol}",
                        "status": "known_direct_issuer_weight",
                        "coverage": str(known[position.issuer_id]),
                        "source": compositions[a].source_url,
                        "as_of": str(compositions[a].as_of),
                    }
                )
    return RiskResult(
        scope=request.scope,
        asset_scope=request.asset_scope,
        out_of_scope=out_of_scope,
        status="complete" if before else "partial_or_insufficient",
        base_currency=request.base_currency,
        valuation_date=valuation_date,
        quantity_date=quantity_date,
        period_start=common[0] if common else None,
        period_end=common[-1] if common else None,
        coverage_fraction=Decimal(1) if complete else None,
        covered_value=total,
        excluded=excluded,
        positions=list(universe.values()),
        before=before,
        after=after,
        benchmark=benchmark,
        benchmark_status="same_currency_and_period" if benchmark else "missing_or_incomplete",
        history_dates=len(common),
        return_dates=return_dates,
        skipped_pairs=skipped,
        history_coverage={s: len(rows) for s, rows in indexed.items()},
        etf_overlap=overlap,
        warnings=warnings,
    )


def allocation_result(
    request: RiskRequest,
    universe: dict[str, RiskPosition],
    symbols: list[str],
    weights: dict[str, Decimal],
    total: Decimal,
    days: list[date],
    relatives: dict[str, list[Decimal]],
    daily_rows: list[list[float]],
    valuation_date: date | None,
) -> AllocationResult:
    values = [
        total * sum((weights[s] * relatives[s][i] for s in symbols), Decimal(0))
        for i in range(len(days))
    ]
    performance = performance_summary(days, [float(v) for v in values])
    exposures: dict[str, dict[str, Decimal]] = {}
    for field in (
        "asset_class",
        "currency",
        "sector",
        "listing_country",
        "issuer_country",
        "economic_currency",
    ):
        groups: dict[str, Decimal] = {}
        for symbol in symbols:
            label = str(getattr(universe[symbol], field) or "unknown")
            groups[label] = groups.get(label, Decimal(0)) + weights[symbol]
        exposures[field] = groups
    scenarios: list[ScenarioResult] = []
    for scenario in request.scenarios:
        if set(scenario.position_shocks) - set(universe):
            raise ValueError("Scenario position shock does not match the analysis universe")
        impacts: dict[str, Decimal] = {}
        for symbol in symbols:
            p = universe[symbol]
            # Specific position shock overrides class shock. It is never added twice.
            shock = scenario.position_shocks.get(
                symbol, scenario.class_shocks.get(p.asset_class, Decimal(0))
            )
            if p.asset_class == "cash" and shock != 0:
                raise ValueError("Cash supports FX shocks only")
            impacts[symbol] = compound_shock(
                total * weights[symbol], shock, scenario.fx_shocks.get(p.currency or "", Decimal(0))
            )
        scenarios.append(scenario_result(request, scenario.name, "hypothetical", total, impacts))
    terminal_impacts = {s: total * weights[s] * (relatives[s][-1] - 1) for s in symbols}
    historic = scenario_result(
        request, f"{days[0]} — {days[-1]}", "historical_current_allocation", total, terminal_impacts
    )
    historic.maximum_drawdown = performance.maximum_drawdown
    scenarios.append(historic)
    risk = allocation_risk(
        symbols, [weights[s] for s in symbols], daily_rows, float(request.confidence)
    )
    curve = list(zip(days, values, strict=True))
    synthetic = all(
        h.origin == "synthetic" for h in request.histories if weights.get(h.symbol, 0) > 0
    )
    diagnostics = equity_diagnostics(
        symbols=symbols,
        weights=weights,
        issuer_ids={s: universe[s].issuer_id for s in symbols},
        daily_rows=daily_rows,
        risk=risk,
        performance=performance,
        curve=curve,
        capital=total,
        equity_symbols={s for s in symbols if universe[s].asset_class == "equity"},
        stale_valuation=not synthetic
        and (valuation_date is None or (datetime.now(UTC).date() - valuation_date).days > 7),
    )
    return AllocationResult(
        value=total,
        weights=weights,
        position_values={s: total * weights[s] for s in symbols},
        var_amount=total * Decimal(str(risk.var_fraction))
        if risk.var_fraction is not None
        else None,
        es_amount=total * Decimal(str(risk.es_fraction)) if risk.es_fraction is not None else None,
        largest_position=max(weights.values()),
        top_five=sum(sorted(weights.values(), reverse=True)[:5], Decimal(0)),
        exposures=exposures,
        risk=risk,
        performance=performance,
        curve=curve,
        scenarios=scenarios,
        diagnostics=diagnostics,
    )


def scenario_result(
    request: RiskRequest, name: str, kind: str, total: Decimal, impacts: dict[str, Decimal]
) -> ScenarioResult:
    pnl = sum(impacts.values(), Decimal(0))
    limits = [
        limit
        for limit in (
            request.tolerance_amount,
            total * request.tolerance_fraction if request.tolerance_fraction is not None else None,
        )
        if limit is not None
    ]
    return ScenarioResult(
        name=name,
        kind=kind,
        status="complete",
        pnl=pnl,
        fraction=pnl / total,
        value_after=total + pnl,
        impacts=impacts,
        largest_losses=sorted((s for s in impacts if impacts[s] < 0), key=lambda s: impacts[s])[:5],
        exceeds_tolerance=(-pnl > min(limits)) if limits else None,
    )
