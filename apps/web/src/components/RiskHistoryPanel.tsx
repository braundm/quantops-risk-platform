import { useEffect, useRef, useState } from "react";

import { retailRequest, type Portfolio } from "../data/retailApi";
import { RetailChart } from "./RetailChart";

export interface HistoryRow { date: string; symbol: string; price: string; fx_to_base: string; source: "user" | "synthetic" }
export interface HistoricalRisk {
  model_version: string; status: "ok" | "insufficient_data" | "invalid_data" | "unstable";
  source: string; base_currency: string; confidence: string; observation_count: number;
  required_observations: number; tail_count: number; var_amount: string | null; es_amount: string | null;
  var_fraction: number | null; es_fraction: number | null; daily_volatility: number | null;
  maximum_drawdown: number | null; period_start: string | null; period_end: string | null;
  points: { date: string; value: string }[]; correlation_symbols: string[];
  correlations: (number | null)[][]; warnings: string[];
}
interface Preview { rows: HistoryRow[]; errors: { row: number; message: string }[]; importable: boolean }
const money = (value: string | null, currency: string) => value === null ? "—" : new Intl.NumberFormat("pl-PL", { style: "currency", currency }).format(Number(value));
const percent = (value: number | null) => value === null ? "—" : new Intl.NumberFormat("pl-PL", { style: "percent", maximumFractionDigits: 2 }).format(value);
const messages: Record<string, string> = {
  incomplete_or_inconsistent_history: "Historia jest niepełna, ma duplikaty, niespójne kursy lub niedodatnią wartość portfela. Każdy instrument wymaga tego samego zestawu dat.",
  too_short_history: "Za mało obserwacji dla wybranego poziomu ufności. Wyniki miar są ukryte.",
  synthetic_history: "Historia zawiera dane syntetyczne — służy do sprawdzenia działania modelu.",
  history_is_not_recent: "Okres historii nie kończy się w ostatnim tygodniu. Dane nie opisują aktualnego rynku.",
  calendar_gaps_one_observation_horizon: "W kalendarzu są luki. Horyzont miar to jedna obserwacja, nie zawsze jeden dzień.",
  nonpositive_current_equity: "Bieżąca wartość netto nie jest dodatnia. Kwotowe miary ryzyka są niedostępne.",
};

export function RiskHistoryPanel({ portfolio, onResult }: { portfolio: Portfolio; onResult: (value: HistoricalRisk | null) => void }) {
  const [rows, setRows] = useState<HistoryRow[]>([]);
  const [risk, setRisk] = useState<HistoricalRisk | null>(null);
  const [confidence, setConfidence] = useState("0.95");
  const [csv, setCsv] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const latest = useRef(0);
  const upload = useRef(0);
  const callback = useRef(onResult);
  callback.current = onResult;
  useEffect(() => { latest.current++; setRisk(null); setBusy(false); callback.current(null); }, [portfolio, confidence]);

  async function calculate(inputRows = rows) {
    const token = ++latest.current;
    setBusy(true); setError(""); setRisk(null); callback.current(null);
    try {
      const next = await retailRequest<HistoricalRisk>("history-risk", { portfolio, rows: inputRows, confidence });
      if (latest.current === token) { setRisk(next); callback.current(next); }
    } catch (err: unknown) { if (latest.current === token) setError(err instanceof Error ? err.message : "Błąd analizy historii."); }
    finally { if (latest.current === token) setBusy(false); }
  }

  async function loadDemo() {
    const token = ++latest.current;
    setBusy(true); setError("");
    try {
      const next = await retailRequest<HistoryRow[]>("history-demo");
      if (token !== latest.current) return;
      setRows(next); await calculate(next);
    } catch (err: unknown) { setError(err instanceof Error ? err.message : "Brak danych demo."); setBusy(false); }
  }

  async function inspectCsv() {
    const token = ++upload.current;
    setPreview(null); setError("");
    try {
      const next = await retailRequest<Preview>("history-preview", { text: csv });
      if (token === upload.current) setPreview(next);
    } catch (err: unknown) { if (token === upload.current) setError(err instanceof Error ? err.message : "Błąd pliku historii."); }
  }

  return <section className="qo-panel qo-history-panel" id="risk">
    <div className="qo-panel-heading"><div><p className="qo-eyebrow">OD LICZB DO ZROZUMIENIA</p><h2>Jak duże byłyby wahania tego portfela?</h2></div><span className="qo-tag">Symulacja historyczna · stałe ilości</span></div>
    <p className="qo-muted">Przeliczamy dzisiejsze ilości na dawnych cenach i kursach. To nie jest historia Twoich inwestycji ani dowód przyszłych wyników.</p>
    <div className="qo-history-controls">
      <label className="qo-field">Poziom ufności<select aria-label="Poziom ufności" value={confidence} onChange={(e) => setConfidence(e.target.value)}><option value="0.90">90%</option><option value="0.95">95%</option><option value="0.99">99%</option></select></label>
      <button className="qo-button" disabled={busy || portfolio.base_currency !== "PLN"} onClick={() => void loadDemo()}>Wczytaj syntetyczną historię demo</button>
      <button className="qo-button qo-primary" disabled={busy || !rows.length} onClick={() => void calculate()}>{busy ? "Obliczanie historii…" : "Uruchom analizę ryzyka"}</button>
    </div>
    {error ? <p className="qo-alert qo-error" role="alert">{error}</p> : null}
    {risk ? <>
      <div className="qo-risk-strip" aria-label="Miary ryzyka historycznego">
        <article><p>VaR · próg straty</p><strong>{money(risk.var_amount, portfolio.base_currency)}</strong><small>{percent(risk.var_fraction)} · nie jest maksymalną stratą</small></article>
        <article><p>ES · średnia strata w ogonie</p><strong>{money(risk.es_amount, portfolio.base_currency)}</strong><small>{percent(risk.es_fraction)} · {risk.tail_count} obserwacji ogona</small></article>
        <article><p>Zmienność jednej obserwacji</p><strong>{percent(risk.daily_volatility)}</strong><small>Odchylenie standardowe, próba ddof = 1</small></article>
        <article><p>Maksymalne obsunięcie</p><strong>{percent(risk.maximum_drawdown)}</strong><small>Spadek od historycznego szczytu symulacji</small></article>
      </div>
      <p className="qo-history-status" role="status">{risk.status === "ok" ? "Obliczono" : risk.status === "unstable" ? "Niestabilny ogon próby" : risk.status === "invalid_data" ? "Nieprawidłowe dane" : "Niewystarczająca historia"} · {risk.observation_count} obserwacji zwrotu / wymagane {risk.required_observations} · {risk.period_start} — {risk.period_end} · {risk.source === "user" ? "Dane użytkownika" : "Zawiera dane syntetyczne"}</p>
      {risk.points.length > 1 ? <RetailChart values={risk.points.map((p) => Number(p.value))} labels={risk.points.map((p) => p.date)} currency={portfolio.base_currency} title="Historyczna symulacja wartości obecnych pozycji" /> : null}
      {risk.correlations.length ? <details className="qo-details"><summary>Korelacje zmian cen w walucie bazowej</summary><div className="qo-table-wrap" role="region" aria-label="Korelacje historyczne" tabIndex={0}><table className="qo-correlation"><caption className="sr-only">Wspólna próba: {risk.observation_count} obserwacji</caption><thead><tr><th scope="col">Instrument</th>{risk.correlation_symbols.map((symbol) => <th scope="col" key={symbol}>{symbol}</th>)}</tr></thead><tbody>{risk.correlations.map((row, index) => <tr key={index}><th scope="row">{risk.correlation_symbols[index]}</th>{row.map((value, column) => <td key={column}>{value === null ? "Nieokreślona" : value.toFixed(2)}</td>)}</tr>)}</tbody></table></div></details> : null}
      <ul className="qo-history-warnings">{risk.warnings.filter((w) => messages[w]).map((warning) => <li key={warning}>{messages[warning]}</li>)}</ul>
    </> : <div className="qo-history-empty"><span aria-hidden="true">∿</span><div><h3>Ryzyko potrzebuje historii</h3><p>Wczytaj przykład lub własny plik cen i kursów. Nie uzupełniamy braków ani nie wyliczamy precyzyjnych miar z kilku dni.</p></div></div>}
    <details className="qo-details"><summary>Wczytaj własną historię cen i kursów</summary>
      <p>CSV: <code>date,symbol,price,fx_to_base,source</code>. Jedna pozycja na datę i symbol; dzienna cena dodatnia; kurs w jednostkach {portfolio.base_currency}; źródło user lub synthetic. Wymagane wspólne daty wszystkich papierów i gotówki walutowej. Gotówka w walucie bazowej pozostaje stała. Przykład: <code>2025-01-02,OWN,100,4,user</code>.</p>
      <label className="qo-field">Plik historii CSV<input type="file" accept=".csv,text/csv" onChange={(e) => {
        const file = e.target.files?.[0]; if (!file) return;
        const token = ++upload.current; setPreview(null);
        if (file.size > 1500000) { setError("Maksymalny rozmiar historii: 1,5 MB."); return; }
        void file.text().then((text) => { if (upload.current === token) setCsv(text); }).catch(() => setError("Nie udało się odczytać pliku."));
      }} /></label>
      <label className="qo-field">Treść historii CSV<textarea rows={4} value={csv} onChange={(e) => { upload.current++; setPreview(null); setCsv(e.target.value); }} /></label>
      <button className="qo-button" disabled={!csv} onClick={() => void inspectCsv()}>Sprawdź historię</button>
      {preview ? <div className="qo-preview"><h3>Podgląd historii: {preview.rows.length} rekordów</h3><p>{preview.rows[0]?.date} — {preview.rows.at(-1)?.date}; {Array.from(new Set(preview.rows.map((r) => r.symbol))).join(", ")}</p><ul>{preview.errors.map((issue, index) => <li key={index}>Wiersz {issue.row}: {issue.message}</li>)}</ul><button className="qo-button qo-primary" disabled={!preview.importable} onClick={() => { latest.current++; setRows(preview.rows); setRisk(null); callback.current(null); setPreview(null); }}>Zatwierdź historię</button></div> : null}
    </details>
    <p className="qo-note">Metoda: kwantyl empiryczny z interpolacją liniową; ES to średnia strat co najmniej równych VaR. Horyzont: jedna wspólna obserwacja, bez skalowania pierwiastkiem czasu. Wymagamy minimum 252 zwrotów i próby pozwalającej oczekiwać 5 obserwacji ogona. Historia musi uwzględniać splity; dywidendy, podatki, przepływy i koszty portfela nie są rekonstruowane.</p>
  </section>;
}
