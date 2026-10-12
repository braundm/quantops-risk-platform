import { useState, type FormEvent } from "react";
import type { Knowledge, ProfileAnswers } from "../data/stocksApi";

const initial: ProfileAnswers = {
  goal: "Zrozumieć ryzyko posiadanych akcji", horizon_months: 36,
  willingness_pct: 10, capacity_pct: 10, needs_cash_soon: false,
  stocks: "none", bonds: "none", etfs: "none", options: "none", futures: "none",
  knows_loss: false, knows_diversification: false, knows_leverage: false,
};

export function StockProfileSurvey({ name, saved, busy, onSubmit }: {
  name: string; saved: ProfileAnswers | null; busy: boolean;
  onSubmit: (answers: ProfileAnswers) => Promise<void>;
}) {
  const [answers, setAnswers] = useState(saved ?? initial);
  function submit(event: FormEvent) { event.preventDefault(); void onSubmit(answers); }
  return <section className="iv-panel sq-survey">
    <p className="iv-eyebrow">TWÓJ PROFIL · ANKIETA OPCJONALNA</p>
    <h2>{name}, poznajmy Twój punkt startu.</h2>
    <p>Odpowiedzi służą do objaśnień i zapisania Twojego punktu startu. Nie wpływają na wycenę, obliczenia ani dostęp do importu.</p>
    <form onSubmit={submit}>
      <fieldset><legend>Cel i możliwość poniesienia straty</legend><div className="iv-form-grid">
        <label>Cel korzystania<input required maxLength={200} value={answers.goal} onChange={(e) => setAnswers({ ...answers, goal: e.target.value })} /></label>
        <label>Horyzont (miesiące)<input required type="number" min={1} max={1200} step={1} value={answers.horizon_months} onChange={(e) => setAnswers({ ...answers, horizon_months: Number(e.target.value) })} /></label>
        <label>Akceptowana strata (%)<input required type="number" min={0} max={100} step={1} value={answers.willingness_pct} onChange={(e) => setAnswers({ ...answers, willingness_pct: Number(e.target.value) })} /></label>
        <label>Strata bez naruszenia ważnych wydatków (%)<input required type="number" min={0} max={100} step={1} value={answers.capacity_pct} onChange={(e) => setAnswers({ ...answers, capacity_pct: Number(e.target.value) })} /></label>
      </div><label className="sq-check"><input type="checkbox" checked={answers.needs_cash_soon} onChange={(e) => setAnswers({ ...answers, needs_cash_soon: e.target.checked })} /> Potrzebuję tych środków w ciągu najbliższych 12 miesięcy</label></fieldset>
      <fieldset><legend>Znajomość rynku i instrumentów</legend><div className="iv-form-grid">
        {([['stocks','Akcje'],['bonds','Obligacje'],['etfs','ETF-y'],['options','Opcje'],['futures','Kontrakty terminowe']] as const).map(([key, label]) => <label key={key}>{label}<select value={answers[key]} onChange={(e) => setAnswers({ ...answers, [key]: e.target.value as Knowledge })}><option value="none">Nie znam / zaczynam</option><option value="basic">Znam podstawy</option><option value="experienced">Mam praktyczne doświadczenie</option></select></label>)}
      </div></fieldset>
      <fieldset><legend>Co już rozumiesz?</legend>
        {([['knows_loss','Rozumiem, że akcje mogą stracić całą wartość'],['knows_diversification','Rozumiem koncentrację i dywersyfikację'],['knows_leverage','Rozumiem dźwignię i depozyt zabezpieczający']] as const).map(([key, label]) => <label className="sq-check" key={key}><input type="checkbox" checked={answers[key]} onChange={(e) => setAnswers({ ...answers, [key]: e.target.checked })} />{label}</label>)}
      </fieldset>
      <button className="iv-button iv-primary" disabled={busy}>{busy ? "Zapisuję…" : "Zapisz ankietę"}</button>
    </form>
  </section>;
}
