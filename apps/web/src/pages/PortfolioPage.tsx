import { Badge, LineChart, PageHeading, StateNotice } from "../components/Primitives";
import type { DemoResult } from "../data/demoAdapter";
import { formatCurrency, formatInteger, formatPercent, formatUtc } from "../lib/format";

function correlationTone(value: number): string {
  const magnitude = Math.abs(value);
  if (value === 1) return "correlation-self";
  if (magnitude >= 0.7) return "correlation-high";
  if (magnitude >= 0.4) return "correlation-medium";
  return "correlation-low";
}

export function PortfolioPage({ result }: { readonly result: DemoResult }) {
  const bundle = result.data;
  if (bundle === null) return null;
  const { portfolio } = bundle;
  const symbols = portfolio.positions.map((position) => position.symbol);

  return (
    <div className="page">
      <PageHeading
        eyebrow="Portfolio / QO-SYN-01"
        title={portfolio.name}
        description="Positions, concentration, risk history, and input completeness for a fictional research portfolio."
        actions={
          <a className="button button-primary" href={`/portfolios/${portfolio.id}/scenarios`}>
            Open scenario laboratory
          </a>
        }
      />
      <StateNotice mode={result.mode} warnings={result.warnings} />

      <section className="portfolio-summary" aria-label="Portfolio summary">
        <div><span>Net market value</span><strong>{formatCurrency(portfolio.value, true)}</strong><small>{portfolio.baseCurrency} base currency</small></div>
        <div><span>Latest price time</span><strong><time dateTime={portfolio.asOf}>{formatUtc(portfolio.asOf)}</time></strong><small>Simulated market timestamp</small></div>
        <div><span>Input coverage</span><strong>{result.mode === "partial" ? "75.0%" : "100.0%"}</strong><small>{result.mode === "partial" ? "One instrument is late" : "All expected inputs present"}</small></div>
        <div><span>Risk status</span><strong>{result.mode === "insufficient" ? "Insufficient" : "Valid"}</strong><small>Calculation status, not a recommendation</small></div>
      </section>

      <section className="panel" aria-labelledby="positions-title">
        <header className="panel-header">
          <div><p className="panel-kicker">As-of positions</p><h2 id="positions-title">Holdings &amp; exposures</h2></div>
          <Badge>{portfolio.positions.length} fictional instruments</Badge>
        </header>
        <div className="table-wrap positions-table">
          <table>
            <caption className="sr-only">Synthetic portfolio positions and market values</caption>
            <thead><tr><th scope="col">Instrument</th><th scope="col">Asset class</th><th scope="col">Quantity</th><th scope="col">Last price</th><th scope="col">Market value</th><th scope="col">Weight</th><th scope="col">Data</th></tr></thead>
            <tbody>
              {portfolio.positions.map((position) => (
                <tr key={position.symbol}>
                  <th scope="row"><strong>{position.symbol}</strong><small>{position.name}</small></th>
                  <td>{position.assetClass}</td>
                  <td className="numeric">{formatInteger(position.quantity)}</td>
                  <td className="numeric">{formatCurrency(position.lastPrice, true)}</td>
                  <td className="numeric"><strong>{formatCurrency(position.marketValue)}</strong></td>
                  <td className="numeric">{formatPercent(position.weight)}</td>
                  <td><Badge tone={position.dataStatus === "complete" ? "good" : "warning"}>{position.dataStatus === "complete" ? "Complete" : "Late"}</Badge></td>
                </tr>
              ))}
            </tbody>
            <tfoot><tr><th scope="row" colSpan={4}>Portfolio total</th><td className="numeric">{formatCurrency(portfolio.value, true)}</td><td className="numeric">100.0%</td><td /></tr></tfoot>
          </table>
        </div>
      </section>

      <div className="content-grid content-grid-wide">
        <section className="panel chart-panel" aria-labelledby="value-history-title">
          <header className="panel-header"><div><p className="panel-kicker">Month-end observations</p><h2 id="value-history-title">Portfolio value history</h2></div><Badge>USD</Badge></header>
          <LineChart points={portfolio.history} value="portfolioValue" label="Portfolio value in USD over six month-end observations" />
        </section>
        <section className="panel" aria-labelledby="lineage-title">
          <header className="panel-header"><div><p className="panel-kicker">Input lineage</p><h2 id="lineage-title">Data status</h2></div><a href="/pipelines">Full quality view →</a></header>
          <dl className="definition-list">
            <div><dt>Dataset</dt><dd>synthetic-market-data@1.0.0</dd></div>
            <div><dt>Generator seed</dt><dd>20250317</dd></div>
            <div><dt>Canonical bars</dt><dd>2,088 accepted</dd></div>
            <div><dt>Source interval</dt><dd>Daily close</dd></div>
            <div><dt>Latest watermark</dt><dd><time dateTime="2024-12-31T21:00:00Z">31 Dec 2024, 21:00 UTC</time></dd></div>
            <div><dt>Quarantine</dt><dd>4 isolated quality cases</dd></div>
          </dl>
          <a className="inline-evidence" href="/evidence#evidence-pipeline-001"><span aria-hidden="true">↗</span> Open source-run evidence</a>
        </section>
      </div>

      <section className="panel" aria-labelledby="correlation-title">
        <header className="panel-header">
          <div><p className="panel-kicker">Pairwise return observations</p><h2 id="correlation-title">Correlation structure</h2></div>
          <Badge tone="warning">Min n = 520</Badge>
        </header>
        <div className="correlation-layout">
          <div className="correlation-table-wrap">
            <table className="correlation-table">
              <caption className="sr-only">Pairwise correlations with observation counts</caption>
              <thead><tr><td /><th scope="col">QTECH</th><th scope="col">QGOLD</th><th scope="col">QWTI</th><th scope="col">QCASH</th></tr></thead>
              <tbody>
                {symbols.map((row) => (
                  <tr key={row}>
                    <th scope="row">{row}</th>
                    {symbols.map((column) => {
                      const cell = portfolio.correlations.find((candidate) => candidate.row === row && candidate.column === column);
                      if (cell === undefined) return <td key={column}>—</td>;
                      return (
                        <td className={correlationTone(cell.value)} key={column} title={`${cell.observations} observations`}>
                          <strong>{cell.value.toFixed(2)}</strong><small>n={cell.observations}</small>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <aside className="correlation-note">
            <span className="notice-icon" aria-hidden="true">!</span>
            <div><strong>Observation counts matter</strong><p>Pairwise alignment uses 520 observations for cross-instrument cells. Values with different sample sizes should not be compared without this context.</p><a href="/methodology#correlation">Review alignment assumptions →</a></div>
          </aside>
        </div>
      </section>
    </div>
  );
}
