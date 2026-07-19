const capabilities = [
  "Deterministic synthetic market data",
  "Versioned and reproducible risk methods",
  "Traceable data quality and evidence",
] as const;

export function App() {
  return (
    <main>
      <nav className="nav" aria-label="Primary navigation">
        <a className="wordmark" href="/" aria-label="QuantOps home">
          <span aria-hidden="true">Q</span>
          QuantOps
        </a>
        <span className="environment">Synthetic demo</span>
      </nav>

      <section className="hero" aria-labelledby="hero-title">
        <p className="eyebrow">Market risk · data lineage · grounded AI</p>
        <h1 id="hero-title">Risk engineering you can trace.</h1>
        <p className="lede">
          QuantOps turns deterministic multi-asset market fixtures into auditable portfolio risk,
          stress scenarios, and evidence-backed explanations.
        </p>
        <a className="primary-action" href="/dashboard">
          Open demo dashboard
        </a>
      </section>

      <section className="capability-grid" aria-label="Platform capabilities">
        {capabilities.map((capability, index) => (
          <article className="capability" key={capability}>
            <span className="capability-index">0{index + 1}</span>
            <h2>{capability}</h2>
            <p>Designed for independent verification, bounded operation, and explicit limits.</p>
          </article>
        ))}
      </section>

      <footer>
        Research and engineering use only. QuantOps does not execute trades or provide investment
        recommendations.
      </footer>
    </main>
  );
}
