import { useEffect, useRef, useState } from "react";
import { money, pct } from "../data/investorApi";
import type { AllocationResult, PerformanceSummary, RiskHistory, RiskInput, RiskResult, RiskScenario } from "../data/portfolioRiskApi";
import { xtbRequest, type XtbAnalysis } from "../data/xtbApi";
import type { XtbAccount } from "../lib/xtbAccounts";
import { HistoryChart } from "./InvestorCharts";
import { MonteCarloPanel } from "./MonteCarloPanel";
import { DrawdownChart, RiskConcentration, RiskDiversification, RiskOverview, RiskTabs } from "./RiskDashboard";
import "../styles/portfolioRisk.css";

const currencies = ["PLN", "USD", "EUR", "GBP", "CHF"];
const fraction = (value: string | number | null | undefined) => pct(value == null ? null : Number(value));
const yesterday = () => new Date(Date.now() - 86400000).toISOString().slice(0, 10);
const initialScenario: RiskScenario = { name: "Hipotetyczny spadek akcji i ETF o 20%", position_shocks: {}, class_shocks: { equity: "-0.2", etf: "-0.2" }, fx_shocks: {} };
const initialScenarios = ["0.1", "0.2", "0.35"].map(shock => ({ ...initialScenario, name: `Hipotetyczny spadek akcji o ${Number(shock)*100}%`, class_shocks: { equity: `-${shock}` } }));

function percentInput(raw: string): string {
  if (!/^\d{1,3}(?:\.\d{1,8})?$/.test(raw)) throw new Error("Wagi i szoki: liczba z maksymalnie 8 miejscami po przecinku.");
  const [whole, decimals = ""] = raw.split(".");
  const digits = `${whole}${decimals.padEnd(8, "0")}`.replace(/^0+(?=\d)/, "").padStart(11, "0");
  return `${digits.slice(0, -10)}.${digits.slice(-10)}`;
}
function copyWeights(weights: Record<string, string>): Record<string, string> {
  const rounded = Object.entries(weights).map(([s, w]) => [s, Math.round(Number(w) * 100000000)] as const);
  const largest = rounded.reduce((a, b) => b[1] > a[1] ? b : a);
  const residual = 100000000 - rounded.reduce((sum, [, w]) => sum + w, 0);
  return Object.fromEntries(rounded.map(([s, w]) => [s, ((w + (s === largest[0] ? residual : 0)) / 1000000).toFixed(6)]));
}

function checkedHistories(data: unknown): RiskHistory[] {
  if (!Array.isArray(data) || data.length > 50) throw new Error("Oczekiwano do 50 historii z metadanymi źródeł.");
  for (const value of data as unknown[]) {
    if (!value || typeof value !== "object") throw new Error("Niepoprawna historia instrumentu.");
    const h = value as Partial<RiskHistory>;
    if (![h.symbol, h.currency, h.base_currency, h.source, h.fx_source, h.fetched_at].every(s => typeof s === "string" && s.length > 0) ||
        typeof h.source_url !== "string" || !h.source_url.startsWith("https://") || !["provider", "user", "synthetic"].includes(h.origin ?? "") ||
        h.price_basis !== "split_dividend_adjusted" || !Array.isArray(h.rows) || h.rows.length < 2 || h.rows.length > 1300 ||
        !h.rows.every(row => row && typeof row.date === "string" && [row.close, row.adjusted_close, row.fx_to_base].every(n => typeof n === "string" && n.trim() && Number.isFinite(Number(n)) && Number(n) > 0))) {
      throw new Error("Historia wymaga symbolu, walut, źródła HTTPS, daty pobrania oraz dodatnich cen skorygowanych i FX. Pełną walidację dat i zgodności wykona API.");
    }
  }
  return data as RiskHistory[];
}

const warningDescriptions: Record<string, string> = {
  unsupported_derivative_or_unclassified: "Ten instrument wymaga innego modelu ryzyka; pełna analiza tego rachunku jest niedostępna.",
  unsupported_listing_or_asset_type: "Ten typ instrumentu lub rynek nie jest obsługiwany w tej analizie.",
  missing_history_or_fx: "Brakuje cen historycznych lub kursów walut. Pobierz historie albo sprawdź źródło danych.",
  split_requires_quantity_reconciliation: "Po splicie trzeba uzgodnić liczbę jednostek z aktualnym raportem rachunku.",
  no_common_valuation_date: "Brakuje wspólnego dnia wyceny. Potrzebne są ceny i kursy walut z tego samego dnia.",
  current_allocation_simulation_not_actual_performance: "Symulacja obecnej alokacji, nie faktyczny wynik inwestora.",
  buy_and_hold_no_rebalancing: "Początkowe wagi odpowiadają obecnemu składowi; potem brak rebalancingu.",
  adjusted_total_returns_dividends_reinvested_once: "Korekty splitów i reinwestowane dywidendy ujęte raz w stopach zwrotu.",
  costs_taxes_inflation_excluded: "Koszty, podatki, inflacja i oprocentowanie gotówki są pominięte.",
  cash_balance_must_be_confirmed_not_inferred_from_flows: "Saldo gotówki wymaga potwierdzenia; przepływy nie są saldem.",
  no_proxy_substitution: "Brakujące instrumenty nie są zastępowane proxy.",
  listing_country_is_not_issuer_country: "Kraj notowania nie określa kraju emitenta ani jego przychodów.",
  quote_currency_is_not_economic_exposure: "Waluta notowania nie opisuje wszystkich ekspozycji ekonomicznych.",
  unknown_etf_holdings_are_not_invented: "Nieznane składy ETF pozostają brakiem danych.",
  var_is_not_maximum_loss: "VaR nie jest maksymalną możliwą stratą.",
  common_calendar_no_fill_no_returns_across_missing_union_dates: "Wspólny kalendarz bez uzupełniania cen. Pary przechodzące przez brakującą sesję są pomijane w estymacji ryzyka.",
  cash_balance_unconfirmed: "Nie potwierdzono kompletnego salda gotówki.",
  securities_only_account_cash_not_included: "Analiza zapisanych akcji i ETF. Raport nie zawiera salda gotówki, więc gotówka rachunku nie jest uwzględniona.",
  equities_only_other_instruments_not_included: "Wybrany zakres obejmuje wyłącznie akcje bez dźwigni. Inne instrumenty pokazujemy jako pozostające poza analizą.",
  cash_balance_date_differs_from_valuation: "Data salda gotówki różni się od wspólnej daty wyceny.",
  stale_valuation_date: "Ostatnia wspólna wycena jest starsza niż 7 dni.",
  valuation_precedes_quantity_snapshot: "Ceny kończą się przed datą stanu pozycji. Potrzebna jest późniejsza wycena, niezależnie od okresu symulacji.",
  synthetic_history: "Analiza zawiera oznaczone dane syntetyczne.",
};

function download(name: string, payload: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function PortfolioRisk({ account }: { account: XtbAccount }) {
  const [base, setBase] = useState(account.book.currency);
  const [histories, setHistories] = useState<RiskHistory[]>([]);
  const [start, setStart] = useState(new Date(Date.now() - 3 * 365 * 86400000).toISOString().slice(0, 10));
  const [end, setEnd] = useState(yesterday);
  const [benchmark, setBenchmark] = useState("");
  const [confidence, setConfidence] = useState("0.95");
  const [tolerance, setTolerance] = useState("10");
  const [toleranceKind, setToleranceKind] = useState("percent");
  const [scenarioText, setScenarioText] = useState(JSON.stringify(initialScenarios, null, 2));
  const [stressPreset, setStressPreset] = useState("custom");
  const [quickPrice, setQuickPrice] = useState("-20");
  const [quickFx, setQuickFx] = useState("-10");
  const [quickCurrency, setQuickCurrency] = useState(account.book.currency === "USD" ? "EUR" : "USD");
  const [variant, setVariant] = useState<Record<string, string> | null>(null);
  const [extra, setExtra] = useState("");
  const [metadataText, setMetadataText] = useState("[]");
  const [etfText, setEtfText] = useState("[]");
  const [example, setExample] = useState<RiskInput | null>(null);
  const [result, setResult] = useState<RiskResult | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [section, setSection] = useState("summary");
  const pending = useRef<AbortController | null>(null);
  const latest = useRef<RiskInput | null>(null);
  const resultAnchor = useRef<HTMLElement | null>(null);
  const variantAnchor = useRef<HTMLElement | null>(null);
  useEffect(() => () => pending.current?.abort(), []);
  useEffect(() => {
    pending.current?.abort(); setResult(null); setExample(null); setVariant(null); setHistories([]);
    setBase(account.book.currency); setBenchmark(""); setEnd(yesterday()); setSection("summary"); setBusy(false); setError(""); setNotice("");
    setStart(new Date(Date.now() - 3 * 365 * 86400000).toISOString().slice(0, 10));
    setScenarioText(JSON.stringify(initialScenarios, null, 2)); setStressPreset("custom"); setMetadataText("[]"); setEtfText("[]");
  }, [account.book]);
  useEffect(() => { if (result) resultAnchor.current?.scrollIntoView({ block: "start" }); }, [result]);
  useEffect(() => { if (variant) variantAnchor.current?.scrollIntoView({ block: "start" }); }, [Boolean(variant)]);
  function invalidate() { pending.current?.abort(); setResult(null); setBusy(false); setNotice(""); }
  function input(): RiskInput {
    const variants = variant ? Object.fromEntries(Object.entries(variant).map(([s, w]) => [s, percentInput(w)])) : null;
    return { book: example?.book ?? account.book, scope: "securities_only", asset_scope: "equities_only", base_currency: base, histories,
      cash: example?.cash ?? [],
      cash_confirmed: example?.cash_confirmed ?? false, start: start || null, end: end || null, benchmark: benchmark || null,
      confidence, tolerance_amount: toleranceKind === "amount" && tolerance ? tolerance : null,
      tolerance_fraction: toleranceKind === "percent" && tolerance ? percentInput(tolerance) : null,
      scenarios: JSON.parse(scenarioText) as RiskScenario[], variant: variants,
      metadata: JSON.parse(metadataText) as unknown[], etf_compositions: JSON.parse(etfText) as unknown[] };
  }
  async function analyze(target?: string) {
    if (target) setSection(target);
    const controller = new AbortController(); pending.current?.abort(); pending.current = controller;
    setBusy(true); setError(""); setResult(null);
    try {
      const body = input();
      if (variant && Object.values(variant).some(w => !w.trim() || !Number.isFinite(Number(w)))) throw new Error("Uzupełnij wszystkie wagi wariantu.");
      if (!histories.length || Object.keys(variant ?? {}).some(s => !s.startsWith("CASH:") && !histories.some(h => h.symbol === s))) {
        setNotice("Pobieram ceny i kursy walut dla pozycji zapisanych na tym koncie…");
        body.histories = await fetchHistory(controller);
      }
      const next = await xtbRequest<RiskResult>("risk", body, controller.signal);
      if (!controller.signal.aborted) { latest.current = body; setResult(next); if (target === "comparison" && !variant && next.before) setVariant(copyWeights(next.before.weights)); }
    } catch (reason) { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Nie można obliczyć ryzyka."); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  async function fetchHistory(existingController?: AbortController): Promise<RiskHistory[]> {
    const controller = existingController ?? new AbortController();
    if (!existingController) { pending.current?.abort(); pending.current = controller; setBusy(true); setError(""); setResult(null); }
    try {
      const book = example?.book ?? account.book;
      // Include the quantity snapshot interval when checking for intervening splits.
      const historyStart = [start, book.open_snapshot_at?.slice(0, 10), ...book.records.filter(r => r.kind === "fill").map(r => r.event_at?.slice(0, 10))].filter((day): day is string => Boolean(day)).sort()[0] ?? start;
      const current = await xtbRequest<XtbAnalysis>("analyze", book, controller.signal);
      const symbols = [...new Set([...current.holdings.filter(h => h.asset_type === "equity").map(h => h.symbol), ...Object.keys(variant ?? {}).filter(s => s !== `CASH:${base}`), ...(benchmark ? [benchmark] : []), ...(example?.cash.filter(c => c.currency !== base).map(c => c.symbol) ?? [])])];
      if (!symbols.length) return histories;
      if (symbols.length > 20) throw new Error("Jedno pobranie obsługuje do 20 instrumentów i sald walutowych. Możesz wczytać plik historii.");
      const next = await xtbRequest<{ histories: RiskHistory[]; failures: Record<string, string> }>("risk-history", { symbols, base_currency: base, start: historyStart, end: yesterday() }, controller.signal);
      if (!controller.signal.aborted) {
        const incoming = new Map(next.histories.map(h => [h.symbol, h]));
        const merged = [...histories.filter(h => !incoming.has(h.symbol)), ...next.histories];
        setHistories(merged);
        setNotice(`Pobrano historie: ${next.histories.length}. Poprzednie dane zachowano przy błędach.`);
        if (Object.keys(next.failures).length) setError(`Nie udało się pobrać: ${Object.keys(next.failures).join(", ")}. Sprawdź daty zachowanych danych.`);
        return merged;
      }
      return histories;
    } catch (reason) { if (existingController) throw reason; if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Nie można pobrać historii."); return histories; }
    finally { if (!existingController && !controller.signal.aborted) setBusy(false); }
  }
  async function loadExample() {
    invalidate(); setError(""); setBusy(true);
    const controller = new AbortController(); pending.current = controller;
    try {
      const response = await fetch("/api/v1/xtb/risk-example?asset_scope=equities_only", { signal: controller.signal });
      if (!response.ok) throw new Error("Nie można wczytać przykładu.");
      const data = await response.json() as RiskInput;
      if (controller.signal.aborted) return;
      setExample(data); setBase(data.base_currency); setHistories(data.histories);
      setStart(data.histories[0]?.rows[0]?.date ?? ""); setEnd(data.histories[0]?.rows.at(-1)?.date ?? "");
      setBenchmark(data.benchmark ?? ""); setStressPreset("custom"); setScenarioText(JSON.stringify(data.scenarios, null, 2));
      setVariant(null); setMetadataText(JSON.stringify(data.metadata, null, 2)); setEtfText("[]"); setNotice("Wczytano wyłącznie syntetyczny przykład analizy. Raporty rachunku pozostają zapisane oddzielnie.");
    } catch (reason) { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Błąd przykładu."); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  const before = result?.before;
  const after = result?.after;
  let scenarioNames = "Sprawdź definicję scenariuszy w ustawieniach.";
  try { const parsed: unknown = JSON.parse(scenarioText); if (Array.isArray(parsed)) scenarioNames = parsed.map((s: { name?: string }) => s?.name ?? "Bez nazwy").join("; "); } catch { /* Invalid JSON is reported before calculation. */ }
  const chooseSection = (key: string) => { setSection(key); };
  const resetExample = () => {
    invalidate(); setExample(null); setHistories([]); setVariant(null); setBase(account.book.currency);
    setBenchmark(""); setEnd(yesterday()); setStart(new Date(Date.now() - 3 * 365 * 86400000).toISOString().slice(0, 10));
    setScenarioText(JSON.stringify(initialScenarios, null, 2)); setStressPreset("custom"); setMetadataText("[]"); setEtfText("[]");
  };
  return <div className="qr-workspace" onChange={event => { if ((event.target as HTMLInputElement).type !== "range") invalidate(); }}>
    <header className="qr-workspace-header">
      <div><p className="iv-eyebrow">AKCJE BEZ DŹWIGNI · BADANIE RYZYKA</p><h2>Analiza ryzyka portfela</h2><p>Od ogólnego profilu do pojedynczej spółki. Wspólne dane, jawne założenia.</p></div>
      <div className="qr-header-actions"><button className="iv-button iv-primary" disabled={busy} onClick={() => void analyze()}>{busy ? "Sprawdzam dane…" : result ? "Przelicz analizę" : "Oblicz analizę i scenariusze"}</button>{result && <button className="iv-button" onClick={() => download("quantops-risk-report.json", { inputs: latest.current, result })}>Pobierz raport z danymi i założeniami</button>}</div>
    </header>
    <aside className={"qr-source-strip" + (example ? " qr-source-synthetic" : "")} aria-label="Źródło portfela"><div><span className="qr-source-dot" /><strong>{example ? "Przykład syntetyczny · pięć spółek" : account.label}</strong><small>{example ? "DANE SYNTETYCZNE — przykład badawczy, nie rzeczywisty wynik rachunku." : "Stan pozycji: " + (account.book.open_snapshot_at?.slice(0,10) ?? "z historii transakcji") + " · bez gotówki i pozostałych instrumentów"}</small></div>{example ? <button className="iv-text" disabled={busy} onClick={resetExample}>Wróć do mojego rachunku</button> : <details><summary>Obejrzyj przykład</summary><p>Odrębna, oznaczona analiza demonstracyjna. Zapisany rachunek pozostaje osobno.</p><button className="iv-button" disabled={busy} onClick={() => void loadExample()}>Wczytaj przykład syntetyczny</button></details>}</aside>
    <RiskTabs active={section} onSelect={chooseSection} />
    {error && <p className="iv-alert iv-error" role="alert">{error}</p>}
    {notice && <p className="qr-status" role="status">{notice}</p>}
    {result && Object.keys(result.out_of_scope).length > 0 && <aside className="qr-scope-notice" role="note"><strong>Analiza dotyczy części akcyjnej rachunku.</strong><p>Poza zakresem: {Object.keys(result.out_of_scope).join(", ")}. Ich wartości nie doliczono do kapitału ani wskaźników. Nie jest to ocena całego rachunku.</p></aside>}
    <section id={"risk-panel-" + section} role="tabpanel" aria-labelledby={"risk-tab-" + section} tabIndex={0} className="qr-tab-panel" ref={resultAnchor}>
      {section === "scenarios" && before && result && !busy && latest.current && <MonteCarloPanel portfolio={latest.current} hasVariant={Boolean(after)} />}
      {busy ? <section className="iv-panel qr-loading" role="status"><span className="qr-loading-ring" /><h3>Przygotowuję analizę</h3><p>Sprawdzam pozycje, wspólne daty cen i kursy walut. Następnie obliczam ryzyko.</p></section> : null}
      {!before && !busy && section !== "data" && <section className="iv-panel qr-empty-state"><div className="qr-empty-art" aria-hidden="true"><i /><i /><i /><i /><i /></div><p className="iv-eyebrow">{result ? "POTRZEBNE UZUPEŁNIENIE DANYCH" : "TWÓJ PUNKT WYJŚCIA"}</p><h3>{result ? "Uzupełnij dane, aby otrzymać wynik" : "Poznaj profil swojego portfela"}</h3><p>{result ? "Wynik częściowy — brakuje danych do wyceny zapisanych pozycji." : "Oblicz analizę zapisanych akcji. Zobaczysz indeks ryzyka 0–100, koncentrację, powiązania i scenariusze spadków."}</p><div className="iv-actions"><button className="iv-button iv-primary" onClick={() => void analyze()} disabled={busy}>Analizuj zapisane akcje</button><button className="iv-button" disabled={busy} onClick={() => void loadExample()}>Wczytaj przykład syntetyczny</button></div><small>Wynik 0–100 jest jawną heurystyką ryzyka cenowego, nie gwarancją bezpieczeństwa.</small></section>}
      {result && !before && !busy && <section className="iv-panel"><h3>Co wymaga uzupełnienia?</h3>{result.warnings.includes("valuation_precedes_quantity_snapshot") ? <p className="iv-alert">Zapisane pozycje są na {result.quantity_date ?? account.book.open_snapshot_at?.slice(0,10)}, a ostatnie wspólne ceny i kursy walut na {result.valuation_date}. Potrzebuję cen co najmniej z dnia raportu, aby wycenić ten stan.</p> : null}{Object.entries(result.excluded).map(([symbol,why]) => <p key={symbol}><strong>{symbol}</strong> · {warningDescriptions[why] ?? "Pozycja wymaga sprawdzenia danych lub innego modelu."}</p>)}<p>Pokryta wartość: {money(result.covered_value,base)}. Nie jest to wartość ani miara ryzyka całego portfela.</p><button className="iv-text" onClick={() => setSection("data")}>Sprawdź dane i źródła →</button></section>}
      {before && result && !busy && section === "summary" && <RiskOverview result={result} allocation={before} onSelect={chooseSection} />}
      {before && result && !busy && section === "concentration" && <RiskConcentration key={result.valuation_date + account.id} result={result} allocation={before} />}
      {before && !busy && section === "diversification" && <><RiskDiversification allocation={before} /><details className="iv-panel"><summary>Szczegóły liczbowe — wkład pozycji w ryzyko</summary><ContributionTable allocation={before} currency={base} /></details></>}
      {section === "scenarios" && <><section className="iv-panel"><p className="iv-eyebrow">HIPOTETYCZNE ZAŁOŻENIA</p><h2>Sprawdź możliwe spadki</h2><p>Wybierz szok i przelicz jego wpływ na zapisane akcje. Scenariusze nie mają przypisanych prawdopodobieństw.</p><div className="qr-stress-controls"><label>Wybierz próbny spadek<select disabled={busy} value={stressPreset} onChange={e => { const shock = e.target.value; setStressPreset(shock); if (shock !== "custom") setScenarioText(JSON.stringify([{ name: "Hipotetyczny spadek akcji o " + Number(shock)*100 + "%", position_shocks: {}, class_shocks: { equity: "-" + shock }, fx_shocks: {} }],null,2)); }}><option value="custom">Aktualny zestaw scenariuszy</option><option value="0.1">Akcje spadają o 10%</option><option value="0.2">Akcje spadają o 20%</option><option value="0.35">Akcje spadają o 35%</option></select></label><button className="iv-button iv-primary" disabled={busy} onClick={() => void analyze("scenarios")}>Wykonaj stress test</button></div><p className="iv-note">{scenarioNames}. W gotowych presetach kursy walut są bez zmian.</p>
        <details><summary>Dostosuj stress test — opcjonalnie</summary><div className="iv-form-grid"><label>Tolerancja straty<input type="number" min="0" step="any" value={tolerance} onChange={e => setTolerance(e.target.value)} /></label><label>Jednostka tolerancji<select value={toleranceKind} onChange={e => setToleranceKind(e.target.value)}><option value="percent">% kapitału</option><option value="amount">Kwota w walucie bazowej</option></select></label><label>Szok akcji (%)<input type="number" min="-99" max="500" step="any" value={quickPrice} onChange={e => setQuickPrice(e.target.value)} /></label><label>Waluta szoku FX<select value={quickCurrency} onChange={e => setQuickCurrency(e.target.value)}>{currencies.filter(c => c !== base).map(c => <option key={c}>{c}</option>)}</select></label><label>Szok FX względem {base} (%)<input type="number" min="-99" max="500" step="any" value={quickFx} onChange={e => setQuickFx(e.target.value)} /></label></div><button className="iv-button" onClick={() => { if (!quickPrice.trim() || !quickFx.trim() || !Number.isFinite(Number(quickPrice)) || !Number.isFinite(Number(quickFx)) || quickCurrency === base) { setError("Uzupełnij szoki i wybierz walutę inną niż bazowa."); return; } setStressPreset("custom"); setScenarioText(JSON.stringify([{ name: "Hipotetycznie: akcje " + quickPrice + "%, " + quickCurrency + "/" + base + " " + quickFx + "%", position_shocks: {}, class_shocks: { equity: String(Number(quickPrice)/100) }, fx_shocks: { [quickCurrency]: String(Number(quickFx)/100) } }],null,2)); invalidate(); }}>Zastosuj własny scenariusz</button><details><summary>Zaawansowane: szoki poszczególnych pozycji i wiele scenariuszy</summary><label>Definicje scenariuszy — szoki jako ułamki<textarea rows={8} value={scenarioText} onChange={e => { setStressPreset("custom"); setScenarioText(e.target.value); }} /></label></details><p className="iv-note">Szok pozycji zastępuje szok klasy. Cena i FX mnożą się. Tolerancja odnosi się do końcowej straty w scenariuszu, a nie maksymalnego obsunięcia w jego trakcie.</p></details></section>
        {before && !busy && <><RiskTakeaway allocation={before} currency={base} kind="scenarios" /><ScenarioTable allocation={before} currency={base} /><section className="iv-panel"><h3>Co, jeśli spadnie tylko jedna spółka?</h3><p>Każdy wiersz to osobny spadek danej spółki o 50%. Pozostałe ceny i kursy walut są bez zmian. To nie są prognozy.</p><div className="iv-table-wrap" role="region" aria-label="Spadek pojedynczej spółki" tabIndex={0}><table><thead><tr><th>Spółka</th><th>Strata portfela</th><th>Zmiana portfela</th><th>Pozostała wartość</th></tr></thead><tbody>{before.diagnostics.single_position_stress.map(s => <tr key={s.symbol}><th>{s.symbol}</th><td className="qr-negative">{money(s.pnl,base)}</td><td>{fraction(s.portfolio_fraction)}</td><td>{money(s.value_after,base)}</td></tr>)}</tbody></table></div></section></>}
      </>}
      {before && !busy && section === "history" && <><DrawdownChart allocation={before} /><section className="iv-panel"><RiskTakeaway allocation={before} currency={base} kind="history" /><h2>Obecna alokacja w przeszłości — symulacja</h2><p>Początkowe wagi obecnego składu, potem buy-and-hold bez rebalancingu. Skorygowane ceny z reinwestycją dywidend. Koszty, podatki i inflacja są pominięte.</p><HistoryChart points={before.curve.map(([date,value]) => ({ date,value:Number(value) }))} label="Symulowana wartość obecnej alokacji" unit={base} /><PerformanceDetails value={before.performance} /><h3>Benchmark — identyczny okres i waluta</h3>{result?.benchmark ? <PerformanceDetails value={result.benchmark} /> : <p>Brak pełnych danych benchmarku we wspólnym okresie. Nie skrócono okresu portfela, aby ukryć brak.</p>}<a href="/investor">Faktyczny wynik i TWR z pełnej historii transakcji →</a></section></>}
      {section === "comparison" && <><section className="iv-panel" ref={variantAnchor}><p className="iv-eyebrow">ODRĘBNA KOPIA · TEN SAM KAPITAŁ</p><h2>Co zmieni inny podział pieniędzy?</h2><p>Porównanie nie zmienia zapisanych raportów ani rzeczywistych pozycji. Wagi muszą sumować się dokładnie do 100%.</p>{!variant ? <button className="iv-button iv-primary" disabled={!before || busy} onClick={() => { if (before) { setVariant(copyWeights(before.weights)); invalidate(); } }}>Utwórz kopię alokacji</button> : <><div className="qr-weights">{Object.entries(variant).map(([symbol,weight]) => <label key={symbol}>{symbol + " — udział %"}<input type="number" min="0" max="100" step="any" value={weight} onChange={e => setVariant({ ...variant,[symbol]:e.target.value })} /></label>)}</div><p role="status">Suma wag: {Object.values(variant).reduce((sum,w) => sum + Number(w),0).toFixed(6)}% — wymagana dokładnie 100%.</p><div className="iv-form-grid"><label>Dodaj symbol do wariantu<input value={extra} maxLength={80} onChange={e => setExtra(e.target.value.trim().toUpperCase())} placeholder="np. JNJ.US" /></label><button className="iv-button" onClick={() => { if (extra) { setVariant({ ...variant,[extra]:"0" }); setExtra(""); invalidate(); } }}>Dodaj pozycję do wariantu</button></div><div className="iv-actions"><button className="iv-button iv-primary" disabled={busy} onClick={() => void analyze("comparison")}>Porównaj inny podział</button><button className="iv-button" onClick={() => { setVariant(null); invalidate(); }}>Odrzuć wariant</button></div><p className="iv-note">Początkowe udziały są zaokrąglane do sześciu miejsc procentowych; resztę dostaje największa pozycja. Nowa spółka wymaga historii. Wagi 0% usuwają ekspozycję z wariantu.</p></>}</section>{before && after && !busy && <section className="iv-panel"><RiskTakeaway allocation={after} original={before} currency={base} kind="comparison" /><SignedBars title="Zmienność roczna — przed i po" rows={[{label:"Przed",value:before.risk.annual_volatility,text:pct(before.risk.annual_volatility)},{label:"Po",value:after.risk.annual_volatility,text:pct(after.risk.annual_volatility)}]} /><Comparison before={before} after={after} currency={base} /></section>}</>}
      {section === "data" && <section className="iv-panel"><p className="iv-eyebrow">JAKOŚĆ I ODTWARZALNOŚĆ</p><h2>Dane, metody i ograniczenia</h2>{result && <><div className="qr-metric-grid"><Metric label="Wycena na" value={result.valuation_date ?? "Brak wspólnej daty"} /><Metric label="Wspólne daty historii" value={String(result.history_dates)} /><Metric label="Stopy zwrotu" value={String(result.return_dates)} /><Metric label="Pominięte pary dat" value={String(result.skipped_pairs)} /></div><p>Okres: {result.period_start ?? "—"} — {result.period_end ?? "—"}. Pokrycie dotyczy wyłącznie wybranej części akcyjnej. Gotówka i pozostałe instrumenty rachunku pozostają poza zakresem.</p>{before && <><div className="iv-metrics"><Metric label={"VaR " + Number(confidence)*100 + "% · 1 sesja"} value={before.risk.var_fraction === null ? "Za mało danych" : money(before.var_amount,base)} /><Metric label={"ES " + Number(confidence)*100 + "% · 1 sesja"} value={before.risk.es_fraction === null ? "Za mało danych" : money(before.es_amount,base)} /></div><p className="iv-note">Metoda historyczna, kwantyl liniowy. VaR nie jest maksymalną możliwą stratą. Próba: {before.risk.observations}/{before.risk.required_observations}; ogon ES: {before.risk.tail_count}; status: {before.risk.status}.</p></>}<details><summary>Pokrycie analizy i jakość danych</summary>{result.warnings.map(w => <p key={w}>{warningDescriptions[w] ?? w}</p>)}<p>{result.methodology}</p></details></>}
        <details open={!histories.length}><summary>Ustawienia zaawansowane — okres, waluta i źródła danych</summary><fieldset disabled={busy}><legend>Dane i wspólny okres analizy</legend><button className="iv-button" onClick={() => void fetchHistory()}>Odśwież historie cen i FX</button><div className="iv-form-grid"><label>Waluta bazowa<select value={base} onChange={e => { setBase(e.target.value); setHistories([]); setVariant(null); }}>{currencies.map(c => <option key={c}>{c}</option>)}</select></label><label>Od<input type="date" value={start} max={end} onChange={e => setStart(e.target.value)} /></label><label>Do<input type="date" value={end} max={yesterday()} onChange={e => setEnd(e.target.value)} /></label><label>Benchmark — symbol XTB<input value={benchmark} maxLength={80} placeholder="np. CSPX.UK" onChange={e => setBenchmark(e.target.value.trim().toUpperCase())} /></label><label>Ufność VaR / ES<select value={confidence} onChange={e => setConfidence(e.target.value)}><option value="0.95">95%</option><option value="0.99">99%</option></select></label></div><label>Wczytaj historie JSON<input type="file" accept=".json" onChange={e => { const file = e.target.files?.[0]; if (!file) return; void (async () => { try { if (file.size > 8*1024*1024) throw new Error("Limit pliku: 8 MiB."); const data: unknown = JSON.parse(await file.text()); setHistories(checkedHistories(data)); setNotice("Plik wczytany; API sprawdzi strukturę i spójność przy analizie."); } catch (reason) { setError(reason instanceof Error ? reason.message : "Niepoprawny plik."); } })(); }} /></label></fieldset></details>
        <details><summary>Pochodzenie danych i plik do odtworzenia</summary><button className="iv-button" onClick={() => download("quantops-risk-histories.json",histories)}>Pobierz historie JSON</button><div className="iv-table-wrap" role="region" aria-label="Źródła historii" tabIndex={0}><table><thead><tr><th>Symbol</th><th>Okres</th><th>Źródło</th><th>Pobranie</th><th>Pochodzenie</th></tr></thead><tbody>{histories.map(h => <tr key={h.symbol}><th>{h.symbol}</th><td>{h.rows[0]?.date} — {h.rows.at(-1)?.date}</td><td><a href={h.source_url} target="_blank" rel="noreferrer">{h.source}</a><small className="sq-block">{h.fx_source}</small></td><td>{h.fetched_at}</td><td>{h.origin}</td></tr>)}</tbody></table></div><p>Oznaczenie „provider” w pliku jest deklaracją, nie podpisem źródła. Własne pliki wymagają sprawdzenia.</p></details>
        <details><summary>Udokumentowane dane o emitentach</summary><p>Wymagane są daty i źródła. Brakujące sektory i kraje pozostają oznaczone jako nieznane. Wspólny issuer_id łączy notowania tego samego emitenta.</p><label>Metadane ekspozycji JSON<textarea rows={7} value={metadataText} onChange={e => setMetadataText(e.target.value)} /></label></details><p className="iv-note">Skorygowane ceny służą do stóp zwrotu, surowe do wyceny. Brakujące daty i kursy walut nie są uzupełniane. Historia obecnego składu jest symulacją; rzeczywisty wynik wymaga pełnej historii transakcji.</p>
      </section>}
    </section>
  </div>;
}
function SignedBars({ title, rows }: { title: string; rows: { label: string; value: number | null; text: string }[] }) {
  const maximum = Math.max(...rows.map(row => Math.abs(row.value ?? 0)), 0);
  return <figure className="qr-bars"><figcaption>{title}</figcaption>{rows.map((row, index) => <div className="qr-bar-row" key={index}><div className="qr-bar-caption"><span>{row.label}</span><strong>{row.text}</strong></div><div className="qr-bar-track" aria-hidden="true"><span className="qr-bar-zero" /><span className={row.value !== null && row.value < 0 ? "qr-bar-negative" : "qr-bar-positive"} style={{ width: `${maximum && row.value !== null ? Math.abs(row.value) / maximum * 50 : 0}%`, left: row.value !== null && row.value < 0 ? `${50 - (maximum ? Math.abs(row.value) / maximum * 50 : 0)}%` : "50%" }} /></div></div>)}<p className="iv-note">Linia pośrodku oznacza zero. W lewo: wartości ujemne; w prawo: dodatnie. Długości porównują wartości w obrębie tego wykresu.</p></figure>;
}
function RiskTakeaway({ allocation, original, currency, kind }: { allocation: AllocationResult; original?: AllocationResult; currency: string; kind: string }) {
  const largest = Object.entries(allocation.weights).sort((a, b) => Number(b[1]) - Number(a[1]))[0];
  const driver = Object.entries(allocation.risk.risk_shares).filter((entry): entry is [string, number] => entry[1] !== null).sort((a, b) => b[1] - a[1])[0];
  const worst = allocation.scenarios.filter(s => s.pnl !== null).sort((a, b) => Number(a.pnl) - Number(b.pnl))[0];
  let text = "Brak wystarczających danych do wniosku.";
  if (kind === "summary") text = `${largest?.[0] ?? "—"} stanowi ${fraction(largest?.[1])} wartości portfela. ${driver ? `Największy wkład w historyczne wahania ma ${driver[0]}: ${pct(driver[1])} łącznej zmienności.` : "Za mało danych lub brak wahań, aby wskazać udział w ryzyku."} Liczba pozycji sama nie przesądza o rozproszeniu ryzyka.`;
  if (kind === "scenarios" && worst) text = `${Number(worst.pnl) < 0 ? "Największa strata wśród sprawdzonych scenariuszy" : "Najniższy wynik wśród sprawdzonych scenariuszy"}: ${money(worst.pnl, currency)} (${fraction(worst.fraction)}), w scenariuszu „${worst.name}”. Po nim wartość wyniosłaby ${money(worst.value_after, currency)}. To wynik założeń, nie prognoza ani maksymalna możliwa strata.`;
  if (kind === "history") text = allocation.performance.maximum_drawdown === null ? "Za mało historii do oceny spadku." : `Największy zaobserwowany spadek od wcześniejszego szczytu wyniósł ${pct(Math.abs(allocation.performance.maximum_drawdown))}. ${allocation.performance.maximum_drawdown === 0 ? "W badanym okresie nie zaobserwowano spadku od szczytu." : allocation.performance.recovery ? `Powrót do tego szczytu nastąpił ${allocation.performance.recovery}.` : "Do końca badanego okresu ten spadek nie został odrobiony."} To symulacja dzisiejszego składu, a nie Twój faktyczny wynik inwestycyjny.`;
  if (kind === "comparison" && original) {
    const a = original.risk.annual_volatility; const b = allocation.risk.annual_volatility;
    text = a === null || b === null ? "Za mało danych do porównania zmienności obu podziałów." : `Historyczna zmienność roczna wynosi ${pct(a)} przed zmianą i ${pct(b)} po zmianie. W kopii jest ${b < a ? "niższa" : b > a ? "wyższa" : "taka sama"}. Sprawdź też straty w scenariuszach poniżej: mniejsze wahania nie gwarantują mniejszych strat w każdej sytuacji.`;
  }
  return <aside className="qr-takeaway" aria-label="Wniosek z obliczeń"><h3>Co to oznacza dla Ciebie?</h3><p>{text}</p><small>Wniosek wynika z obliczonych danych i wybranych założeń.</small></aside>;
}
function Metric({ label, value }: { label: string; value: string }) { return <article className="iv-tile"><span>{label}</span><strong>{value}</strong></article>; }
function ContributionTable({ allocation, currency }: { allocation: AllocationResult; currency: string }) {
  return <div className="iv-table-wrap" tabIndex={0} role="region" aria-label="Wkład pozycji w ryzyko"><table><thead><tr><th>Pozycja</th><th>Kwota w walucie bazowej</th><th>Wartość portfela</th><th>Udział w zmienności</th><th>Wkład do zmienności rocznej</th><th>Objaśnienie</th></tr></thead><tbody>{Object.entries(allocation.weights).map(([s, w]) => <tr key={s}><th>{s}</th><td>{money(allocation.position_values[s] ?? null, currency)}</td><td>{fraction(w)}</td><td>{pct(allocation.risk.risk_shares[s] ?? null)}</td><td>{pct(allocation.risk.components[s] ?? null)}</td><td>Ta pozycja odpowiada za {fraction(w)} wartości i {pct(allocation.risk.risk_shares[s] ?? null)} zmienności portfela.{(allocation.risk.risk_shares[s] ?? 0) < 0 ? " Historycznie ograniczała wahania całości." : ""}</td></tr>)}</tbody></table><p className="iv-note">Wkłady są podpisane i sumują się do zmienności portfela. Przy zerowej zmienności udział procentowy jest nieokreślony. Błąd uzgodnienia: {allocation.risk.reconciliation_error ?? "brak danych"}.</p></div>;
}
export function PerformanceDetails({ value }: { value: PerformanceSummary }) {
  return <><div className="iv-metrics"><Metric label="Wynik okresu" value={pct(value.period_return)} /><Metric label="Maksymalne obsunięcie" value={pct(value.maximum_drawdown)} /><Metric label="Bieżące obsunięcie" value={pct(value.current_drawdown)} /><Metric label={`Najgorszy miesiąc · ${value.worst_month ?? "—"}`} value={pct(value.worst_month_return)} /><Metric label={`Najgorszy rok · ${value.worst_year ?? "—"}`} value={pct(value.worst_year_return)} /></div><p>Szczyt {value.peak ?? "—"} → dołek {value.trough ?? "—"}: {value.peak_to_trough_days ?? "—"} dni kalendarzowych. {value.maximum_drawdown === 0 ? "W okresie nie było zaobserwowanego obsunięcia." : value.recovery ? `Odrobienie: ${value.recovery}, ${value.recovery_days} dni od dołka.` : "Strata nieodrobiona w dostarczonej historii."}</p><p className="iv-note">Okresy brzegowe są niepełne: miesiące {value.partial_months.join(", ")}; lata {value.partial_years.join(", ")}. Nie są pełnymi wynikami kalendarzowymi.</p></>;
}
function ScenarioTable({ allocation, currency }: { allocation: AllocationResult; currency: string }) {
  const [chosen, setChosen] = useState(0);
  const scenario = allocation.scenarios[Math.min(chosen, allocation.scenarios.length - 1)];
  return <section className="iv-panel"><h2>Jakie straty pokazują scenariusze?</h2><SignedBars title="Zmiana wartości w scenariuszach" rows={allocation.scenarios.map(s => ({label:s.name,value:s.pnl === null ? null : Number(s.pnl),text:money(s.pnl,currency)}))} /><div className="qr-scenario-select" aria-label="Wybór scenariusza">{allocation.scenarios.map((s,i) => <button key={i} aria-pressed={scenario === s} onClick={() => setChosen(i)}>{s.kind === "historical_current_allocation" ? "Ruchy w badanej historii" : s.name}</button>)}</div>{scenario && <article className="qr-scenario"><h3>{scenario.name}</h3><p>{scenario.kind === "hypothetical" ? "Scenariusz hipotetyczny — bez przypisanego prawdopodobieństwa" : "Historyczne ruchy zastosowane do obecnej alokacji — nie wynik inwestora"}</p><div className="iv-metrics"><Metric label="Zmiana wartości" value={money(scenario.pnl,currency) + " · " + fraction(scenario.fraction)} /><Metric label="Wartość po scenariuszu" value={money(scenario.value_after,currency)} />{scenario.maximum_drawdown !== null && <Metric label="Największe obsunięcie w trakcie" value={pct(scenario.maximum_drawdown)} />}</div>{scenario.exceeds_tolerance !== null && <p className={scenario.exceeds_tolerance ? "iv-alert iv-error" : "iv-note"}>{scenario.exceeds_tolerance ? "Końcowa strata przekracza Twoją tolerancję" : "Końcowy wynik mieści się w Twojej tolerancji straty"}</p>}<SignedBars title={"Wpływ pozycji: " + scenario.name} rows={Object.entries(scenario.impacts).map(([label,value]) => ({label,value:Number(value),text:money(value,currency)}))} /><p>Największe źródła strat: {scenario.largest_losses.join(", ") || "brak strat w końcowym wyniku"}.</p><p className="iv-note">Wynik końcowy i obsunięcie w trakcie to różne miary. Tolerancja dotyczy wyniku końcowego. Szoki nie obejmują kosztów, płynności, podatków ani zmian składu.</p></article>}</section>;
}
function Comparison({ before, after, currency }: { before: AllocationResult; after: AllocationResult; currency: string }) {
  const rows = [
    ["Kapitał", money(before.value, currency), money(after.value, currency)],
    ["Największa pozycja", fraction(before.largest_position), fraction(after.largest_position)],
    ["Top 5", fraction(before.top_five), fraction(after.top_five)],
    ["Zmienność roczna", pct(before.risk.annual_volatility), pct(after.risk.annual_volatility)],
    ...[...new Set([...Object.keys(before.exposures.currency ?? {}), ...Object.keys(after.exposures.currency ?? {})])].map(c => [`Waluta notowania ${c}`, fraction(before.exposures.currency?.[c] ?? "0"), fraction(after.exposures.currency?.[c] ?? "0")]),
    ["VaR — kwota / %", before.risk.var_fraction === null ? "Brak danych" : `${money(before.var_amount, currency)} / ${pct(before.risk.var_fraction)}`, after.risk.var_fraction === null ? "Brak danych" : `${money(after.var_amount, currency)} / ${pct(after.risk.var_fraction)}`],
    ["ES — kwota / %", before.risk.es_fraction === null ? "Brak danych" : `${money(before.es_amount, currency)} / ${pct(before.risk.es_fraction)}`, after.risk.es_fraction === null ? "Brak danych" : `${money(after.es_amount, currency)} / ${pct(after.risk.es_fraction)}`],
    ...before.scenarios.map((s, i) => [s.name, `${money(s.pnl, currency)} / ${fraction(s.fraction)}`, `${money(after.scenarios[i]?.pnl ?? null, currency)} / ${fraction(after.scenarios[i]?.fraction ?? null)}`]),
  ];
  return <div className="iv-table-wrap" tabIndex={0} role="region" aria-label="Porównanie wariantów"><table><thead><tr><th>Miara</th><th>Przed</th><th>Po</th></tr></thead><tbody>{rows.map(([label, a, b]) => <tr key={label}><th>{label}</th><td>{a}</td><td>{b}</td></tr>)}</tbody></table></div>;
}
