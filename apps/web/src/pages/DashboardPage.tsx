import { Badge, LineChart, MetricCard, PageHeading, StateNotice } from "../components/Primitives";
import type { DemoResult } from "../data/demoAdapter";
import { formatCurrency, formatPercent, formatUtc } from "../lib/format";

export function DashboardPage({ result }: { readonly result: DemoResult }) {
  const bundle = result.data;
  if (bundle === null) return null;
  const { portfolio } = bundle;
  const contributionTotal = portfolio.positions.reduce((sum, position) => sum + position.contribution, 0);
  const maximumWeight = Math.max(...portfolio.positions.map((position) => position.weight));

  return (
    <div className="page">
      <PageHeading
        eyebrow="Portfolio overview"
        title="Risk at a glance"
        description="A deterministic historical replay of a fictional multi-asset portfolio."
        actions={
          <>
            <a className="button button-secondary" href={`/portfolios/${portfolio.id}`}>Portfolio detail</a>
            <a className="button button-primary" href={`/portfolios/${portfolio.id}/scenarios`}>Run scenario</a>
          </>
        }
      />
      <StateNotice mode={result.mode} warnings={result.warnings} />

      <section className="snapshot-hero" aria-labelledby="snapshot-title">
        <div>
          <div className="section-title-row">
            <p id="snapshot-title">{portfolio.name}</p>
            <Badge tone="accent">Historical replay</Badge>
          </div>
          <strong className="portfolio-value">{formatCurrency(portfolio.value, true)}</strong>
          <span className="as-of">
            As of <time dateTime={portfolio.asOf}>{formatUtc(portfolio.asOf)}</time>
          </span>
        </div>
        <dl className="snapshot-metadata">
          <div><dt>Snapshot</dt><dd>{portfolio.snapshotId.slice(0, 8)}…</dd></div>
          <div><dt>Base currency</dt><dd>{portfolio.baseCurrency}</dd></div>
          <div><dt>Positions</dt><dd>{portfolio.positions.length}</dd></div>
          <div><dt>Data quality</dt><dd><Badge tone={result.mode === "partial" ? "warning" : "good"}>{result.mode === "partial" ? "Partial" : "Complete"}</Badge></dd></div>
        </dl>
      </section>

      <section className="metric-grid" aria-label="Latest risk metrics">
        {portfolio.metrics.map((metric) => <MetricCard key={metric.label} metric={metric} />)}
      </section>

      <div className="content-grid content-grid-wide">
        <section className="panel chart-panel" aria-labelledby="risk-history-title">
          <header className="panel-header">
            <div><p className="panel-kicker">Six-month history</p><h2 id="risk-history-title">Historical VaR</h2></div>
            <Badge>USD · 95% · 1 day</Badge>
          </header>
          <LineChart points={portfolio.history} value="historicalVar" label="Historical VaR in USD over six month-end observations" />
        </section>

        <section className="panel" aria-labelledby="exposure-title">
          <header className="panel-header"><div><p className="panel-kicker">Gross allocation</p><h2 id="exposure-title">Exposure</h2></div><Badge>{formatPercent(maximumWeight)} max</Badge></header>
          <div className="exposure-list">
            {portfolio.positions.map((position) => (
              <div className="exposure-row" key={position.symbol}>
                <div><strong>{position.symbol}</strong><span>{formatCurrency(position.marketValue)}</span></div>
                <div className="bar-track" aria-label={`${position.symbol} ${formatPercent(position.weight)} of portfolio`}>
                  <span style={{ width: `${position.weight * 100}%` }} />
                </div>
                <b>{formatPercent(position.weight)}</b>
              </div>
            ))}
          </div>
          <p className="panel-note"><span aria-hidden="true">i</span> HHI concentration: 0.2806 · moderate synthetic concentration.</p>
        </section>
      </div>

      <div className="content-grid content-grid-equal">
        <section className="panel" aria-labelledby="contributors-title">
          <header className="panel-header"><div><p className="panel-kicker">Signed Euler allocation</p><h2 id="contributors-title">Risk contribution</h2></div><a href="/evidence#evidence-risk-001">Evidence →</a></header>
          <div className="table-wrap">
            <table>
              <caption className="sr-only">Instrument contributions to parametric Value at Risk</caption>
              <thead><tr><th scope="col">Instrument</th><th scope="col">Contribution</th><th scope="col">Share</th><th scope="col">Status</th></tr></thead>
              <tbody>
                {portfolio.positions.map((position) => (
                  <tr key={position.symbol}>
                    <th scope="row"><span className={`instrument-dot dot-${position.symbol.toLowerCase()}`} aria-hidden="true" />{position.symbol}</th>
                    <td className="numeric">{formatCurrency(position.contribution)}</td>
                    <td className="numeric">{formatPercent(position.contribution / contributionTotal)}</td>
                    <td><Badge tone="good">Reconciled</Badge></td>
                  </tr>
                ))}
              </tbody>
              <tfoot><tr><th scope="row">Total</th><td className="numeric">{formatCurrency(contributionTotal)}</td><td className="numeric">100.0%</td><td><Badge tone="good">Exact</Badge></td></tr></tfoot>
            </table>
          </div>
        </section>

        <section className="panel" aria-labelledby="operations-title">
          <header className="panel-header"><div><p className="panel-kicker">Latest assurance signals</p><h2 id="operations-title">Data &amp; model status</h2></div><a href="/pipelines">Inspect →</a></header>
          <ul className="status-list">
            <li><span className="status-symbol status-good" aria-hidden="true">✓</span><div><strong>Canonical market fixture</strong><small>2,088 / 2,088 bars accepted</small></div><Badge tone="good">Complete</Badge></li>
            <li><span className="status-symbol status-good" aria-hidden="true">✓</span><div><strong>Risk snapshot</strong><small>Methodology 1.0.0 · deterministic</small></div><Badge tone="good">Valid</Badge></li>
            <li><span className="status-symbol status-neutral" aria-hidden="true">–</span><div><strong>Regime model</strong><small>Not yet connected in this milestone</small></div><Badge>Unavailable</Badge></li>
            <li><span className="status-symbol status-warning" aria-hidden="true">!</span><div><strong>Quality-case fixture</strong><small>4 deliberately invalid records</small></div><Badge tone="warning">Quarantined</Badge></li>
          </ul>
        </section>
      </div>

      <section className="method-strip" aria-label="Methodology summary">
        <div><span className="method-number">1.0</span><span><strong>{portfolio.methodology.name}</strong><small>Methodology version {portfolio.methodology.version}</small></span></div>
        <dl>
          <div><dt>Confidence</dt><dd>{formatPercent(portfolio.methodology.confidence)}</dd></div>
          <div><dt>Window</dt><dd>{portfolio.methodology.window} observations</dd></div>
          <div><dt>Horizon</dt><dd>{portfolio.methodology.horizon} day</dd></div>
        </dl>
        <a className="button button-secondary" href="/methodology">Read methodology</a>
      </section>
    </div>
  );
}
