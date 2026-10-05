import { useEffect, useRef, useState } from "react";

import { retailRequest, type Analysis } from "../data/retailApi";

export interface PreferenceReview { willingness_amount_from_fraction: string; capacity_fraction: string | null; flags: string[]; model_version: string }
const flags: Record<string, string> = {
  inconsistent_loss_answers: "Odpowiedzi o stracie w procentach i pieniądzu są niespójne. Sprawdź obie wartości.",
  willingness_exceeds_capacity: "Deklarowana tolerancja przekracza finansową zdolność do poniesienia straty. To dwa różne ograniczenia.",
  cash_below_liquidity_reserve: "Gotówka portfela jest niższa niż wpisana rezerwa płynności.",
  near_term_net_withdrawals: "Planowane wypłaty przewyższają wpłaty przy horyzoncie do roku. Uwzględnij terminy zapotrzebowania na gotówkę.",
  explain_leverage_and_margin: "Dźwignia zwiększa ekspozycję względem kapitału. Depozyt może wymagać dopłat, także podczas strat.",
};

export function PreferencesPanel({ analysis, onLimit, onResult }: { analysis: Analysis | null; onLimit: (value: number) => void; onResult: (value: PreferenceReview | null) => void }) {
  const [goal, setGoal] = useState("");
  const [months, setMonths] = useState("60");
  const [inflow, setInflow] = useState("0");
  const [outflow, setOutflow] = useState("0");
  const [reserve, setReserve] = useState("0");
  const [lossPercent, setLossPercent] = useState("10");
  const [lossAmount, setLossAmount] = useState("0");
  const [capacity, setCapacity] = useState("0");
  const [limit, setLimit] = useState("40");
  const [experience, setExperience] = useState<Record<string, string>>({ equity: "none", etf: "none", bonds: "none", forex: "none", options: "none" });
  const [leverage, setLeverage] = useState(false);
  const [margin, setMargin] = useState(false);
  const [constraints, setConstraints] = useState("");
  const [review, setReview] = useState<PreferenceReview | null>(null);
  const [error, setError] = useState("");
  const latest = useRef(0);
  const callback = useRef(onResult); callback.current = onResult;
  useEffect(() => { latest.current++; setReview(null); callback.current(null); }, [analysis]);
  function invalidate() { latest.current++; setReview(null); callback.current(null); }
  async function save() {
    if (!analysis) return;
    const token = ++latest.current; setError("");
    try {
      const next = await retailRequest<PreferenceReview>("preferences", {
        equity: analysis.net_value, cash: analysis.cash_value, horizon_months: Number(months), goal,
        monthly_inflow: inflow, monthly_outflow: outflow, liquidity_reserve: reserve,
        willingness_fraction: String(Number(lossPercent) / 100), willingness_amount: lossAmount,
        loss_capacity: capacity, concentration_limit: String(Number(limit) / 100),
        asset_experience: experience, understands_leverage: leverage, understands_margin: margin, constraints,
      });
      if (token === latest.current) { setReview(next); callback.current(next); onLimit(Number(limit) / 100); }
    } catch (err: unknown) { if (token === latest.current) setError(err instanceof Error ? err.message : "Błąd odpowiedzi."); }
  }
  const fields = [
    { label: "Horyzont (miesiące)", value: months, set: setMonths, max: 1200, min: 1 },
    { label: "Planowane wpłaty / miesiąc", value: inflow, set: setInflow, min: 0 },
    { label: "Planowane wypłaty / miesiąc", value: outflow, set: setOutflow, min: 0 },
    { label: "Potrzebna rezerwa płynności", value: reserve, set: setReserve, min: 0 },
    { label: "Tolerowana strata (%)", value: lossPercent, set: setLossPercent, min: 0, max: 100 },
    { label: "Tolerowana strata w pieniądzu", value: lossAmount, set: setLossAmount, min: 0 },
    { label: "Finansowa zdolność do poniesienia straty", value: capacity, set: setCapacity, min: 0 },
    { label: "Mój limit koncentracji (%)", value: limit, set: setLimit, min: 0, max: 100 },
  ];
  return <section className="qo-panel" id="profile"><div className="qo-panel-heading"><div><p className="qo-eyebrow">TWOJE CELE, TWOJE GRANICE</p><h2>Krótka ankieta · opcjonalna</h2></div><span className="qo-tag">Możesz uzupełnić później</span></div><p className="qo-muted">Waluta bazowa: {analysis?.base_currency ?? "według portfela"}. Kwoty podaj w tej walucie. Chęć ryzyka i możliwość poniesienia straty są osobnymi odpowiedziami. Ankieta personalizuje wyjaśnienia i Twój limit; nie stanowi formalnego badania MiFID ani rekomendacji instrumentów.</p>
    {error ? <p role="alert" className="qo-alert qo-error">{error}</p> : null}
    <form onSubmit={(e) => { e.preventDefault(); void save(); }} onChange={invalidate}>
      <label className="qo-field">Cel inwestowania<input maxLength={300} value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="np. rezerwa na przyszłe wydatki" /></label>
      <div className="qo-form-grid qo-profile-fields">{fields.map((field) => <label key={field.label} className="qo-field">{field.label}<input type="number" required step={field.label.includes("miesiące") ? "1" : "any"} min={field.min} max={field.max} value={field.value} onChange={(e) => field.set(e.target.value)} /></label>)}</div>
      <fieldset className="qo-experience"><legend>Doświadczenie z klasami instrumentów</legend>{Object.entries({ equity: "Akcje", etf: "ETF", bonds: "Obligacje", forex: "Forex", options: "Opcje" }).map(([key, label]) => <label key={key} className="qo-field">{label}<select value={experience[key]} onChange={(e) => setExperience({ ...experience, [key]: e.target.value })}><option value="none">Brak</option><option value="basic">Podstawowe</option><option value="experienced">Praktyczne</option></select></label>)}</fieldset>
      <div className="qo-profile-checks"><label className="qo-checkbox"><input type="checkbox" checked={leverage} onChange={(e) => setLeverage(e.target.checked)} /> Rozumiem wpływ dźwigni</label><label className="qo-checkbox"><input type="checkbox" checked={margin} onChange={(e) => setMargin(e.target.checked)} /> Rozumiem depozyt i możliwe dopłaty</label></div>
      <label className="qo-field">Preferencje i ograniczenia<textarea maxLength={2000} rows={2} value={constraints} onChange={(e) => setConstraints(e.target.value)} /></label>
      <button className="qo-button qo-primary" disabled={!analysis || Number(analysis.net_value) < 0} type="submit">Sprawdź odpowiedzi i zastosuj limit</button>
    </form>
    {review ? <div className="qo-preference-review" role="status"><strong>Sprawdzono odpowiedzi</strong><p>Strata wynikająca z procentów: {new Intl.NumberFormat("pl-PL", { style: "currency", currency: analysis?.base_currency ?? "PLN" }).format(Number(review.willingness_amount_from_fraction))}.</p><ul>{review.flags.map((flag) => <li key={flag}>{flags[flag]}</li>)}</ul><p>Limit koncentracji zastosowano w panelu obserwacji. Doświadczenie lub zainteresowanie opcjami nie określa zdolności do bezpiecznego używania opcji.</p></div> : null}
    <p className="qo-note">Odpowiedzi pozostają w bieżącej sesji. Pominięcie ankiety nie blokuje analizy. Po zmianie waluty lub wyceny sprawdź ponownie kwoty i spójność odpowiedzi.</p>
  </section>;
}
