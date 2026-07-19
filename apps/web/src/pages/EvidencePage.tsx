import { Badge, PageHeading } from "../components/Primitives";
import type { DemoResult, EvidenceRecord } from "../data/demoAdapter";
import { formatUtc } from "../lib/format";

function EvidenceType({ type }: { readonly type: EvidenceRecord["type"] }) {
  const labels: Record<EvidenceRecord["type"], string> = {
    risk_snapshot: "Risk snapshot",
    price_bar: "Market input",
    methodology: "Methodology",
    pipeline_run: "Pipeline run",
  };
  return <Badge tone={type === "risk_snapshot" ? "accent" : "neutral"}>{labels[type]}</Badge>;
}

export function EvidencePage({ result }: { readonly result: DemoResult }) {
  const bundle = result.data;
  if (bundle === null) return null;
  return (
    <div className="page">
      <PageHeading
        eyebrow="Evidence register"
        title="Verify every factual claim"
        description="Versioned demo evidence records connect displayed numbers to calculation methods and synthetic source data."
      />

      <section className="brief-panel" aria-labelledby="brief-title">
        <div className="brief-header">
          <div><p className="panel-kicker">Deterministic fallback · generated 31 Dec 2024, 21:03 UTC</p><h2 id="brief-title">Latest bounded risk brief</h2></div>
          <Badge tone="good">Citations validated</Badge>
        </div>
        <div className="brief-layout">
          <div className="brief-copy">
            <p className="brief-summary">The synthetic portfolio has a one-day 95% Historical VaR of <strong>USD 7,964.48</strong> and Expected Shortfall of <strong>USD 27,263.46</strong>. QTECH is the largest signed risk contributor in this fixture.</p>
            <h3>Main factors</h3>
            <ul>
              <li>QTECH represents 38.7% of portfolio market value and USD 7,978.52 of the reconciled local contribution allocation. <a href="#evidence-risk-001">[1]</a></li>
              <li>The last synthetic QTECH close is USD 95.457199. <a href="#evidence-price-001">[2]</a></li>
              <li>Four invalid quality-case records were quarantined and do not affect the canonical snapshot. <a href="#evidence-pipeline-001">[3]</a></li>
            </ul>
            <h3>Uncertainty &amp; follow-up</h3>
            <p>Historical and normal-distribution estimates can understate losses outside the observed window. Review the scenario laboratory and observation counts; do not treat this brief as a forecast.</p>
          </div>
          <aside className="trace-summary">
            <h3>Tool trace summary</h3>
            <ol><li><span>1</span><p><strong>Read snapshot</strong><small>Read-only · succeeded</small></p></li><li><span>2</span><p><strong>Resolve evidence</strong><small>4 records · succeeded</small></p></li><li><span>3</span><p><strong>Validate numbers</strong><small>Exact match · succeeded</small></p></li></ol>
            <p className="trace-boundary">Compact execution metadata only. No hidden prompts or private reasoning are exposed.</p>
          </aside>
        </div>
      </section>

      <section className="refusal-card" aria-labelledby="refusal-title">
        <span className="refusal-icon" aria-hidden="true">⊘</span>
        <div><p className="panel-kicker">Safety boundary example</p><h2 id="refusal-title">Buy/sell recommendation refused</h2><p>QuantOps can explain observed risk and hypothetical sensitivity, but it cannot recommend a trade, predict direction, or guarantee a return.</p></div>
        <Badge>Expected refusal</Badge>
      </section>

      <section aria-labelledby="records-title">
        <div className="section-heading"><div><p className="panel-kicker">Cited records</p><h2 id="records-title">Evidence records</h2></div><p>{bundle.evidence.length} in-scope records</p></div>
        <div className="evidence-list">
          {bundle.evidence.map((record, index) => (
            <article className="evidence-card" id={record.id} key={record.id} tabIndex={-1}>
              <div className="evidence-index">[{index + 1}]</div>
              <div className="evidence-content">
                <div><EvidenceType type={record.type} /><code>{record.id}</code></div>
                <h3>{record.title}</h3>
                <p>{record.detail}</p>
                <dl><div><dt>Recorded</dt><dd><time dateTime={record.recordedAt}>{formatUtc(record.recordedAt)}</time></dd></div><div><dt>Source</dt><dd>{record.source}</dd></div><div><dt>Checksum</dt><dd><code>{record.checksum}</code></dd></div></dl>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
