import { useState } from "react";

import { Badge, PageHeading, StateNotice } from "../components/Primitives";
import type { DemoResult } from "../data/demoAdapter";
import { formatCurrency, formatPercent, formatUtc } from "../lib/format";

const SCENARIO_RUN_IDS = {
  combined_liquidity_stress: "97affe896f9e605f093807b3049f6dcce2999e8ce4450ea45bb50512935efe49",
  cross_asset_correlation_breakdown: "62dd53d5eb2dcb02590b9f083c6c004612b6edb6a63abc45b3ca1047f54cbb8f",
  equity_selloff_15pct: "e5d944bd7788738e9dea9b3ebbe5b2cb96e3507a04adb35b78b93de1c5a8c832",
  gold_down_10pct: "8bf665f672e0f5b5997e761fc00108dd0a2aaf39a1137bffa89ed739cffff0ba",
  oil_spike_25pct: "151393dc4fc82657b0c445649758ccd93e321aa53f8d9c761327731264754724",
  custom: "scn-custom-local-preview",
} as const;

function roundFinancialAmount(value: number): number {
  return Math.round((value + Number.EPSILON) * 10_000) / 10_000;
}

export function ScenarioPage({ result }: { readonly result: DemoResult }) {
  const bundle = result.data;
  const [scenarioId, setScenarioId] = useState("cross_asset_correlation_breakdown");
  const [customShock, setCustomShock] = useState("-10");
  if (bundle === null) return null;

  const { portfolio, scenarios } = bundle;
  const selected = scenarios.find((scenario) => scenario.id === scenarioId) ?? scenarios[0];
  if (selected === undefined) return null;
  const parsedShock = Number(customShock);
  const customIsValid = Number.isFinite(parsedShock) && parsedShock >= -100 && parsedShock <= 100;
  const isCustom = scenarioId === "custom";
  const customImpact = customIsValid
    ? roundFinancialAmount(portfolio.positions[0]!.marketValue * (parsedShock / 100))
    : 0;
  const impact = isCustom ? customImpact : selected.impact;
  const stressedValue = roundFinancialAmount(portfolio.value + impact);
  const runId = SCENARIO_RUN_IDS[scenarioId as keyof typeof SCENARIO_RUN_IDS] ?? SCENARIO_RUN_IDS.custom;
  const exportPayload = encodeURIComponent(
    JSON.stringify(
      {
        schema_version: "1.0.0",
        run_id: runId,
        scenario: isCustom ? "Custom QTECH shock" : selected.name,
        portfolio_id: portfolio.id,
        base_value_usd: portfolio.value,
        stressed_value_usd: stressedValue,
        impact_usd: impact,
        is_synthetic: true,
      },
      null,
      2,
    ),
  );

  return (
    <div className="page">
      <PageHeading
        eyebrow="Scenario laboratory"
        title="Explore hypothetical stress"
        description="Compare deterministic shocks without treating them as forecasts or trading signals."
        actions={<a className="button button-secondary" href={`/portfolios/${portfolio.id}`}>Back to portfolio</a>}
      />
      <StateNotice mode={result.mode} warnings={result.warnings} />

      <div className="scenario-grid">
        <section className="panel scenario-controls" aria-labelledby="scenario-controls-title">
          <header className="panel-header"><div><p className="panel-kicker">Versioned inputs</p><h2 id="scenario-controls-title">Configure scenario</h2></div><Badge>USD only</Badge></header>
          <form onSubmit={(event) => event.preventDefault()}>
            <label htmlFor="scenario">System scenario</label>
            <select id="scenario" value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}>
              {scenarios.map((scenario) => <option key={scenario.id} value={scenario.id}>{scenario.name} · v{scenario.version}</option>)}
              <option value="custom">Custom QTECH shock · local preview</option>
            </select>

            {isCustom ? (
              <div className="field-group">
                <label htmlFor="custom-shock">QTECH price shock (%)</label>
                <div className="input-suffix"><input aria-describedby="shock-help shock-error" id="custom-shock" max="100" min="-100" step="0.1" type="number" value={customShock} onChange={(event) => setCustomShock(event.target.value)} /><span>%</span></div>
                <small id="shock-help">Enter a finite percentage from −100% to +100%.</small>
                {customIsValid ? null : <p className="field-error" id="shock-error" role="alert">Shock must be between −100% and +100%.</p>}
              </div>
            ) : (
              <div className="scenario-description"><strong>{selected.name}</strong><p>{selected.description}</p></div>
            )}

            <fieldset>
              <legend>Fixed assumptions</legend>
              <label className="readonly-check"><input checked disabled type="checkbox" /> Positions held constant</label>
              <label className="readonly-check"><input checked disabled type="checkbox" /> USD conversion held constant</label>
              <label className="readonly-check"><input checked disabled type="checkbox" /> Instantaneous shock</label>
            </fieldset>
            <p className="form-boundary"><span aria-hidden="true">i</span> Scenario outputs are hypothetical sensitivity results, not predictions.</p>
          </form>
        </section>

        <section className="panel scenario-result" aria-labelledby="scenario-result-title" aria-live="polite">
          <header className="panel-header"><div><p className="panel-kicker">Deterministic result</p><h2 id="scenario-result-title">{isCustom ? "Custom QTECH shock" : selected.name}</h2></div><Badge tone={customIsValid ? "accent" : "warning"}>{customIsValid ? "Preview" : "Invalid"}</Badge></header>
          {customIsValid ? (
            <>
              <div className="impact-summary">
                <div><span>Base value</span><strong>{formatCurrency(portfolio.value, true)}</strong></div>
                <span className="impact-arrow" aria-hidden="true">→</span>
                <div><span>Stressed value</span><strong>{formatCurrency(stressedValue, true)}</strong></div>
              </div>
              <div className="impact-callout">
                <span>Total hypothetical impact</span>
                <strong>{formatCurrency(impact, true)} <small>({formatPercent(impact / portfolio.value)})</small></strong>
              </div>
              <div className="component-impact">
                <h3>Component impacts</h3>
                <ul>
                  {(isCustom
                    ? portfolio.positions.map((position, index) => ({ symbol: position.symbol, impact: index === 0 ? customImpact : 0 }))
                    : selected.componentImpacts
                  ).map((component) => (
                    <li key={component.symbol}><span>{component.symbol}</span><span className="impact-bar"><i style={{ width: `${Math.max(2, Math.min(100, Math.abs(component.impact / Math.min(impact || 1, -1)) * 100))}%` }} /></span><strong>{formatCurrency(component.impact)}</strong></li>
                  ))}
                </ul>
              </div>
              <dl className="run-metadata">
                <div><dt>{isCustom ? "Preview run ID" : "Immutable run ID"}</dt><dd><code>{runId}</code></dd></div>
                <div><dt>Snapshot as of</dt><dd><time dateTime={portfolio.asOf}>{formatUtc(portfolio.asOf)}</time></dd></div>
                <div><dt>Scenario version</dt><dd>{isCustom ? "local preview" : selected.version}</dd></div>
              </dl>
              <div className="result-actions">
                <a className="button button-secondary" download={`${runId}.json`} href={`data:application/json;charset=utf-8,${exportPayload}`}>Export JSON</a>
                <a className="text-link" href="/evidence#evidence-risk-001">Verify base snapshot →</a>
              </div>
            </>
          ) : <div className="invalid-result"><span aria-hidden="true">!</span><p>Correct the shock percentage to produce a scenario preview.</p></div>}
        </section>
      </div>

      <section className="panel assumptions-panel" aria-labelledby="assumptions-title">
        <header className="panel-header"><div><p className="panel-kicker">Interpretation boundary</p><h2 id="assumptions-title">Assumptions &amp; limitations</h2></div><a href="/methodology#scenarios">Methodology →</a></header>
        <ol>
          {(isCustom ? ["Instantaneous deterministic QTECH price shock", "All other prices and positions held constant", "No liquidity, execution, or second-order effects"] : selected.assumptions).map((assumption, index) => <li key={assumption}><span>0{index + 1}</span><p>{assumption}</p></li>)}
        </ol>
      </section>
    </div>
  );
}
