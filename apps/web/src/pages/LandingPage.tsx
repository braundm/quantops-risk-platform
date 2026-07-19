import { DEMO_PORTFOLIO_ID } from "../data/demoAdapter";

const capabilities = [
  {
    index: "01",
    title: "Risk, with a receipt",
    body: "Versioned calculations, immutable snapshot IDs, and evidence links keep every displayed number open to verification.",
  },
  {
    index: "02",
    title: "Data quality in context",
    body: "Watermarks, quarantine decisions, and downstream impact appear beside risk—not in a separate operational blind spot.",
  },
  {
    index: "03",
    title: "Bounded explanations",
    body: "Deterministic briefs may summarize approved evidence. They never calculate authoritative metrics or recommend trades.",
  },
] as const;

function Logo() {
  return (
    <svg aria-hidden="true" className="landing-mark" viewBox="0 0 40 40">
      <path d="M9 9h15a7 7 0 0 1 7 7v15H16a7 7 0 0 1-7-7V9Z" />
      <path d="m20 15 8 13m-12-2 11-7" />
    </svg>
  );
}

export function LandingPage() {
  return (
    <div className="landing">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="landing-nav">
        <a className="landing-brand" href="/" aria-label="QuantOps home">
          <Logo />
          Quant<span>Ops</span>
        </a>
        <nav aria-label="Landing navigation">
          <a href="/methodology">Methodology</a>
          <a href="/architecture">Architecture</a>
          <a className="button button-secondary" href="/dashboard">
            Open demo
          </a>
        </nav>
      </header>

      <main id="main-content" tabIndex={-1}>
        <section className="landing-hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow"><span aria-hidden="true" /> Market risk · data lineage · evidence</p>
            <h1 id="hero-title">See the risk.<br />Trace the reason.</h1>
            <p className="hero-lede">
              QuantOps is a reproducible market-risk research platform for inspecting portfolio
              exposure, deterministic stress scenarios, and the data behind every result.
            </p>
            <div className="hero-actions">
              <a className="button button-primary" href="/dashboard">
                Explore synthetic demo <span aria-hidden="true">→</span>
              </a>
              <a className="text-link" href={`/portfolios/${DEMO_PORTFOLIO_ID}`}>
                Inspect the portfolio
              </a>
            </div>
            <p className="hero-boundary">
              <span aria-hidden="true">i</span>
              Historical synthetic data. Research and engineering use only—not investment advice.
            </p>
          </div>

          <div className="hero-visual" aria-label="Example trace from price data to evidence">
            <div className="visual-orbit" aria-hidden="true" />
            <article className="visual-card visual-card-main">
              <div className="visual-card-header">
                <span>Risk snapshot</span>
                <span className="historical-label">Synthetic</span>
              </div>
              <p>Portfolio value</p>
              <strong>$1,503,208</strong>
              <div className="visual-metrics">
                <span><small>Hist. VaR 95%</small><b>$7,964</b></span>
                <span><small>Expected shortfall</small><b>$27,263</b></span>
              </div>
              <svg aria-label="Example historical risk trend rising towards the latest point" role="img" viewBox="0 0 340 90">
                <defs>
                  <linearGradient id="landing-fill" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#4fd1c5" stopOpacity=".3" />
                    <stop offset="100%" stopColor="#4fd1c5" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <path d="M0 76 44 65 84 70 128 42 170 48 214 31 256 38 300 13 340 21V90H0Z" fill="url(#landing-fill)" />
                <path d="M0 76 44 65 84 70 128 42 170 48 214 31 256 38 300 13 340 21" fill="none" stroke="#4fd1c5" strokeWidth="2" />
              </svg>
            </article>
            <article className="visual-card visual-card-source">
              <span className="mini-icon" aria-hidden="true">✓</span>
              <div><small>Source verified</small><strong>2,088 canonical bars</strong></div>
            </article>
            <article className="visual-card visual-card-method">
              <span className="mini-icon" aria-hidden="true">§</span>
              <div><small>Methodology</small><strong>Version 1.0.0</strong></div>
            </article>
          </div>
        </section>

        <section className="trust-strip" aria-label="Demo properties">
          <span>Fixed seed <strong>20250317</strong></span>
          <span>Versioned methods <strong>1.0.0</strong></span>
          <span>Canonical bars <strong>2,088</strong></span>
          <span>Trade execution <strong>None</strong></span>
        </section>

        <section className="landing-section" aria-labelledby="capability-title">
          <div className="section-intro">
            <p className="eyebrow">Built for scrutiny</p>
            <h2 id="capability-title">A clear line from input to decision support.</h2>
            <p>Designed for independent verification, explicit limits, and calm investigation under pressure.</p>
          </div>
          <div className="capability-grid">
            {capabilities.map((capability) => (
              <article className="capability" key={capability.index}>
                <span>{capability.index}</span>
                <h3>{capability.title}</h3>
                <p>{capability.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-architecture" aria-labelledby="landing-flow-title">
          <div>
            <p className="eyebrow">Transparent by design</p>
            <h2 id="landing-flow-title">Follow one result all the way back.</h2>
            <p>
              The demo keeps simulated market time, ingestion lineage, calculation version, and
              evidence identity separate—so “where did this come from?” has a concrete answer.
            </p>
            <a className="text-link" href="/architecture">Explore the system flow →</a>
          </div>
          <ol className="flow-preview">
            <li><span>01</span><strong>Synthetic prices</strong><small>Deterministic source events</small></li>
            <li><span>02</span><strong>Quality gate</strong><small>Validate and quarantine</small></li>
            <li><span>03</span><strong>Risk engine</strong><small>Pure versioned methods</small></li>
            <li><span>04</span><strong>Evidence</strong><small>Traceable presentation</small></li>
          </ol>
        </section>
      </main>

      <footer className="landing-footer">
        <a className="landing-brand" href="/" aria-label="QuantOps home"><Logo />Quant<span>Ops</span></a>
        <p>Market-risk research and observability. No brokerage connectivity, trading, or recommendations.</p>
        <span>Deterministic synthetic demo</span>
      </footer>
    </div>
  );
}
