import { useEffect, useRef, useState, type FormEvent } from "react";
import { treasuryExample, treasuryRequest, type TreasuryBond, type TreasuryRequest, type TreasuryResult } from "../data/treasuryApi";
import "../styles/treasury.css";

const number = (value: string | null | undefined, digits = 2) => value == null ? "Unavailable" : Number(value).toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits });

export function TreasuryPage() {
  const [input, setInput] = useState<TreasuryRequest>(() => treasuryExample("ladder"));
  const [volumeText, setVolumeText] = useState(() => input.liquidity_positions[0]?.sessions.map(s => `${s.date},${s.volume}`).join("\n") ?? "");
  const [output, setOutput] = useState<TreasuryResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const revision = useRef(0);
  useEffect(() => { document.title = "QuantOps — Treasury and liquidity lab"; document.documentElement.lang = "en"; }, []);

  function change(next: TreasuryRequest) {
    revision.current += 1;
    setInput(next); setOutput(null); setError("");
  }
  function changeBond(index: number, patch: Partial<TreasuryBond>) {
    change({ ...input, bonds: input.bonds.map((bond, i) => i === index ? { ...bond, ...patch } : bond) });
  }
  function loadExample(kind: "ladder" | "long" | "offset") {
    const next = treasuryExample(kind);
    setVolumeText(next.liquidity_positions[0]?.sessions.map(s => `${s.date},${s.volume}`).join("\n") ?? "");
    change(next);
  }
  function requestInput(): TreasuryRequest {
    const sessions = volumeText.split("\n").filter(line => line.trim()).map(line => {
      const fields = line.split(",");
      if (fields.length !== 2) throw new Error("Each volume row must contain exactly a date and volume separated by one comma.");
      return { date: (fields[0] ?? "").trim(), volume: (fields[1] ?? "").trim() };
    });
    return { ...input, liquidity_positions: input.liquidity_positions.map((p, i) => i === 0 ? { ...p, sessions } : p) };
  }
  async function analyze(event: FormEvent) {
    event.preventDefault();
    const token = revision.current;
    setBusy(true); setOutput(null); setError("");
    try {
      const response = await treasuryRequest("analyze", requestInput());
      const data = await response.json() as TreasuryResult;
      if (token === revision.current) setOutput(data);
    } catch (e) { if (token === revision.current) setError(e instanceof Error ? e.message : "Analysis unavailable."); }
    finally { setBusy(false); }
  }
  async function report() {
    const token = revision.current;
    setBusy(true); setError("");
    try {
      const response = await treasuryRequest("report", requestInput());
      const blob = await response.blob();
      if (token !== revision.current) return;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = "quantops-treasury-report.html"; anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { if (token === revision.current) setError(e instanceof Error ? e.message : "Report unavailable."); }
    finally { setBusy(false); }
  }
  const liquidity = input.liquidity_positions[0];
  return <div className="treasury-page">
    <header><p className="eyebrow">Market risk research · Treasury</p><h1>Treasury and liquidity lab</h1>
      <p>Inspect fixed-coupon bond sensitivity, parallel yield shocks and a separate equity liquidity book.</p>
      <span className="badge badge-warning">{input.origin === "synthetic" ? "SYNTHETIC EXAMPLE" : "USER SUPPLIED"} · UNVERIFIED INPUTS</span>
      <p>Educational models. No live yields, bank balance sheet or regulatory compliance claim. Inputs stay in this page and are sent to your local API for calculation.</p>
    </header>
    <section className="panel"><h2>Three reproducible cases</h2><div className="treasury-actions">
      <button type="button" className="button button-secondary" onClick={() => loadExample("ladder")}>Maturity ladder</button>
      <button type="button" className="button button-secondary" onClick={() => loadExample("long")}>Long duration</button>
      <button type="button" className="button button-secondary" onClick={() => loadExample("offset")}>Offsetting sensitivities</button>
    </div><p>Compare maturity exposure, long-duration stress losses and net versus gross DV01. The offset case is a sensitivity illustration, with no transaction or financing model.</p></section>
    <form onSubmit={(event) => void analyze(event)}>
      <section className="panel"><h2>1. Define the bond book</h2>
        <div className="treasury-fields">
          <label>Currency<select value={input.currency} onChange={(e) => change({ ...input, currency: e.target.value })}>{["USD", "EUR", "CHF", "PLN", "GBP"].map(c => <option key={c}>{c}</option>)}</select></label>
          <label>Valuation date<input type="date" required value={input.valuation_date} onChange={(e) => change({ ...input, valuation_date: e.target.value })} /></label>
          <label>Input origin<select value={input.origin} onChange={(e) => change({ ...input, origin: e.target.value as TreasuryRequest["origin"] })}><option value="synthetic">Synthetic</option><option value="user_supplied">User supplied, unverified</option></select></label>
          <label>Absolute net DV01 limit<input type="number" min="0" step="any" value={input.max_abs_dv01 ?? ""} onChange={(e) => change({ ...input, max_abs_dv01: e.target.value || null })} /></label>
        </div>
        <label>Source and assumptions<input required maxLength={500} value={input.source_note} onChange={(e) => change({ ...input, source_note: e.target.value })} /></label>
        <p>Rates are decimals: 0.04 = 4%. Prices use the face amount per bond. Settlement is at a coupon boundary, with whole remaining years and no accrued interest.</p>
        {input.bonds.map((bond, index) => <fieldset key={bond.id}><legend>Bond {index + 1}</legend><div className="treasury-fields">
          <label>Name<input required maxLength={80} value={bond.name} onChange={(e) => changeBond(index, { name: e.target.value })} /></label>
          <label>Face amount<input type="number" min="0.01" max="1000000000000" step="any" required value={bond.face} onChange={(e) => changeBond(index, { face: e.target.value })} /></label>
          <label>Signed quantity<input type="number" min="-1000000000" max="1000000000" step="any" required value={bond.quantity} onChange={(e) => changeBond(index, { quantity: e.target.value })} /></label>
          <label>Annual coupon (decimal)<input type="number" min="0" max="0.5" step="any" required value={bond.coupon_rate} onChange={(e) => changeBond(index, { coupon_rate: e.target.value })} /></label>
          <label>Nominal yield (decimal)<input type="number" min="-0.1" max="1" step="any" required value={bond.yield_rate} onChange={(e) => changeBond(index, { yield_rate: e.target.value })} /></label>
          <label>Remaining years<input type="number" min="1" max="50" step="1" required value={bond.years} onChange={(e) => changeBond(index, { years: Number(e.target.value) })} /></label>
          <label>Coupons per year<select value={bond.frequency} onChange={(e) => changeBond(index, { frequency: Number(e.target.value) })}>{[1, 2, 4, 12].map(m => <option key={m}>{m}</option>)}</select></label>
        </div><button type="button" className="button button-secondary" disabled={input.bonds.length === 1} onClick={() => change({ ...input, bonds: input.bonds.filter((_, i) => i !== index) })}>Remove bond {index + 1}</button></fieldset>)}
        <button type="button" className="button button-secondary" disabled={input.bonds.length >= 30} onClick={() => change({ ...input, bonds: [...input.bonds, { id: crypto.randomUUID(), name: "User-defined bond", face: "1000", quantity: "1", coupon_rate: "0.04", yield_rate: "0.04", years: 5, frequency: 2 }] })}>Add bond</button>
      </section>
      <section className="panel"><h2>2. Inspect liquidity separately</h2><p>Paste dated volume sessions from your source. At least 20 sessions are required; blank history means insufficient data. This equity position is excluded from bond totals.</p>
        {liquidity && <><div className="treasury-fields">
          <label>Equity name<input required maxLength={80} value={liquidity.name} onChange={(e) => change({ ...input, liquidity_positions: [{ ...liquidity, name: e.target.value }] })} /></label>
          <label>Equity quantity<input type="number" min="0.0001" step="any" required value={liquidity.quantity} onChange={(e) => change({ ...input, liquidity_positions: [{ ...liquidity, quantity: e.target.value }] })} /></label>
          <label>Reference price<input type="number" min="0.0001" step="any" required value={liquidity.reference_price} onChange={(e) => change({ ...input, liquidity_positions: [{ ...liquidity, reference_price: e.target.value }] })} /></label>
          <label>Reference price date<input type="date" required value={liquidity.price_date} onChange={(e) => change({ ...input, liquidity_positions: [{ ...liquidity, price_date: e.target.value }] })} /></label>
          <label>ADV participation<select value={input.participation} onChange={(e) => change({ ...input, participation: e.target.value })}><option value="0.05">5%</option><option value="0.1">10%</option><option value="0.2">20%</option></select></label>
          <label>Liquidation limit (days)<input type="number" min="1" max="252" step="1" required value={input.max_liquidation_days} onChange={(e) => change({ ...input, max_liquidation_days: Number(e.target.value) })} /></label>
        </div><label>Volume sessions (YYYY-MM-DD,volume; one per line)<textarea rows={6} value={volumeText} onChange={(e) => { setVolumeText(e.target.value); change(input); }} /></label></>}
      </section>
      <div className="treasury-actions"><button className="button button-primary" disabled={busy}>{busy ? "Calculating…" : "Calculate risk"}</button>
        <button type="button" className="button button-secondary" disabled={busy || !output} onClick={() => void report()}>Export HTML report</button></div>
    </form>
    {error && <p role="alert" className="treasury-error">{error}</p>}
    {!output && <p role="status">Calculate after editing to see results. Previous results are cleared when inputs change.</p>}
    {output && <section aria-label="Treasury results" aria-live="polite">
      <div className="treasury-summary">{[["Net bond value", number(output.net_value)], ["Gross bond value", number(output.gross_value)], ["Signed DV01 / bp", number(output.signed_dv01, 4)], ["Gross DV01 / bp", number(output.gross_dv01, 4)]].map(([label, value]) => <article className="panel" key={label}><p>{label}</p><strong>{value} {output.currency}</strong></article>)}</div>
      <p>Absolute net DV01 limit: <strong>{output.dv01_limit_status}</strong> · {output.methodology_version} · {output.generated_at}</p>
      <section className="panel"><h2>Bond sensitivity</h2><div className="treasury-table" role="region" aria-label="Bond sensitivity table" tabIndex={0}><table><thead><tr><th>Bond</th><th>Price</th><th>Macaulay years</th><th>Modified duration</th><th>Convexity</th><th>Signed DV01</th></tr></thead><tbody>{output.bonds.map(b => <tr key={b.id}><th scope="row">{b.name}</th><td>{number(b.metrics.price)}</td><td>{number(b.metrics.macaulay_duration, 4)}</td><td>{number(b.metrics.modified_duration, 4)}</td><td>{number(b.metrics.convexity, 4)}</td><td>{number(b.signed_dv01, 4)}</td></tr>)}</tbody></table></div></section>
      <section className="panel"><h2>Parallel yield shocks</h2><p>Full repricing of current fixed cash flows. Positive bp means higher yields. P&amp;L is in {output.currency}; no net-value percentage is shown for offsetting books.</p><div className="treasury-table" role="region" aria-label="Rate shock table" tabIndex={0}><table><thead><tr><th>Yield shock</th><th>Before</th><th>After</th><th>P&amp;L</th>{output.bonds.map(b => <th key={b.id}>{b.name} P&amp;L</th>)}</tr></thead><tbody>{output.scenarios.map(s => <tr key={s.shock_bp}><th scope="row">{s.shock_bp > 0 ? "+" : ""}{s.shock_bp} bp</th><td>{number(s.before)}</td><td>{number(s.after)}</td><td>{number(s.pnl)}</td>{output.bonds.map(b => <td key={b.id}>{number(s.pnl_by_position[b.id])}</td>)}</tr>)}</tbody></table></div></section>
      <section className="panel"><h2>Liquidity observations</h2><p>Usable value coverage: {number(output.liquidity_coverage_pct)}% · Liquidatable in 1 day: {number(output.liquidatable_one_day_pct)} · 5 days: {number(output.liquidatable_five_days_pct)} (percent of separate equity book).</p>
        {output.liquidity.map(p => <article key={p.id}><h3>{p.name}</h3><p>Quality: <strong>{p.status.toUpperCase()}</strong> · Limit: <strong>{p.limit_status}</strong></p><p>{p.estimate.observations} supplied sessions · {p.first_date ?? "No start"} to {p.last_date ?? "no end"}</p><p>ADV: {number(p.estimate.adv)} · Position / ADV: {number(p.estimate.position_to_adv, 4)} · Estimated days: {p.status === "valid" ? p.estimate.days : "Unavailable"}</p></article>)}
      </section>
      <section className="panel"><h2>Methodology and limitations</h2><ul>{output.assumptions.map(a => <li key={a}>{a}</li>)}</ul></section>
    </section>}
    <section className="panel"><h2>Reading Treasury risk</h2><p>Repricing risk arises when assets and funding reset at different times. Yield-curve risk includes changes in slope and shape, which these parallel shocks do not model. Basis risk arises from different reference rates; optionality changes the timing or amount of cash flows.</p><p>NII measures an earnings perspective over a defined horizon. EVE measures the economic-value perspective of the banking book. These bond sensitivities illustrate valuation effects; they do not calculate either bank-wide measure.</p><a className="text-link" href="https://www.bis.org/basel_framework/chapter/SRP/98.htm">Basel Committee: IRRBB application guidance →</a></section>
  </div>;
}
