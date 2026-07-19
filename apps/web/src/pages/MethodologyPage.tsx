import { Badge, PageHeading } from "../components/Primitives";

const methods = [
  {
    index: "01",
    id: "historical-var",
    title: "Historical Value at Risk",
    formula: "VaR₍c₎ = Q₍c₎(−V · rₜ)",
    text: "Daily arithmetic portfolio returns become nonnegative loss amounts. The configured confidence percentile is selected with an explicit linear empirical quantile and floored at zero if it is a gain.",
    assumptions: ["500 aligned observations", "One-day horizon", "Current positions held constant"],
  },
  {
    index: "02",
    id: "expected-shortfall",
    title: "Expected Shortfall",
    formula: "ES₍c₎ = E[L | L ≥ VaR₍c₎]",
    text: "The mean observed loss at or beyond the interpolated Historical VaR threshold. A single tail observation is reported as unstable rather than silently presented as robust.",
    assumptions: ["Inclusive tail boundary", "Same loss convention as VaR", "Typed unstable status"],
  },
  {
    index: "03",
    id: "parametric-var",
    title: "Parametric Value at Risk",
    formula: "VaR₍c₎ = max(0, −h·xᵀμ + z₍c₎σₚ)",
    text: "A variance-covariance estimate using signed monetary exposures, aligned returns, and sample covariance. Normality is an approximation, not a claim about market behavior.",
    assumptions: ["Normal approximation", "Stable covariance estimate", "Signed exposure vector"],
  },
  {
    index: "04",
    id: "drawdown",
    title: "Maximum drawdown",
    formula: "Dₜ = Vₜ / max₍s≤t₎ Vₛ − 1",
    text: "The deepest nonnegative peak-to-trough loss over supplied portfolio values, with peak, first deepest trough, and first recovery dates retained where available.",
    assumptions: ["Positive portfolio values", "Chronological inputs", "No interpolation between dates"],
  },
] as const;

export function MethodologyPage() {
  return (
    <div className="page methodology-page">
      <PageHeading
        eyebrow="Methodology 1.0.0"
        title="Risk methods, without a black box"
        description="Definitions, assumptions, and typed failure states for the calculations shown in the synthetic demo."
        actions={<a className="button button-secondary" href="/evidence#evidence-method-001">Method evidence</a>}
      />

      <section className="method-overview" aria-label="Methodology scope">
        <div><span>Version</span><strong>1.0.0</strong><small>Immutable calculation identity</small></div>
        <div><span>Loss convention</span><strong>Positive amount</strong><small>Greater value means greater loss</small></div>
        <div><span>Demo confidence</span><strong>95%</strong><small>Explicit on every snapshot</small></div>
        <div><span>Authoritative engine</span><strong>Deterministic</strong><small>No LLM calculations</small></div>
      </section>

      <div className="methodology-layout">
        <aside className="method-toc">
          <p>On this page</p>
          <nav aria-label="Methodology sections">
            {methods.map((method) => <a href={`#${method.id}`} key={method.id}>{method.index} {method.title}</a>)}
            <a href="#correlation">05 Correlation</a>
            <a href="#scenarios">06 Scenarios</a>
            <a href="#limitations">07 Limitations</a>
          </nav>
        </aside>

        <div className="method-content">
          {methods.map((method) => (
            <section className="method-block" id={method.id} key={method.id}>
              <div className="method-index">{method.index}</div>
              <div><div className="method-title"><h2>{method.title}</h2><Badge>Implemented</Badge></div><p>{method.text}</p><code className="formula">{method.formula}</code><h3>Visible assumptions</h3><ul>{method.assumptions.map((assumption) => <li key={assumption}>{assumption}</li>)}</ul></div>
            </section>
          ))}

          <section className="method-block" id="correlation">
            <div className="method-index">05</div>
            <div><div className="method-title"><h2>Pairwise correlation</h2><Badge>Counts retained</Badge></div><p>Returns are aligned by explicit timestamp intersection. Each matrix cell retains its observation count so missingness cannot masquerade as comparable statistical support.</p><code className="formula">ρ₍ᵢⱼ₎ = cov(rᵢ, rⱼ) / (σᵢσⱼ)</code><div className="method-callout"><span aria-hidden="true">!</span><p>Correlation is descriptive over the supplied window. It is not stable by assumption and can change sharply under stress.</p></div></div>
          </section>

          <section className="method-block" id="scenarios">
            <div className="method-index">06</div>
            <div><div className="method-title"><h2>Deterministic scenarios</h2><Badge>Hypothetical</Badge></div><p>Versioned shocks transform current positions under declared price, FX, volatility, or correlation assumptions. Base value, stressed value, component impacts, and an immutable run identity are retained.</p><ul><li>No probability is assigned to a scenario.</li><li>No scenario is a forecast or recommendation.</li><li>Unsupported currencies and percentages outside −100% to +100% are rejected.</li></ul></div>
          </section>

          <section className="limitations" id="limitations" aria-labelledby="limitations-title">
            <p className="panel-kicker">Read before interpretation</p>
            <h2 id="limitations-title">Material limitations</h2>
            <div className="limitation-grid">
              <article><span>01</span><h3>History is finite</h3><p>Observed returns do not contain every possible loss or dependency structure.</p></article>
              <article><span>02</span><h3>Normality is approximate</h3><p>Parametric VaR may understate skew, fat tails, and nonlinear exposure.</p></article>
              <article><span>03</span><h3>Liquidity is absent</h3><p>The demo does not estimate market impact, execution cost, or forced-sale dynamics.</p></article>
              <article><span>04</span><h3>Fixtures are fictional</h3><p>Symbols, prices, portfolio quantities, and outcomes are synthetic and not investable.</p></article>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
