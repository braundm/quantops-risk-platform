import { useEffect, useRef, useState, type FormEvent } from "react";

import { csvExample, retailRequest, type Analysis, type AnalysisInput, type CsvPreview, type Holding, type Portfolio } from "../data/retailApi";
import { retailLocales } from "../lib/retailLocale";
import { RiskHistoryPanel, type HistoricalRisk } from "../components/RiskHistoryPanel";
import { EducationLab } from "../components/EducationLab";
import { CostPanel, type CostSummary } from "../components/CostPanel";
import { PreferencesPanel, type PreferenceReview } from "../components/PreferencesPanel";
import "../styles/retail.css";
import "../styles/retail-next.css";

const copy = retailLocales.pl;
const STORAGE_KEY = "quantops.local-portfolio.v1";
const classNames = { equity: "Akcje", etf: "ETF", cash: "Gotówka / zobowiązanie" };
const money = (value: string | number, currency = "PLN") => new Intl.NumberFormat("pl-PL", { style: "currency", currency, maximumFractionDigits: 2 }).format(Number(value));
const percent = (value: string | null) => value === null ? "Brak danych" : new Intl.NumberFormat("pl-PL", { style: "percent", maximumFractionDigits: 1 }).format(Number(value));
const decimal = (value: string) => new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 4 }).format(Number(value));
const stamp = (value: string) => new Intl.DateTimeFormat("pl-PL", { dateStyle: "short", timeStyle: "short", timeZone: "UTC" }).format(new Date(value)) + " UTC";

function download(name: string, text: string, mime: string) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

function formText(form: FormData, key: string): string {
  const value = form.get(key);
  return typeof value === "string" ? value : "";
}

function Field({ label, value, onChange, min, max, step = "any", unit }: {
  label: string; value: string; onChange: (value: string) => void;
  min?: number; max?: number; step?: string; unit?: string;
}) {
  return <label className="qo-field"><span>{label}{unit ? <small>{unit}</small> : null}</span><input type="number" required min={min} max={max} step={step} value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

export function RetailPage() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [result, setResult] = useState<{ input: AnalysisInput; data: Analysis } | null>(null);
  const [baseline, setBaseline] = useState<Analysis | null>(null);
  const [history, setHistory] = useState<HistoricalRisk | null>(null);
  const [costBudget, setCostBudget] = useState<CostSummary | null>(null);
  const [preferences, setPreferences] = useState<PreferenceReview | null>(null);
  const [concentrationLimit, setConcentrationLimit] = useState(0.4);
  const [sessionKey, setSessionKey] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [currency, setCurrency] = useState("USD");
  const [fxShock, setFxShock] = useState("-10");
  const [assetShock, setAssetShock] = useState("0");
  const [ratio, setRatio] = useState("50");
  const [days, setDays] = useState("90");
  const [baseRate, setBaseRate] = useState("4");
  const [foreignRate, setForeignRate] = useState("3");
  const [entry, setEntry] = useState("10");
  const [holding, setHolding] = useState("0");
  const [csv, setCsv] = useState("");
  const [preview, setPreview] = useState<CsvPreview | null>(null);
  const [symbol, setSymbol] = useState("");
  const [account, setAccount] = useState("Własny");
  const [kind, setKind] = useState<Holding["asset_class"]>("equity");
  const [positionCurrency, setPositionCurrency] = useState("PLN");
  const [quantity, setQuantity] = useState("1");
  const [price, setPrice] = useState("100");
  const [priceDate, setPriceDate] = useState(new Date().toISOString().slice(0, 16));
  const [fxDate, setFxDate] = useState("2026-01-02T16:00");
  const revision = useRef(0);
  const analysisRequest = useRef(0);
  const csvRequest = useRef(0);
  const initialized = useRef(false);

  useEffect(() => {
    document.documentElement.lang = "pl";
    document.title = "QuantOps — Twój portfel i ryzyko";
    const controller = new AbortController();
    void retailRequest<Portfolio>("demo", undefined, controller.signal)
      .then(setPortfolio)
      .catch((err: unknown) => { if (!controller.signal.aborted) setError(`Uruchom API na porcie 8000. ${err instanceof Error ? err.message : "Brak połączenia."}`); });
    return () => controller.abort();
  }, []);

  async function analyzePortfolio(current: Portfolio) {
    const token = ++analysisRequest.current;
    const currentRevision = revision.current;
    setBusy(true);
    setError("");
    try {
      const numeric = [fxShock, assetShock, ratio, days, baseRate, foreignRate, entry, holding];
      if (numeric.some((value) => value.trim() === "" || !Number.isFinite(Number(value)))) throw new Error("Uzupełnij wszystkie parametry liczbowe.");
      const input: AnalysisInput = {
        portfolio: current, currency, fx_shock: String(Number(fxShock) / 100),
        asset_shock: String(Number(assetShock) / 100), hedge_ratio: String(Number(ratio) / 100),
        days: Number(days), base_rate: String(Number(baseRate) / 100),
        foreign_rate: String(Number(foreignRate) / 100), entry_bps: entry, annual_holding_bps: holding,
      };
      const data = await retailRequest<Analysis>("analyze", input);
      if (token === analysisRequest.current && currentRevision === revision.current) setResult({ input, data });
    } catch (err: unknown) {
      if (token === analysisRequest.current) setError(err instanceof Error ? err.message : "Błąd obliczeń.");
    } finally { if (token === analysisRequest.current) setBusy(false); }
  }

  useEffect(() => {
    if (portfolio !== null && !initialized.current) {
      initialized.current = true;
      void analyzePortfolio(portfolio);
    }
  });

  function invalidate() {
    revision.current++;
    setResult(null);
    setError("");
    setNotice("");
  }

  function changePortfolio(next: Portfolio) { invalidate(); setPortfolio(next); }
  function deletePersonalData() {
    if (!portfolio) return;
    try {
      localStorage.removeItem(STORAGE_KEY);
      changePortfolio({ ...portfolio, positions: [], fx: { [portfolio.base_currency]: "1" }, fx_source: "user" });
      setSessionKey((key) => key + 1); setHistory(null); setCostBudget(null); setPreferences(null);
      setConcentrationLimit(0.4); setBaseline(null); setCsv(""); setPreview(null); csvRequest.current++;
      setSymbol(""); setAccount("Własny"); setQuantity("1"); setPrice("100");
      setNotice("Usunięto lokalny zapis, pozycje, historię, koszty i odpowiedzi z bieżącej sesji.");
    } catch { setError("Nie udało się usunąć lokalnego zapisu."); }
  }
  function parameter(setter: (value: string) => void) { return (value: string) => { invalidate(); setter(value); }; }

  async function confirmHolding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!portfolio) return;
    invalidate();
    const token = revision.current;
    try {
      const candidate: Portfolio = { ...portfolio, positions: [...portfolio.positions, {
        id: crypto.randomUUID(), account, symbol: symbol.trim().toUpperCase(), asset_class: kind,
        currency: positionCurrency, quantity, price: kind === "cash" ? "1" : price,
        multiplier: "1", as_of: new Date(priceDate + "Z").toISOString(), source: "user",
      }] };
      // The Python contract validates manual input with the same rules as CSV input.
      await retailRequest<Analysis>("analyze", {
        portfolio: candidate, currency, fx_shock: "0", asset_shock: "0", hedge_ratio: "0",
      });
      if (token === revision.current) {
        changePortfolio(candidate); setSymbol(""); setNotice("Pozycja dodana. Przelicz portfel, aby zaktualizować wyniki.");
      }
    } catch (err: unknown) { if (token === revision.current) setError(err instanceof Error ? err.message : "Nieprawidłowa pozycja."); }
  }

  async function previewCsv() {
    const token = ++csvRequest.current;
    setPreview(null); setError("");
    try {
      const next = await retailRequest<CsvPreview>("csv-preview", { text: csv });
      if (token === csvRequest.current) setPreview(next);
    } catch (err: unknown) { if (token === csvRequest.current) setError(err instanceof Error ? err.message : "Błąd importu."); }
  }

  async function loadDemo() {
    invalidate();
    const token = revision.current;
    try {
      const next = await retailRequest<Portfolio>("demo");
      if (token !== revision.current) return;
      setPortfolio(next); setCurrency("USD"); setFxDate(next.fx_as_of.slice(0, 16));
      setBaseline(null); setNotice("Wczytano portfel demonstracyjny z danymi syntetycznymi.");
    } catch (err: unknown) { setError(err instanceof Error ? err.message : "Brak połączenia z API."); }
  }

  async function restoreLocal() {
    invalidate(); const token = revision.current;
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) throw new Error("Brak zapisanego portfela w tej przeglądarce.");
      const next = JSON.parse(stored) as Portfolio;
      // Validate stored data before displaying or using it as a portfolio.
      const selected = Object.keys(next.fx).find((code) => code !== next.base_currency);
      if (!selected) throw new Error("Zapis nie zawiera kursu waluty obcej.");
      await retailRequest<Analysis>("analyze", { portfolio: next, currency: selected });
      if (token !== revision.current) return;
      setPortfolio(next); setCurrency(selected); setFxDate(next.fx_as_of.slice(0, 16));
      setBaseline(null); setNotice("Wczytano lokalny zapis. Przelicz portfel.");
    } catch (err: unknown) { setError(err instanceof Error ? err.message : "Nieprawidłowy zapis."); }
  }

  function report() {
    if (!result) return;
    const { data, input } = result;
    const text = [
      "QuantOps — raport analizy portfela", `Model: ${data.model_version}`,
      `Obliczono: ${stamp(data.calculated_at)}`, `Źródło: ${data.source}`, `ID scenariusza: ${data.run_id ?? "pusty portfel"}`,
      `Wartość netto: ${money(data.net_value, data.base_currency)}`,
      `Gotówka: ${money(data.cash_value, data.base_currency)}`,
      `Ekspozycja brutto papierów: ${money(data.gross_exposure, data.base_currency)}`,
      `Szok cen: ${percent(input.asset_shock)}; ${input.currency}: ${percent(input.fx_shock)}`,
      `Termin: ${input.days} dni; ACT/365; stopy: ${percent(input.base_rate)} / ${percent(input.foreign_rate)}`,
      `Koszty: ${input.entry_bps} pb wejście; ${input.annual_holding_bps} pb/rok utrzymanie`,
      "", "Pozycje (wartość / wpływ scenariusza):",
      ...data.positions.map((p) => `${p.symbol}: ${money(p.value, data.base_currency)} / ${money(p.impact, data.base_currency)}`),
      "", "Porównanie zabezpieczeń (nominał walutowy / wpływ łączny po kosztach):",
      ...data.hedges.map((h) => `${percent(h.ratio)}: ${decimal(h.signed_foreign_notional)} ${input.currency} / ${money(h.portfolio_impact, data.base_currency)}; wejście ${money(h.entry_cost, data.base_currency)}, utrzymanie ${money(h.holding_cost, data.base_currency)}; kurs teoretyczny ${decimal(h.theoretical_forward)}`),
      "", "Założenia i ograniczenia:", ...data.warnings.map((w) => copy.warnings[w] ?? w),
      ...(history ? ["", "Symulacja historyczna obecnych ilości:", JSON.stringify(history, null, 2)] : []),
      ...(costBudget ? ["", "Osobny budżet kosztów (nie odejmowany ponownie od cen):", JSON.stringify(costBudget, null, 2)] : []),
      ...(preferences ? ["", "Spójność odpowiedzi i własne limity:", JSON.stringify(preferences, null, 2)] : []),
      "Szok cen dotyczy wszystkich papierów; gotówka podlega tylko szokowi walutowemu.",
      "Ceny i waluta są przeliczane łącznie: (1 + szok ceny) × (1 + szok waluty).",
      "Zabezpieczenie ma stały nominał początkowy. Zmiana cen może prowadzić do nadmiernego zabezpieczenia.",
      "Zabezpieczenie waluty nie usuwa ryzyka spadku aktywa. Wyniki są hipotetyczne, nie stanowią rekomendacji.",
      "", "Pełne dane wejściowe:", JSON.stringify(input, null, 2),
    ].join("\n");
    download("QuantOps-raport.txt", text, "text/plain;charset=utf-8");
  }

  const data = result?.data;
  const base = portfolio?.base_currency ?? "PLN";
  const selectedExposure = data?.exposures.find((e) => e.currency === currency);

  return <div className="qo-app">
    <a className="skip-link" href="#main-content">Przejdź do treści</a>
    <aside className="qo-sidebar">
      <a className="qo-brand" href="/">Q<span>QuantOps<small>PORTFEL · RYZYKO · WIEDZA</small></span></a>
      <p className="qo-nav-label">TWÓJ PORTFEL</p>
      <nav aria-label="Główna nawigacja">
        <a href="#overview">◫ <span>Przegląd portfela</span></a>
        <a href="#positions">▤ <span>Pozycje i import</span></a>
        <a href="#exposures">◎ <span>Ekspozycje</span></a>
        <a href="#risk">∿ <span>Ryzyko historyczne</span></a>
        <a href="#scenario">↗ <span>Scenariusze</span></a>
        <a href="#hedge">⇄ <span>Zabezpieczenia i koszty</span></a>
        <a href="#costs">◷ <span>Budżet kosztów</span></a>
        <a href="#lab">◇ <span>Laboratorium</span></a>
        <a href="#profile">◉ <span>Moje cele i limity</span></a>
        <a href="#integrations">⊞ <span>Integracje</span></a>
        <a href="#assumptions">ⓘ <span>Metoda i dane</span></a>
      </nav>
      <div className="qo-sidebar-bottom"><strong>Analiza przed decyzją</strong><p>Sprawdź konsekwencje. Zabezpieczenie waluty nie usuwa ryzyka aktywów.</p><a href="/research">Środowisko badawcze →</a></div>
    </aside>
    <div className="qo-column">
      <header className="qo-topbar"><span>Przestrzeń osobista <b>/</b> Portfel</span><span className="qo-tag">Lokalnie · bez połączenia z brokerem</span></header>
      <main id="main-content" tabIndex={-1}>
        <section className="qo-heading" id="overview"><div><p className="qo-eyebrow">WIESZ WIĘCEJ. DECYDUJESZ ŚWIADOMIE.</p><h1>{copy.title}</h1><p>{copy.subtitle}</p></div><button className="qo-button" disabled={!result} onClick={report}>↓ Eksportuj raport</button></section>
        {error ? <div className="qo-alert qo-error" role="alert">{error}</div> : null}
        {notice ? <div className="qo-alert" role="status">{notice}</div> : null}
        {!portfolio ? <section className="qo-panel"><h2>Łączenie z lokalnym silnikiem…</h2><p>Uruchom API i interfejs według instrukcji w README.</p><button className="qo-button" onClick={() => void loadDemo()}>Spróbuj ponownie</button></section> : <>
          <div className="qo-source"><span className="qo-dot" /><strong>{(portfolio.fx_source === "synthetic" || portfolio.positions.some((p) => p.source === "synthetic")) ? (portfolio.fx_source === "user" || portfolio.positions.some((p) => p.source === "user") ? "Dane mieszane · zawierają dane syntetyczne" : "Demo · dane syntetyczne") : "Dane użytkownika"}</strong><span>Ceny i kursy wpisane ręcznie. Brak danych na żywo.</span><button onClick={() => void loadDemo()}>Wczytaj demo</button></div>
          <section className="qo-metrics" aria-label="Podsumowanie portfela">
            <article><p>Wartość netto portfela</p><strong>{data ? money(data.net_value, base) : "—"}</strong><small>Pozycje + gotówka − zobowiązania</small></article>
            <article><p>Gotówka netto</p><strong>{data ? money(data.cash_value, base) : "—"}</strong><small>Uwzględniona raz w wartości portfela</small></article>
            <article><p>Największa pozycja</p><strong>{data ? percent(data.concentration) : "—"}</strong><small>Udział w ekspozycji brutto papierów</small></article>
            <article><p>Wpływ scenariusza bez hedge</p><strong className="qo-impact">{data ? money(data.unhedged_impact, base) : "—"}</strong><small>{data ? percent(data.impact_fraction) : "Przelicz po zmianie danych"} wartości netto</small></article>
          </section>

          <div className="qo-two-columns">
            <section className="qo-panel" id="exposures"><div className="qo-panel-heading"><div><p className="qo-eyebrow">CO FAKTYCZNIE POSIADASZ</p><h2>Ekspozycja walutowa</h2></div><span className="qo-tag">Waluta notowania</span></div>
              <p className="qo-muted">Wartość pozycji według waluty, w {base}. Wykres pokazuje kwoty netto; udziały brutto uwzględniają pozycje krótkie.</p>
              {data ? <div className="qo-exposures">{data.exposures.map((exposure) => {
                const total = data.exposures.reduce((sum, item) => sum + Number(item.gross_base), 0);
                return <div key={exposure.currency}><div><strong>{exposure.currency}</strong><span>{money(exposure.net_base, base)}</span></div><div className="qo-bar" aria-hidden="true"><i style={{ width: `${total ? Number(exposure.gross_base) / total * 100 : 0}%` }} /></div><small>Brutto {money(exposure.gross_base, base)} · netto {decimal(exposure.foreign_amount)} {exposure.currency}</small></div>;
              })}</div> : <p className="qo-muted">Przelicz portfel, aby zobaczyć aktualne ekspozycje.</p>}
              <p className="qo-note">ETF notowany w EUR może posiadać aktywa w USD. Pełna ekspozycja aktywów bazowych nie jest dostępna.</p>
            </section>
            <section className="qo-panel"><p className="qo-eyebrow">DANE ZAMIAST POJEDYNCZEJ OCENY</p><h2>Co warto sprawdzić</h2>
              {data ? <><div className="qo-observation"><span>01</span><div><strong>{Number(data.concentration) > concentrationLimit ? `Koncentracja powyżej Twojego limitu ${percent(String(concentrationLimit))}` : "Sprawdź strukturę ekspozycji"}</strong><p>Największa pozycja ma {percent(data.concentration)} ekspozycji brutto papierów. Źródło: ilości, ceny i kursy w tabeli pozycji.</p></div></div>
                <div className="qo-observation"><span>02</span><div><strong>{data.warnings.includes("stale_prices") || data.warnings.includes("stale_fx") ? "Wycena wymaga aktualizacji" : "Wycena według wpisanych danych"}</strong><p>Kursy z {stamp(portfolio.fx_as_of)}. Daty cen znajdziesz przy każdej pozycji.</p></div></div>
                <dl className="qo-stat-list"><div><dt>Ekspozycja brutto papierów</dt><dd>{money(data.gross_exposure, base)}</dd></div><div><dt>Ekspozycja netto papierów</dt><dd>{money(data.net_exposure, base)}</dd></div><div><dt>Brutto / wartość netto</dt><dd>{data.gross_to_equity === null ? "Brak danych" : decimal(data.gross_to_equity) + "×"}</dd></div><div><dt>VaR i Expected Shortfall</dt><dd>{history?.status === "ok" ? "Obliczono z historii" : "Wczytaj historię poniżej"}</dd></div></dl></> : <p>Obserwacje pojawią się po przeliczeniu. Stare wyniki są ukrywane po zmianie danych.</p>}
            </section>
          </div>

          <RiskHistoryPanel key={`history-${sessionKey}`} portfolio={portfolio} onResult={setHistory} />
          <section className="qo-panel" id="positions"><div className="qo-panel-heading"><div><p className="qo-eyebrow">POZYCJE I WYCENA</p><h2>Twój portfel</h2></div><button className="qo-button" onClick={() => { changePortfolio({ ...portfolio, positions: [], fx: { [base]: "1", [base === "USD" ? "PLN" : "USD"]: "" }, fx_source: "user" }); setCurrency(base === "USD" ? "PLN" : "USD"); setBaseline(null); }}>Utwórz pusty portfel</button></div>
            <div className="qo-actions"><button className="qo-button" disabled={!data} onClick={() => { if (data) { setBaseline(data); setNotice("Zapisano punkt odniesienia. Zmień pozycje i przelicz wariant."); } }}>Zapisz punkt porównania</button><button className="qo-button" onClick={() => { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(portfolio)); setNotice("Zapisano w tej przeglądarce. Zapis lokalny nie jest szyfrowany."); } catch { setError("Przeglądarka nie pozwala zapisać danych."); } }}>Zapisz lokalnie</button><button className="qo-button" onClick={() => void restoreLocal()}>Wczytaj zapis</button><button className="qo-button" onClick={deletePersonalData}>Usuń moje dane</button></div>
            <div className="qo-table-wrap" role="region" aria-label="Pozycje portfela" tabIndex={0}><table><caption className="sr-only">Bieżące pozycje, kierunek i wycena</caption><thead><tr><th>Instrument / rachunek</th><th>Klasa / waluta</th><th>Ilość</th><th>Cena</th><th>Wartość w {base}</th><th>Stan danych</th><th>Zmiana</th></tr></thead><tbody>{portfolio.positions.map((p) => <tr key={p.id}><th scope="row">{p.symbol}<small>{p.account} · {Number(p.quantity) < 0 ? "krótka / zobowiązanie" : "długa"}</small></th><td>{classNames[p.asset_class]}<small>{p.currency}</small></td><td><input aria-label={`Ilość ${p.symbol}`} type="number" step="any" value={p.quantity} onChange={(e) => changePortfolio({ ...portfolio, positions: portfolio.positions.map((item) => item.id === p.id ? { ...item, quantity: e.target.value } : item) })} /></td><td><input aria-label={`Cena ${p.symbol}`} type="number" min="0" step="any" disabled={p.asset_class === "cash"} value={p.price} onChange={(e) => changePortfolio({ ...portfolio, positions: portfolio.positions.map((item) => item.id === p.id ? { ...item, price: e.target.value } : item) })} /></td><td>{data?.positions.find((item) => item.id === p.id) ? money(data.positions.find((item) => item.id === p.id)!.value, base) : "—"}</td><td><span className="qo-tag">{p.source === "synthetic" ? "Syntetyczne" : "Wprowadzone"}</span><small>{stamp(p.as_of)}</small></td><td><button className="qo-text-button" aria-label={`Usuń ${p.symbol}`} onClick={() => changePortfolio({ ...portfolio, positions: portfolio.positions.filter((item) => item.id !== p.id) })}>Usuń</button></td></tr>)}</tbody></table></div>
            {portfolio.positions.length === 0 ? <p>Portfel jest pusty. Dodaj pozycję lub zaimportuj CSV.</p> : null}
            <details className="qo-details"><summary>Dodaj pozycję ręcznie</summary><form className="qo-form-grid" onSubmit={(event) => void confirmHolding(event)}>
              <label className="qo-field">Rachunek<input required maxLength={64} value={account} onChange={(e) => setAccount(e.target.value)} /></label>
              <label className="qo-field">Symbol<input required maxLength={32} value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="np. QGLOBAL" /></label>
              <label className="qo-field">Typ<select value={kind} onChange={(e) => setKind(e.target.value as Holding["asset_class"])}>{Object.entries(classNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
              <label className="qo-field">Waluta pozycji<select value={positionCurrency} onChange={(e) => setPositionCurrency(e.target.value)}>{Object.keys(portfolio.fx).map((code) => <option key={code}>{code}</option>)}</select></label>
              <Field label="Ilość (ujemna = short / dług)" value={quantity} onChange={setQuantity} />
              {kind !== "cash" ? <Field label="Cena jednostkowa" min={0.0000000001} value={price} onChange={setPrice} /> : <p>Cena jednostkowa gotówki = 1.</p>}
              <label className="qo-field">Data ceny (UTC)<input required type="datetime-local" value={priceDate} onChange={(e) => setPriceDate(e.target.value)} /></label>
              <button className="qo-button qo-primary" type="submit">Dodaj pozycję</button>
              <p className="qo-note qo-full">Obsługiwane: akcje, ETF i gotówka z mnożnikiem 1. Instrumenty wpisujesz samodzielnie; nie są weryfikowane w katalogu giełdowym. Pochodne wymagają osobnego modelu.</p>
            </form></details>
            <details className="qo-details"><summary>Import CSV z podglądem</summary><p>Import aktualnych pozycji zastępuje całą tabelę po zatwierdzeniu. Nie jest historią transakcji. Separatory: przecinek; liczby: kropka dziesiętna; czas: ISO 8601 ze strefą; source: user lub synthetic. Zachowaj synthetic dla danych przykładowych.</p><button className="qo-button" onClick={() => download("QuantOps-synthetic-positions.csv", csvExample, "text/csv;charset=utf-8")}>Pobierz syntetyczny przykład CSV</button><p><code>account, symbol, asset_class, currency, quantity, price, multiplier, as_of, source</code></p><label className="qo-field">Wybierz plik CSV<input type="file" accept=".csv,text/csv" onChange={(e) => {
              const file = e.target.files?.[0]; if (!file) return;
              const token = ++csvRequest.current;
              setPreview(null);
              if (file.size > 200000) { setError("Plik może mieć najwyżej 200 kB."); return; }
              void file.text().then((text) => { if (token === csvRequest.current) setCsv(text); }).catch(() => setError("Nie udało się odczytać pliku."));
            }} /></label><label className="qo-field">Treść CSV<textarea rows={5} value={csv} onChange={(e) => { csvRequest.current++; setCsv(e.target.value); setPreview(null); }} /></label><button className="qo-button" disabled={!csv} onClick={() => void previewCsv()}>Sprawdź i pokaż podgląd</button>
              {preview ? <div className="qo-preview"><h3>Podgląd: {preview.positions.length} poprawnych pozycji</h3>{preview.errors.length ? <ul role="alert">{preview.errors.map((issue, index) => <li key={index}>Wiersz {issue.row}: {issue.message}</li>)}</ul> : null}<p>Nieznane symbole są danymi użytkownika. Zweryfikuj typ i identyfikator; opcje, CFD i kontrakty nie są obsługiwane.</p><ul>{preview.positions.map((p) => <li key={p.id}>{p.account} · {p.symbol} · {p.quantity} × {p.price} {p.currency} · {classNames[p.asset_class]}</li>)}</ul><button className="qo-button qo-primary" disabled={!preview.importable || preview.positions.some((p) => !portfolio.fx[p.currency])} onClick={() => { changePortfolio({ ...portfolio, positions: preview.positions }); setPreview(null); setNotice("Import zatwierdzony. Przelicz portfel."); }}>Zatwierdź zastąpienie pozycji</button>{preview.positions.some((p) => !portfolio.fx[p.currency]) ? <p role="alert">Najpierw dodaj kurs każdej waluty importu w panelu poniżej.</p> : null}</div> : null}
            </details>
          </section>

          <div className="qo-two-columns qo-scenario-grid">
            <section className="qo-panel" id="scenario"><p className="qo-eyebrow">EKSPERYMENT, NIE PROGNOZA</p><h2>Co jeśli rynek się zmieni?</h2><form onSubmit={(e) => { e.preventDefault(); void analyzePortfolio(portfolio); }}>
              <div className="qo-form-grid">
                <label className="qo-field">Waluta zabezpieczenia<select value={currency} onChange={(e) => parameter(setCurrency)(e.target.value)}>{Object.keys(portfolio.fx).filter((code) => code !== base).map((code) => <option key={code}>{code}</option>)}</select></label>
                <Field label={`Zmiana ${currency}/${base}`} unit="%" value={fxShock} onChange={parameter(setFxShock)} min={-99.99} max={500} />
                <Field label="Zmiana cen wszystkich papierów" unit="%" value={assetShock} onChange={parameter(setAssetShock)} min={-100} max={500} />
                <Field label="Częściowe zabezpieczenie" unit="%" value={ratio} onChange={parameter(setRatio)} min={0} max={100} />
                <Field label="Termin rozliczenia" unit="dni" value={days} onChange={parameter(setDays)} min={1} max={3650} step="1" />
                <Field label={`Stopa ${base} (założenie)`} unit="% / rok" value={baseRate} onChange={parameter(setBaseRate)} min={-10} max={100} />
                <Field label={`Stopa ${currency} (założenie)`} unit="% / rok" value={foreignRate} onChange={parameter(setForeignRate)} min={-10} max={100} />
                <Field label="Koszt wejścia" unit="pb nominału" value={entry} onChange={parameter(setEntry)} min={0} max={10000} />
                <Field label="Koszt utrzymania" unit="pb / rok" value={holding} onChange={parameter(setHolding)} min={0} max={10000} />
              </div>
              <p className="qo-note">Ujemna zmiana USD/PLN oznacza osłabienie USD. Szok cen i kursu łączymy mnożeniem, aby uwzględnić efekt łączny tylko raz. 1 pb = 0,01%. Koszt utrzymania wpisz bez carry zawartego już w kursie forward.</p>
              <button className="qo-button qo-primary qo-calculate" disabled={busy} type="submit">{busy ? "Obliczanie…" : "Przelicz portfel i zabezpieczenie →"}</button>
            </form></section>
            <section className="qo-panel qo-hedge-intro"><p className="qo-eyebrow">OGRANICZAJ EKSPOZYCJĘ, POZNAJ KOSZT</p><h2>Zabezpieczenie waluty</h2><div className="qo-hedge-visual" aria-hidden="true"><span>{currency}</span><i>⇄</i><span>{base}</span></div><p>Modelowy forward blokuje kurs dla stałego nominału. Dla dodatniej ekspozycji sprzedajesz walutę obcą w terminie; dla ujemnej — kupujesz.</p><dl className="qo-stat-list"><div><dt>Ekspozycja przed</dt><dd>{selectedExposure ? money(selectedExposure.foreign_amount, currency) : "—"}</dd></div><div><dt>Kurs teoretyczny w terminie</dt><dd>{data?.hedges[0] ? decimal(data.hedges[0].theoretical_forward) + ` ${base}/${currency}` : "—"}</dd></div><div><dt>Kurs po szoku</dt><dd>{data?.hedges[0] ? decimal(data.hedges[0].terminal_spot) + ` ${base}/${currency}` : "—"}</dd></div></dl><p className="qo-note">To model edukacyjny. Nie jest ofertą brokera. Zmiana wartości aktywów może spowodować nadmierne zabezpieczenie początkowego nominału.</p></section>
          </div>

          <section className="qo-panel" id="hedge" aria-live="polite"><div className="qo-panel-heading"><div><p className="qo-eyebrow">TRZY WARIANTY · TE SAME ZAŁOŻENIA</p><h2>Porównanie po kosztach</h2></div><span className="qo-tag">Hipotetyczny wynik w {base}</span></div>
            {data ? <><div className="qo-hedge-cards">{data.hedges.map((h, index) => <article key={index} className={index === 1 ? "qo-selected-card" : ""}><p>{index === 0 ? "Bez zabezpieczenia" : index === 1 ? `Częściowe · ${percent(h.ratio)}` : "Pełne · 100%"}</p><strong>{money(h.portfolio_impact, base)}</strong><small>Wpływ na portfel po kosztach</small><dl className="qo-stat-list"><div><dt>Wartość w scenariuszu</dt><dd>{money(h.terminal_value, base)}</dd></div><div><dt>Nominał obcy</dt><dd>{money(h.signed_foreign_notional, currency)}</dd></div><div><dt>Nominał bazowy (bezwzględny)</dt><dd>{money(h.base_notional, base)}</dd></div><div><dt>Kierunek</dt><dd>{Number(h.signed_foreign_notional) > 0 ? `Sprzedaż ${currency}` : Number(h.signed_foreign_notional) < 0 ? `Kupno ${currency}` : "Brak"}</dd></div><div><dt>Pozostała ekspozycja początkowa</dt><dd>{money(h.remaining_foreign_exposure, currency)}</dd></div><div><dt>Wynik forward przed kosztami</dt><dd>{money(h.payoff, base)}</dd></div><div><dt>Koszt jednorazowy</dt><dd>{money(h.entry_cost, base)}</dd></div><div><dt>Koszt przez {days} dni</dt><dd>{money(h.holding_cost, base)}</dd></div></dl>{h.overhedged_after_shock ? <p className="qo-warning">Nadmierne zabezpieczenie: po szoku aktywów nominał przekracza pozostałą ekspozycję.</p> : null}</article>)}</div>
              <details className="qo-details"><summary>Wpływ poszczególnych pozycji</summary><ul>{data.positions.map((p) => <li key={p.id}>{p.symbol}: {money(p.impact, base)}</li>)}</ul></details>
            </> : <p>Po zmianie danych przelicz portfel. Wyniki i eksport są dostępne tylko dla aktualnych założeń.</p>}
            {baseline && data ? <div className="qo-comparison"><h3>Porównanie składu portfela</h3><p>Punkt odniesienia: {money(baseline.net_value, baseline.base_currency)} → aktualnie: {money(data.net_value, base)}. Koncentracja: {percent(baseline.concentration)} → {percent(data.concentration)}. To porównanie wycen, nie wyniki inwestora ani historyczny zwrot.</p></div> : null}
          </section>

          <section className="qo-panel">
            <p className="qo-eyebrow">DANE WPROWADZANE PRZEZ CIEBIE</p>
            <h2>Kursy walut i świeżość</h2>
            <p className="qo-muted">Jednostka: liczba {base} za 1 jednostkę waluty obcej. Zmiana waluty bazowej wymaga jawnego wpisania wszystkich kursów.</p>
            <div className="qo-form-grid">
              <label className="qo-field">Waluta bazowa
                <select aria-label="Waluta bazowa" value={base} onChange={(e) => {
                  const next = e.target.value;
                  changePortfolio({
                    ...portfolio, base_currency: next,
                    fx: Object.fromEntries(Object.keys(portfolio.fx).map((code) => [code, code === next ? "1" : ""])),
                    fx_source: "user",
                  });
                  setCurrency(Object.keys(portfolio.fx).find((code) => code !== next) ?? "USD");
                  setBaseline(null);
                }}>
                  {Object.keys(portfolio.fx).map((code) => <option key={code}>{code}</option>)}
                </select>
              </label>
              {Object.entries(portfolio.fx).map(([code, value]) =>
                <label className="qo-field" key={code}>Kurs {code}/{base}
                  <input required type="number" min="0.0000000001" step="any" disabled={code === base} value={value}
                    onChange={(e) => changePortfolio({ ...portfolio, fx: { ...portfolio.fx, [code]: e.target.value }, fx_source: portfolio.fx_source })} />
                </label>,
              )}
              <label className="qo-field">Data kursów (UTC)
                <input type="datetime-local" value={fxDate} onChange={(e) => {
                  setFxDate(e.target.value); invalidate();
                  setPortfolio({ ...portfolio, fx_as_of: e.target.value ? new Date(e.target.value + "Z").toISOString() : "", fx_source: portfolio.fx_source });
                }} />
              </label>
            </div>
            <form className="qo-add-fx" onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              const code = formText(form, "code").trim().toUpperCase();
              const rate = formText(form, "rate");
              if (code === base) { setError("Kurs waluty bazowej musi wynosić 1."); return; }
              changePortfolio({ ...portfolio, fx: { ...portfolio.fx, [code]: rate }, fx_source: portfolio.fx_source });
            }}>
              <label className="qo-field">Dodaj walutę (ISO)<input name="code" required pattern="[A-Za-z]{3}" maxLength={3} placeholder="CHF" /></label>
              <label className="qo-field">Kurs do {base}<input name="rate" required type="number" min="0.0000000001" step="any" /></label>
              <button className="qo-button" type="submit">Dodaj kurs</button>
            </form>
          </section>

          <CostPanel key={`cost-${sessionKey}`} currency={base} onResult={setCostBudget} />
          <EducationLab key={`lab-${sessionKey}`} />
          <PreferencesPanel key={`profile-${sessionKey}-${base}`} analysis={data ?? null} onLimit={setConcentrationLimit} onResult={setPreferences} />
          <section className="qo-panel" id="integrations"><p className="qo-eyebrow">TWOJE ŹRÓDŁA DANYCH</p><h2>Integracje i import</h2><div className="qo-integration-grid"><article><span className="qo-integration-icon">CSV</span><h3>Pliki i dane ręczne</h3><p>Aktywne · pozycje i historia cen z podglądem oraz walidacją.</p><a href="#positions">Importuj pozycje →</a></article><article><span className="qo-integration-icon">MT5</span><h3>MetaTrader 5</h3><p>Planowany adapter tylko do odczytu. Wymaga terminala i lokalnego komponentu pośredniczącego. Niepołączony.</p></article><article><span className="qo-integration-icon">B</span><h3>Bossa</h3><p>Niepołączona. Sposób dostępu i warunki użycia danych wymagają weryfikacji przed wdrożeniem.</p></article></div></section>
          <section className="qo-panel" id="assumptions"><p className="qo-eyebrow">PRZEJRZYSTOŚĆ OBLICZEŃ</p><h2>Założenia i ograniczenia</h2><p>Wycena: ilość × cena × kurs. Scenariusz: stałe pozycje, wspólny szok wszystkich akcji i ETF, osobny szok wybranej waluty. Model forward: F = S × (1 + stopa bazowa × dni/365) / (1 + stopa obca × dni/365). Wynik: podpisany nominał × (F − kurs po szoku), pomniejszony o koszty.</p><ul>{(data?.warnings ?? ["quotation_currency_only", "no_historical_returns", "terminal_forward_model", "no_broker_quote"]).map((warning) => <li key={warning}>{copy.warnings[warning] ?? warning}</li>)}</ul><p className="qo-note">Dostępne: portfel, CSV, ekspozycje, historia cen, scenariusze, model forward, budżet kosztów, ankieta i laboratorium. Integracje brokerskie, historia transakcji i przepływów oraz wspólna baza użytkowników pozostają kolejnymi etapami. Istniejące badawcze VaR i ES są dostępne w <a href="/dashboard">środowisku syntetycznym</a>.</p>{data ? <p className="qo-metadata">{data.model_version} · obliczono {stamp(data.calculated_at)} · ID scenariusza <code>{data.run_id ?? "pusty portfel"}</code></p> : null}</section>
        </>}
      </main><footer className="qo-footer">QuantOps · Zrozumienie ryzyka przed decyzją.<span>Bez wykonywania transakcji · Daty w UTC</span></footer>
    </div>
  </div>;
}
