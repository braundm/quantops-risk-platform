import { Badge, PageHeading, StateNotice } from "../components/Primitives";
import type { DemoResult } from "../data/demoAdapter";
import { formatInteger, formatUtc } from "../lib/format";

export function PipelinePage({ result }: { readonly result: DemoResult }) {
  const bundle = result.data;
  if (bundle === null) return null;

  return (
    <div className="page">
      <PageHeading
        eyebrow="Data operations"
        title="Pipelines & data quality"
        description="Watermarks, acceptance decisions, and deliberately isolated failure cases for the deterministic fixture."
        actions={<a className="button button-secondary" href="/evidence#evidence-pipeline-001">Pipeline evidence</a>}
      />
      <StateNotice mode={result.mode} warnings={result.warnings} />

      <section className="quality-summary" aria-label="Data quality summary">
        <article><span className="summary-icon summary-good" aria-hidden="true">✓</span><div><span>Canonical acceptance</span><strong>2,088</strong><small>all expected bars</small></div></article>
        <article><span className="summary-icon summary-good" aria-hidden="true">↺</span><div><span>Repeat generation</span><strong>0 writes</strong><small>11 files unchanged</small></div></article>
        <article><span className="summary-icon summary-warning" aria-hidden="true">!</span><div><span>Quality cases</span><strong>4</strong><small>all quarantined</small></div></article>
        <article><span className="summary-icon summary-neutral" aria-hidden="true">◷</span><div><span>Watermark</span><strong>31 Dec</strong><small>21:00 UTC</small></div></article>
      </section>

      <section className="panel" aria-labelledby="runs-title">
        <header className="panel-header"><div><p className="panel-kicker">Latest deterministic executions</p><h2 id="runs-title">Pipeline runs</h2></div><Badge tone={result.mode === "offline" ? "warning" : "good"}>{result.mode === "offline" ? "Broker offline · batch available" : "Batch mode"}</Badge></header>
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Pipeline run status and watermarks</caption>
            <thead><tr><th scope="col">Run</th><th scope="col">Status</th><th scope="col">Completed</th><th scope="col">Watermark</th><th scope="col">Accepted</th><th scope="col">Quarantined</th></tr></thead>
            <tbody>
              {bundle.pipelineRuns.map((run) => (
                <tr key={run.id}>
                  <th scope="row"><strong>{run.pipeline}</strong><small>{run.id}</small></th>
                  <td><Badge tone={run.status === "succeeded" ? "good" : "warning"}>{run.status}</Badge></td>
                  <td><time dateTime={run.completedAt ?? run.startedAt}>{formatUtc(run.completedAt ?? run.startedAt)}</time></td>
                  <td><time dateTime={run.watermark}>{formatUtc(run.watermark)}</time></td>
                  <td className="numeric">{formatInteger(run.accepted)}</td>
                  <td className="numeric">{formatInteger(run.quarantined)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel" aria-labelledby="issues-title">
        <header className="panel-header"><div><p className="panel-kicker">Isolated test records</p><h2 id="issues-title">Quality issues</h2></div><Badge tone="warning">4 quarantined</Badge></header>
        <div className="issue-list">
          {bundle.qualityIssues.map((issue) => (
            <article className="quality-issue" key={issue.id}>
              <div className="issue-heading">
                <span className={`issue-symbol issue-${issue.severity}`} aria-hidden="true">{issue.severity === "error" ? "×" : "!"}</span>
                <div><h3>{issue.code}</h3><p>{issue.instrument} · <time dateTime={issue.observedAt}>{formatUtc(issue.observedAt)}</time></p></div>
                <Badge tone={issue.severity === "error" ? "danger" : "warning"}>{issue.severity}</Badge>
              </div>
              <p>{issue.description}</p>
              <dl><div><dt>Remediation</dt><dd>{issue.remediation}</dd></div><div><dt>Downstream risk</dt><dd>{issue.downstreamImpact}</dd></div></dl>
            </article>
          ))}
        </div>
      </section>

      <section className="lineage-band" aria-labelledby="lineage-band-title">
        <div><p className="panel-kicker">Dataset identity</p><h2 id="lineage-band-title">Reproducible from source to checksum</h2><p>The fixture generator uses a fixed seed and stable serialization. Invalid records live in a separate quality-case dataset.</p></div>
        <dl><div><dt>Seed</dt><dd>{bundle.fixture.seed}</dd></div><div><dt>Version</dt><dd>{bundle.fixture.datasetVersion}</dd></div><div><dt>Range</dt><dd>{bundle.fixture.generatedRange}</dd></div><div><dt>SHA-256</dt><dd><code>2796bd52…1150</code></dd></div></dl>
      </section>
    </div>
  );
}
