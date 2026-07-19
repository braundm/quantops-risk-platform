import { Badge, PageHeading } from "../components/Primitives";

const layers = [
  { index: "01", name: "Deterministic sources", detail: "Versioned synthetic OHLCV, fictional documents, and isolated quality cases", tags: ["fixed seed", "stable IDs"] },
  { index: "02", name: "Ingestion & quality", detail: "Schema validation, data rules, watermarks, deduplication, and quarantine", tags: ["idempotent", "observable"] },
  { index: "03", name: "Domain & persistence", detail: "Typed entities, application boundaries, PostgreSQL mappings, audit, and outbox", tags: ["UTC", "Decimal"] },
  { index: "04", name: "Pure risk engine", detail: "Returns, valuation, VaR, ES, drawdown, concentration, and deterministic scenarios", tags: ["versioned", "no network"] },
  { index: "05", name: "API & presentation", detail: "Safe read models, explicit calculation states, evidence links, and this dashboard", tags: ["typed", "accessible"] },
] as const;

export function ArchitecturePage() {
  return (
    <div className="page architecture-page">
      <PageHeading
        eyebrow="System architecture"
        title="Inward dependencies. Outward evidence."
        description="A concise view of how simulated inputs become traceable risk results without giving infrastructure authority over financial calculations."
      />

      <section className="architecture-principles" aria-label="Architecture principles">
        <article><span aria-hidden="true">↓</span><div><strong>Dependencies point inward</strong><p>Infrastructure adapts domain and application ports; the pure core knows no database, web, broker, or provider SDK.</p></div></article>
        <article><span aria-hidden="true">◇</span><div><strong>Evidence travels outward</strong><p>Every presentation layer result retains source, version, simulated market time, and calculation identity.</p></div></article>
        <article><span aria-hidden="true">⊘</span><div><strong>Trading is out of scope</strong><p>No brokerage connection, order route, buy/sell recommendation, or return guarantee exists.</p></div></article>
      </section>

      <section className="architecture-map" aria-labelledby="map-title">
        <div className="section-heading"><div><p className="panel-kicker">Primary data path</p><h2 id="map-title">From event to visible snapshot</h2></div><Badge>Conceptual · current foundation</Badge></div>
        <ol className="layer-list">
          {layers.map((layer, index) => (
            <li key={layer.index}>
              <span className="layer-index">{layer.index}</span>
              <div className="layer-node"><div><h3>{layer.name}</h3><p>{layer.detail}</p></div><div>{layer.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}</div></div>
              {index < layers.length - 1 ? <span className="layer-arrow" aria-hidden="true">↓</span> : null}
            </li>
          ))}
        </ol>
      </section>

      <div className="content-grid content-grid-equal">
        <section className="panel" aria-labelledby="event-flow-title">
          <header className="panel-header"><div><p className="panel-kicker">One synthetic price event</p><h2 id="event-flow-title">Trace sequence</h2></div><Badge>At-least-once ready</Badge></header>
          <ol className="sequence-list">
            <li><span>1</span><p><strong>Generate</strong><small>Stable source event ID and simulated timestamp</small></p></li>
            <li><span>2</span><p><strong>Validate</strong><small>Contract plus OHLC and currency rules</small></p></li>
            <li><span>3</span><p><strong>Persist</strong><small>Unique constraints protect idempotency</small></p></li>
            <li><span>4</span><p><strong>Calculate</strong><small>Pure versioned risk engine</small></p></li>
            <li><span>5</span><p><strong>Present</strong><small>Typed state and exact evidence link</small></p></li>
          </ol>
        </section>
        <section className="panel" aria-labelledby="boundaries-title">
          <header className="panel-header"><div><p className="panel-kicker">Authority boundaries</p><h2 id="boundaries-title">What may calculate what</h2></div></header>
          <div className="boundary-list">
            <div><Badge tone="good">Authoritative</Badge><h3>Risk engine</h3><p>Calculates financial metrics from validated typed inputs.</p></div>
            <div><Badge tone="accent">Orchestrates</Badge><h3>Application layer</h3><p>Coordinates use cases, authorization, audit, and ports.</p></div>
            <div><Badge>Explains only</Badge><h3>AI boundary</h3><p>May summarize approved evidence; never originates an authoritative metric.</p></div>
            <div><Badge tone="warning">Quarantines</Badge><h3>Quality layer</h3><p>Prevents invalid or duplicate inputs from gaining trust.</p></div>
          </div>
        </section>
      </div>

      <section className="deployment-note" aria-labelledby="deployment-title">
        <div><p className="panel-kicker">Operational honesty</p><h2 id="deployment-title">Core demo first, optional infrastructure second</h2><p>The local interface can explain a deterministic batch fixture without Docker, a broker, an external model, or a cloud account. PostgreSQL, Redpanda, observability, and external AI remain adapters—not unit-test prerequisites.</p></div>
        <a className="button button-primary" href="/dashboard">Return to dashboard</a>
      </section>
    </div>
  );
}
