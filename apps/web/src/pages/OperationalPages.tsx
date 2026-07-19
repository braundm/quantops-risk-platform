import { Badge, PageHeading, StateNotice } from "../components/Primitives";
import type { DemoResult } from "../data/demoAdapter";
import { formatCurrency, formatInteger, formatUtc } from "../lib/format";

export function MarketPage({ result }: { readonly result: DemoResult }) {
  const bundle = result.data;
  if (bundle === null) return null;
  return (
    <div className="page">
      <PageHeading
        eyebrow="Synthetic market data"
        title="Prices & replay status"
        description="Fictional daily bars with separate simulated market and ingestion timestamps. No live feed is connected."
        actions={<a className="button button-secondary" href="/pipelines">Data quality</a>}
      />
      <StateNotice mode={result.mode} warnings={result.warnings} />
      <section className="replay-status" aria-labelledby="replay-title">
        <div><span className="status-symbol status-neutral" aria-hidden="true">■</span><div><p className="panel-kicker">Replay engine</p><h2 id="replay-title">Stopped · historical batch available</h2><p>The optional event broker is not required for this deterministic view.</p></div></div>
        <dl><div><dt>Scenario</dt><dd>partial_recovery</dd></div><div><dt>Original market time</dt><dd>31 Dec 2024, 21:00 UTC</dd></div><div><dt>Speed</dt><dd>Not running</dd></div></dl>
      </section>
      <section className="panel" aria-labelledby="market-table-title">
        <header className="panel-header"><div><p className="panel-kicker">Latest canonical daily close</p><h2 id="market-table-title">Instrument prices</h2></div><Badge>Entirely synthetic</Badge></header>
        <div className="table-wrap"><table><caption className="sr-only">Latest fictional instrument prices</caption><thead><tr><th scope="col">Instrument</th><th scope="col">Asset class</th><th scope="col">Close</th><th scope="col">Observed</th><th scope="col">Source</th><th scope="col">Quality</th></tr></thead><tbody>{bundle.portfolio.positions.map((position) => <tr key={position.symbol}><th scope="row"><strong>{position.symbol}</strong><small>{position.name}</small></th><td>{position.assetClass}</td><td className="numeric">{formatCurrency(position.lastPrice, true)}</td><td><time dateTime="2024-12-31T21:00:00Z">31 Dec 2024, 21:00 UTC</time></td><td>deterministic generator</td><td><Badge tone={position.dataStatus === "complete" ? "good" : "warning"}>{position.dataStatus}</Badge></td></tr>)}</tbody></table></div>
      </section>
      <section className="market-footnotes"><article><span>522</span><div><h3>Daily observations</h3><p>Monday–Friday fixture dates from January 2023 through December 2024.</p></div></article><article><span>1d</span><div><h3>Supported interval</h3><p>The current fixture does not imply intraday or real-time coverage.</p></div></article><article><span>USD</span><div><h3>Quote currency</h3><p>Unsupported currencies are rejected rather than silently converted.</p></div></article></section>
    </div>
  );
}

export function ModelsPage() {
  return (
    <div className="page">
      <PageHeading
        eyebrow="Risk-regime models"
        title="Regime evaluation, not market prediction"
        description="A deterministic comparison of a rule baseline and a rejected K-Means candidate for synthetic risk-regime classification only."
      />

      <section className="model-status-hero" aria-labelledby="model-state-title">
        <div className="model-status-icon" aria-hidden="true">!</div>
        <div>
          <div className="model-status-labels"><Badge tone="warning">Candidate rejected</Badge><Badge tone="good">Baseline active</Badge></div>
          <h2 id="model-state-title">Automated demo policy retained rule-baseline-v1</h2>
          <p>The selected seed-7 candidate failed the relative macro-F1 and calibration gates. It is not promoted or used as the active classifier.</p>
        </div>
        <dl><div><dt>Promotion status</dt><dd>rejected_by_automated_demo_policy</dd></div><div><dt>Human approval</dt><dd>Not claimed</dd></div></dl>
      </section>

      <div className="content-grid content-grid-wide">
        <section className="panel" aria-labelledby="comparison-title">
          <header className="panel-header"><div><p className="panel-kicker">Held-out synthetic test · 140 rows</p><h2 id="comparison-title">Baseline versus selected candidate</h2></div><Badge>Seed 7</Badge></header>
          <div className="model-comparison">
            <article className="comparison-active"><div><Badge tone="good">Active fallback</Badge><h3>Rule baseline v1</h3></div><dl><div><dt>Macro-F1</dt><dd>0.2710</dd></div><div><dt>Accuracy</dt><dd>0.3643</dd></div><div><dt>Calibration error</dt><dd>0.4260</dd></div></dl></article>
            <div className="comparison-divider" aria-hidden="true">vs</div>
            <article><div><Badge tone="warning">Rejected candidate</Badge><h3>Standardized K-Means v1</h3></div><dl><div><dt>Macro-F1</dt><dd>0.0000</dd></div><div><dt>Accuracy</dt><dd>0.0000</dd></div><div><dt>Calibration error</dt><dd>0.3396</dd></div></dl></article>
          </div>
          <p className="model-metric-note"><span aria-hidden="true">i</span> Test metrics never selected the candidate. Seed 7 is the median validation macro-F1 run across all five declared seeds.</p>
        </section>

        <section className="panel" aria-labelledby="gates-title">
          <header className="panel-header"><div><p className="panel-kicker">Automated promotion policy</p><h2 id="gates-title">Gate results</h2></div><Badge tone="warning">2 failed</Badge></header>
          <ul className="gate-list">
            <li><span className="status-symbol status-good" aria-hidden="true">✓</span><div><strong>Feature schema</strong><small>risk-regime-features-v1</small></div><Badge tone="good">Pass</Badge></li>
            <li><span className="status-symbol status-warning" aria-hidden="true">×</span><div><strong>Relative macro-F1</strong><small>−0.2710; required ≥ −0.02</small></div><Badge tone="warning">Fail</Badge></li>
            <li><span className="status-symbol status-warning" aria-hidden="true">×</span><div><strong>Calibration error</strong><small>0.3396; required ≤ 0.30</small></div><Badge tone="warning">Fail</Badge></li>
            <li><span className="status-symbol status-good" aria-hidden="true">✓</span><div><strong>Point-in-time leakage check</strong><small>Training-only standardizer fit</small></div><Badge tone="good">Pass</Badge></li>
            <li><span className="status-symbol status-good" aria-hidden="true">✓</span><div><strong>Deterministic inference</strong><small>Artifact serialization v1</small></div><Badge tone="good">Pass</Badge></li>
          </ul>
        </section>
      </div>

      <div className="content-grid content-grid-equal">
        <section className="panel drift-panel" aria-labelledby="drift-title">
          <header className="panel-header"><div><p className="panel-kicker">Synthetic perturbation exercise</p><h2 id="drift-title">Operational drift detected</h2></div><Badge tone="warning">Review</Badge></header>
          <div className="drift-metrics"><div><span>Regime JS divergence</span><strong>0.8926</strong><small>threshold 0.10</small></div><div><span>Missing-ratio change</span><strong>0.1200</strong><small>threshold 0.05</small></div><div><span>Max feature PSI</span><strong>27.6310</strong><small>threshold 0.25</small></div></div>
          <p>Thresholds indicate operational change only—not statistical significance, causality, price direction, or market prediction.</p>
        </section>
        <section className="panel" aria-labelledby="tracking-title">
          <header className="panel-header"><div><p className="panel-kicker">Experiment tracking</p><h2 id="tracking-title">MLflow disabled</h2></div><Badge>Optional</Badge></header>
          <p className="tracking-copy">Deterministic local artifacts are authoritative. There is no MLflow run ID and the UI does not imply an external tracking service is connected.</p>
          <dl className="tracking-details"><div><dt>Provider</dt><dd>MLflow</dd></div><div><dt>Status</dt><dd>Disabled</dd></div><div><dt>Run ID</dt><dd>None</dd></div></dl>
        </section>
      </div>

      <section className="model-metadata" aria-labelledby="model-metadata-title">
        <div className="section-heading"><div><p className="panel-kicker">Reproducibility record</p><h2 id="model-metadata-title">Candidate metadata</h2></div><Badge>Deterministic artifact</Badge></div>
        <dl>
          <div><dt>Dataset hash</dt><dd><code>2796bd52…1150</code></dd></div>
          <div><dt>Feature schema</dt><dd>risk-regime-features-v1</dd></div>
          <div><dt>Training window</dt><dd>27 Mar 2023 – 9 Jan 2024</dd></div>
          <div><dt>Selected seed</dt><dd>7 of 5 declared seeds</dd></div>
          <div><dt>Artifact hash</dt><dd><code>f2d3c17f…e14da</code></dd></div>
          <div><dt>Code revision</dt><dd>Not recorded; Git CLI unavailable to run</dd></div>
        </dl>
      </section>

      <section className="panel model-limitations" aria-labelledby="model-limitations-title">
        <header className="panel-header"><div><p className="panel-kicker">Model card boundary</p><h2 id="model-limitations-title">Limitations</h2></div></header>
        <div className="readiness-grid">
          <article><span>01</span><h3>Synthetic only</h3><p>Designed regimes are not evidence of real-market generalization.</p></article>
          <article><span>02</span><h3>No direction target</h3><p>The classifier estimates risk state, not price direction or investment return.</p></article>
          <article><span>03</span><h3>Uneven classes</h3><p>Chronological partitions intentionally have uneven regime coverage.</p></article>
          <article><span>04</span><h3>Distance confidence</h3><p>K-Means confidence is distance-based, not a probabilistic forecast.</p></article>
        </div>
      </section>
    </div>
  );
}

const auditEvents = [
  { id: "audit-001", action: "pipeline.run.completed", actor: "system:synthetic-generator", at: "2025-03-17T08:00:01Z", target: "run-synthetic-20250317", outcome: "succeeded" },
  { id: "audit-002", action: "risk.snapshot.calculated", actor: "system:risk-worker", at: "2025-03-17T08:00:02Z", target: "8c6a5ec2-2034-4d25-8970-a78e5191505c", outcome: "succeeded" },
  { id: "audit-003", action: "quality.record.quarantined", actor: "system:quality-gate", at: "2025-03-17T08:01:01Z", target: "dq-malformed-qtech", outcome: "succeeded" },
  { id: "audit-004", action: "brief.request.refused", actor: "demo-user", at: "2025-03-17T08:02:00Z", target: "prohibited-trading-advice", outcome: "policy_refusal" },
] as const;

export function AuditPage() {
  return (
    <div className="page">
      <PageHeading
        eyebrow="Safe audit viewer"
        title="Recorded actions, bounded detail"
        description="A read-only deterministic fixture of security- and lineage-relevant events. Secrets, request bodies, and hidden prompts are excluded."
      />
      <section className="audit-boundary" role="note"><span aria-hidden="true">i</span><p><strong>Safe fields only.</strong> This viewer shows stable event identity, actor class, action, target identity, outcome, and UTC time. It does not render credentials or sensitive payloads.</p></section>
      <section className="panel" aria-labelledby="audit-title"><header className="panel-header"><div><p className="panel-kicker">Deterministic local records</p><h2 id="audit-title">Audit events</h2></div><Badge>{formatInteger(auditEvents.length)} events</Badge></header><div className="table-wrap"><table><caption className="sr-only">Safe audit events</caption><thead><tr><th scope="col">Event</th><th scope="col">Action</th><th scope="col">Actor</th><th scope="col">Target</th><th scope="col">Outcome</th><th scope="col">Time</th></tr></thead><tbody>{auditEvents.map((event) => <tr key={event.id}><th scope="row"><code>{event.id}</code></th><td>{event.action}</td><td>{event.actor}</td><td><code>{event.target}</code></td><td><Badge tone={event.outcome === "policy_refusal" ? "warning" : "good"}>{event.outcome}</Badge></td><td><time dateTime={event.at}>{formatUtc(event.at)}</time></td></tr>)}</tbody></table></div></section>
    </div>
  );
}
