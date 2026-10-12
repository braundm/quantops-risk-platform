"""Self-contained, escaped HTML report with reproducible input evidence."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quantops_api.api.treasury import TreasuryResult


def render_report(result: TreasuryResult) -> str:
    def cell(value: object) -> str:
        return escape(str(value))

    bonds = "".join(
        f"<tr><td>{cell(b.name)}</td><td>{b.quantity}</td><td>{b.value:.2f}</td>"
        f"<td>{b.metrics.macaulay_duration:.4f}</td><td>{b.metrics.modified_duration:.4f}</td>"
        f"<td>{b.signed_dv01:.4f}</td><td>{b.metrics.convexity:.4f}</td></tr>"
        for b in result.bonds
    )
    contributions = {
        s.shock_bp: cell(
            "; ".join(f"{b.name}: {s.pnl_by_position[b.id]:.2f}" for b in result.bonds)
        )
        for s in result.scenarios
    }
    scenarios = "".join(
        f"<tr><td>{s.shock_bp:+d}</td><td>{s.before:.2f}</td><td>{s.after:.2f}</td><td>{s.pnl:.2f}</td>"
        f"<td>{contributions[s.shock_bp]}</td></tr>"
        for s in result.scenarios
    )
    liquidity = "".join(
        f"<tr><td>{cell(p.name)}</td><td>{p.status}</td><td>{p.estimate.observations}</td>"
        f"<td>{cell(p.first_date)} to {cell(p.last_date)}</td><td>{cell(p.estimate.adv)}</td>"
        f"<td>{cell(p.estimate.position_to_adv)}</td><td>{cell(p.estimate.days)}</td><td>{p.limit_status}</td></tr>"
        for p in result.liquidity
    )
    assumptions = "".join(f"<li>{cell(a)}</li>" for a in result.assumptions)
    evidence = escape(result.inputs.model_dump_json(indent=2))
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QuantOps Treasury risk report</title>
<style>body{{font:15px system-ui;color:#18312d;max-width:1100px;margin:40px auto;padding:20px}}
h1,h2{{color:#153e35}}table{{border-collapse:collapse;width:100%;font-size:13px}}
td,th{{padding:10px;text-align:left;border-bottom:1px solid #b3c9c1}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef4f1;padding:16px}}
li{{margin:8px 0}}@media print{{body{{margin:0}}tr{{break-inside:avoid}}}}</style>
<h1>QuantOps · Treasury risk report</h1>
<p><strong>{result.origin.upper()} · UNVERIFIED INPUTS</strong></p>
<p>Valuation: {result.valuation_date} · Generated: {result.generated_at.isoformat()}
· {result.methodology_version}</p>
<p>Source: {cell(result.source_note)} · Currency: {result.currency}</p>
<h2>Bond summary</h2>
<p>Net value: {result.net_value:.2f} · Gross value: {result.gross_value:.2f}<br>
Signed DV01: {result.signed_dv01:.4f} {result.currency}/bp · Gross DV01: {result.gross_dv01:.4f}<br>
Absolute net DV01 limit: {cell(result.inputs.max_abs_dv01)} · Status: {result.dv01_limit_status}</p>
<table><tr><th>Bond</th><th>Quantity</th><th>Value</th><th>Macaulay years</th>
<th>Modified duration</th><th>Signed DV01</th><th>Convexity</th></tr>{bonds}</table>
<h2>Parallel yield shocks · full repricing</h2><table><tr><th>bp</th><th>Before</th>
<th>After</th><th>P&amp;L</th><th>Position P&amp;L</th></tr>{scenarios}</table>
<h2>Separate equity liquidity book</h2><p>Participation: {result.inputs.participation * 100}% ADV
· Limit: {result.inputs.max_liquidation_days} days<br>
Usable value coverage: {cell(result.liquidity_coverage_pct)}% · Liquidatable in 1 / 5 days:
{cell(result.liquidatable_one_day_pct)}% / {cell(result.liquidatable_five_days_pct)}%<br>
None means unavailable; whole-book liquidation estimates require complete usable coverage.</p>
<table><tr><th>Position</th><th>Quality</th><th>Sessions</th><th>Range</th><th>ADV</th>
<th>Position/ADV</th><th>Days</th><th>Limit</th></tr>{liquidity}</table>
<h2>Assumptions and limitations</h2><ul>{assumptions}</ul>
<h2>Reproduction inputs</h2><pre>{evidence}</pre></html>"""
