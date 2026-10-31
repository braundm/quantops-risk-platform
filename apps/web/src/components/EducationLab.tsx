import { useState } from "react";

import { retailRequest } from "../data/retailApi";
import { RetailChart } from "./RetailChart";

interface LabRound {
  token: string; exercise: number; step: number; max_steps: number; visible_prices: number[];
  cumulative_gross: string; cumulative_net: string; cumulative_benchmark: string; cumulative_cost: string;
  correct_count: number; traded_count: number; mean_confidence: string | null; mean_brier: string | null;
  outcome: { correct: boolean | null; gross_return: string; net_return: string; cost: string; direction: string } | null;
}
const percent = (value: string | number) => new Intl.NumberFormat("pl-PL", { style: "percent", maximumFractionDigits: 2 }).format(Number(value));

export function EducationLab() {
  const [round, setRound] = useState<LabRound | null>(null);
  const [confidence, setConfidence] = useState("70");
  const [cost, setCost] = useState("10");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function start() {
    setBusy(true); setError("");
    try { setRound(await retailRequest<LabRound>("lab/start", {})); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : "Błąd ćwiczenia."); }
    finally { setBusy(false); }
  }
  async function decide(direction: "up" | "down" | "skip") {
    if (!round || busy) return;
    setBusy(true); setError("");
    try {
      if (confidence.trim() === "" || cost.trim() === "" || !Number.isFinite(Number(confidence)) || !Number.isFinite(Number(cost))) throw new Error("Uzupełnij pewność i koszt.");
      const next = await retailRequest<LabRound>("lab/decision", { token: round.token, direction, confidence: String(Number(confidence) / 100), cost_bps: cost });
      setRound(next);
    } catch (err: unknown) { setError(err instanceof Error ? err.message : "Błąd decyzji."); }
    finally { setBusy(false); }
  }
  return <section className="qo-panel qo-lab-panel" id="lab">
    <div className="qo-panel-heading"><div><p className="qo-eyebrow">SPRAWDŹ SWOJĄ PEWNOŚĆ</p><h2>Laboratorium decyzji</h2></div><span className="qo-tag">Anonimowy wykres · dane syntetyczne</span></div>
    <p className="qo-muted">Bez nazwy instrumentu i bez podglądu przyszłości. Zapisz kierunek oraz pewność, a potem odsłoń pięć kolejnych obserwacji.</p>
    {error ? <p className="qo-alert qo-error" role="alert">{error}</p> : null}
    {!round ? <div className="qo-lab-intro"><div className="qo-lab-mark" aria-hidden="true">?</div><h3>Ile mówi Ci sam wykres?</h3><p>10 prób. Jawne reguły. Wynik przed i po kosztach.</p><button className="qo-button qo-primary" disabled={busy} onClick={() => void start()}>Rozpocznij ćwiczenie</button></div> : <>
      <div className="qo-lab-progress"><strong>Próby: {round.step} / {round.max_steps}</strong><div aria-hidden="true">{Array.from({ length: round.max_steps }, (_, index) => <i key={index} className={index < round.step ? "completed" : ""} />)}</div></div>
      <RetailChart values={round.visible_prices} title="Anonimowa seria: wyłącznie odsłonięte obserwacje" />
      {round.outcome ? <div className="qo-lab-outcome" role="status"><strong>{round.outcome.correct === null ? "Brak transakcji" : round.outcome.correct ? "Kierunek trafny" : "Kierunek nietrafny"}</strong><span>Przed kosztami: {percent(round.outcome.gross_return)} · po kosztach: {percent(round.outcome.net_return)}</span></div> : null}
      {round.step < round.max_steps ? <div className="qo-lab-decision">
        <label className="qo-field">Deklarowana pewność (%)<input type="number" min="50" max="100" value={confidence} onChange={(e) => setConfidence(e.target.value)} /></label>
        <label className="qo-field">Koszt próby (pb)<input type="number" min="0" max="1000" value={cost} onChange={(e) => setCost(e.target.value)} /></label>
        <div className="qo-decision-buttons"><button className="qo-button qo-primary" disabled={busy} onClick={() => void decide("up")}>Wzrost · odsłoń</button><button className="qo-button" disabled={busy} onClick={() => void decide("down")}>Spadek · odsłoń</button><button className="qo-button" disabled={busy} onClick={() => void decide("skip")}>Brak transakcji · odsłoń</button></div>
      </div> : <div className="qo-lab-finished"><h3>Ćwiczenie zakończone</h3><p>Dziesięć prób nie wystarcza, aby wykazać przewagę. Porównaj trafność, koszty i kalibrację pewności — każdy z tych wyników odpowiada na inne pytanie.</p><button className="qo-button" disabled={busy} onClick={() => void start()}>Rozpocznij nową serię</button></div>}
      <div className="qo-risk-strip qo-lab-stats"><article><p>Trafność kierunku</p><strong>{round.traded_count ? percent(round.correct_count / round.traded_count) : "—"}</strong><small>{round.correct_count} trafnych / {round.traded_count} kierunkowych</small></article><article><p>Suma wyników po kosztach</p><strong>{percent(round.cumulative_net)}</strong><small>Przed kosztami {percent(round.cumulative_gross)}</small></article><article><p>Benchmark po kosztach</p><strong>{percent(round.cumulative_benchmark)}</strong><small>Zawsze wzrost · taki sam koszt próby</small></article><article><p>Kalibracja pewności</p><strong>{round.mean_brier === null ? "—" : Number(round.mean_brier).toFixed(3)}</strong><small>Brier: mniej = lepiej · średnia pewność {round.mean_confidence ? percent(round.mean_confidence) : "—"}</small></article></div>
    </>}
    <p className="qo-note">Reguły: wzrost = zwrot ceny; spadek = przeciwny zwrot; brak transakcji = 0 i brak kosztu. Każda próba ma równy, niezależny nominał; sumy nie są kapitalizowanym zwrotem strategii. Benchmark wybiera wzrost w każdej próbie i ponosi wpisany koszt. Pewność dotyczy trafności kierunku, nie zysku. Brier to średni kwadrat różnicy pewności i trafności. Cztery syntetyczne ścieżki, brak rzeczywistej próby rynkowej — bez wniosku o skuteczności strategii. Sesja wygasa po godzinie lub restarcie API.</p>
  </section>;
}
