import { useEffect, useRef, useState } from "react";

import { AllocationChart, HistoryChart, RiskReturnChart, palette } from "../components/InvestorCharts";
import { CashBudgetPanel } from "../components/CashBudgetPanel";
import { EducationLab } from "../components/EducationLab";
import { ForecastQuiz } from "../components/ForecastQuiz";
import { createDefaultBudget, type CashBudget } from "../lib/cashBudget";
import { validInvestorBudget } from "../lib/investorStorage";
import { actionLabels, downloadInvestor, investorRequest, kindLabels, money, number, pct, transactionsCsv, type Action, type InvestorWorkspace, type Market, type SavedScenario, type Transaction, type TransactionPreview, type WorkspaceResult } from "../data/investorApi";
import "../styles/retail.css";
import "../styles/retail-next.css";
import "../styles/investor.css";

const STORE = "quantops.investor-workspace.v1";
const BUDGET = "quantops.investor-cash.v1";
const LIMITS = "quantops.investor-limits.v1";
const tabs = [
  ["overview", "◫", "Przegląd"], ["holdings", "▤", "Portfel i transakcje"], ["allocation", "◉", "Dywersyfikacja"],
  ["risk", "∿", "Ryzyko i zwrot"], ["scenarios", "↗", "Scenariusze"], ["costs", "◷", "Budżet i koszty"],
  ["learn", "◇", "Nauka"], ["data", "⚙", "Dane i ustawienia"],
] as const;
type Tab = typeof tabs[number][0];
const titles: Record<Tab, [string, string]> = {
  overview: ["Twój portfel. Pełniejszy obraz.", "Zobacz, co posiadasz, skąd bierze się wynik i jak duże bywają wahania."],
  holdings: ["Każda pozycja ma swoją historię.", "Daty, ceny, transakcje i koszty w jednym miejscu."],
  allocation: ["Liczba pozycji to dopiero początek.", "Sprawdź, czy różne instrumenty rzeczywiście rozkładają Twoją ekspozycję."],
  risk: ["Zwrot to tylko połowa historii.", "Wahania, obsunięcia i straty w trudniejszych dniach — opisane prostym językiem."],
  scenarios: ["Co, jeśli rynek się zmieni?", "Zapisuj własne założenia i porównuj wpływ na ten sam portfel."],
  costs: ["Koszty i gotówka pod kontrolą.", "Opłaty z historii są już w wyniku. Budżet służy osobnemu planowaniu płynności."],
  learn: ["Najpierw zrozum. Potem oceniaj.", "Ćwiczenia na danych syntetycznych — bez transakcji i bez obietnic przewagi."],
  data: ["Wiesz, skąd pochodzą liczby.", "Źródła cen, zapis lokalny, kopie danych i jawne założenia modeli."],
};
const warningCopy: Record<string, string> = {
  negative_cash_unmodelled_financing: "Saldo gotówki jest ujemne. Wpisz koszty finansowania; nie są naliczane automatycznie.",
  cash_below_margin_assumption: "Gotówka nie pokrywa przyjętej rezerwy depozytowej. Rzeczywisty broker może wymagać innych dopłat.",
  only_common_dates_no_fill: "Historia korzysta ze wspólnych dat notowań i FX. Luki nie są uzupełniane.",
};

function currentTab(): Tab { const key = window.location.hash.slice(1); return tabs.find(([id]) => id === key)?.[0] ?? "overview"; }
function Tile({ title, value, note, featured = false }: { title: string; value: string; note: string; featured?: boolean }) {
  return <article className={`iv-tile ${featured ? "iv-featured" : ""}`}><span>{title}</span><strong>{value}</strong><small>{note}</small></article>;
}
function Panel({ title, eyebrow, children, className = "" }: { title: string; eyebrow?: string; children: React.ReactNode; className?: string }) {
  return <section className={`iv-panel ${className}`}>{eyebrow ? <p className="iv-eyebrow">{eyebrow}</p> : null}<h2>{title}</h2>{children}</section>;
}

export function InvestorPage() {
  const [tab, setTab] = useState<Tab>(currentTab);
  const [book, setBook] = useState<InvestorWorkspace | null>(null);
  const [output, setOutput] = useState<WorkspaceResult | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saved, setSaved] = useState("");
  const [curveMode, setCurveMode] = useState<"profit" | "equity" | "twr">("profit");
  const [selected, setSelected] = useState<string | null>(null);
  const [csv, setCsv] = useState("");
  const [preview, setPreview] = useState<TransactionPreview | null>(null);
  const [backup, setBackup] = useState<{ workspace: InvestorWorkspace; budget: CashBudget; concentration_limit: string } | null>(null);
  const [importMode, setImportMode] = useState<"append" | "replace">("append");
  const [limit, setLimit] = useState("40");
  const [budget, setBudget] = useState<CashBudget>(() => createDefaultBudget("PLN"));
  const [budgetNotice, setBudgetNotice] = useState("");
  const [form, setForm] = useState({ action: "buy" as Action, symbol: "AAPL", date: "2025-04-01", quantity: "1", price: "", amount_pln: "", fee_pln: "0" });
  const [scenario, setScenario] = useState({ name: "Mój scenariusz", price: "-15", fx: "10", oil: "-25", forex: "-5" });
  const [scenarioEdit, setScenarioEdit] = useState<string | null>(null);
  const latest = useRef(0);
  const initialized = useRef(false);
  const importing = useRef(0);
  const deleting = useRef(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  useEffect(() => {
    document.documentElement.lang = "pl"; document.title = "QuantOps — portfel, wynik i ryzyko";
    const change = () => { setTab(currentTab()); window.scrollTo({ top: 0 }); };
    window.addEventListener("hashchange", change);
    if (!initialized.current) {
      initialized.current = true;
      void (async () => {
        try {
          const stored = localStorage.getItem(STORE);
          const input = stored ? JSON.parse(stored) as InvestorWorkspace : await investorRequest<InvestorWorkspace>("demo");
          await apply(input, stored ? "Przywrócono zapisany portfel." : "Wczytano fikcyjne transakcje na rzeczywistych cenach.");
          const storedLimit = localStorage.getItem(LIMITS);
          if (storedLimit && Number.isFinite(Number(storedLimit)) && Number(storedLimit) >= 0 && Number(storedLimit) <= 100) setLimit(storedLimit);
          const storedBudget = localStorage.getItem(BUDGET);
          if (storedBudget) {
            const candidate: unknown = JSON.parse(storedBudget);
            if (validInvestorBudget(candidate)) setBudget(candidate);
          }
        } catch (err: unknown) { setError(err instanceof Error ? err.message : "Nie można odczytać zapisu. Nie nadpisaliśmy go."); setBusy(false); }
      })();
    }
    return () => window.removeEventListener("hashchange", change);
  }, []);

  async function apply(next: InvestorWorkspace, message = "Zapisano i przeliczono."): Promise<boolean> {
    const request = ++latest.current;
    setBusy(true); setError(""); setOutput(null);
    try {
      const result = await investorRequest<WorkspaceResult>("analyze", next);
      if (request !== latest.current) return false;
      setBook(next); setOutput(result); setNotice(message);
      if (!deleting.current) {
        try { localStorage.setItem(STORE, JSON.stringify(next)); setSaved(new Date().toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" })); }
        catch { setSaved(""); setError("Obliczenia są gotowe, ale przeglądarka nie zapisała danych. Pobierz kopię JSON."); }
      }
      return true;
    } catch (err: unknown) { if (request === latest.current) setError(err instanceof Error ? err.message : "Błąd obliczeń."); return false; }
    finally { if (request === latest.current) setBusy(false); }
  }

  async function refresh() {
    if (!book) return;
    setBusy(true); setError("");
    try {
      const market = await investorRequest<Market>("refresh", {});
      await apply({ ...book, market }, `Pobrano ceny. Wspólna data wyceny: ${market.as_of}.`);
    } catch (err: unknown) { setError(err instanceof Error ? err.message : "Brak dostępu do dostawcy. Zachowano poprzednie ceny."); setBusy(false); }
  }
  async function demo() { setBusy(true); try { await apply(await investorRequest<InvestorWorkspace>("demo")); } catch (err: unknown) { setError(err instanceof Error ? err.message : "Brak danych demo."); setBusy(false); } }
  async function inspectCsv() {
    const token = ++importing.current; setError(""); setPreview(null);
    try { const result = await investorRequest<TransactionPreview>("csv-preview", { text: csv }); if (token === importing.current) setPreview(result); }
    catch (err: unknown) { if (token === importing.current) setError(err instanceof Error ? err.message : "Błąd CSV."); }
  }
  async function readBackup(file: File) {
    setBackup(null);
    if (file.size > 3000000) { setError("Kopia może mieć najwyżej 3 MB."); return; }
    try {
      const candidate = JSON.parse(await file.text()) as { workspace?: InvestorWorkspace; budget?: unknown; concentration_limit?: unknown };
      if (!candidate.workspace || !validInvestorBudget(candidate.budget) || typeof candidate.concentration_limit !== "string" || candidate.concentration_limit.trim() === "" || !Number.isFinite(Number(candidate.concentration_limit)) || Number(candidate.concentration_limit) < 0 || Number(candidate.concentration_limit) > 100) throw new Error("Nieprawidłowa kopia danych.");
      setBackup({ workspace: candidate.workspace, budget: candidate.budget, concentration_limit: candidate.concentration_limit });
    } catch { setError("Nieprawidłowa kopia JSON. Dotychczasowy zapis pozostał bez zmian."); }
  }
  async function restoreBackup() {
    if (!backup) return;
    if (await apply(backup.workspace, "Przywrócono portfel, ceny i scenariusze z kopii.")) {
      setBudget(backup.budget); setLimit(backup.concentration_limit);
      try { localStorage.setItem(BUDGET, JSON.stringify(backup.budget)); localStorage.setItem(LIMITS, backup.concentration_limit); setBackup(null); }
      catch { setError("Portfel przywrócono, ale nie udało się zapisać budżetu lub limitu."); }
    }
  }
  async function removeData() {
    if (!book) return;
    deleting.current = true;
    const next = { ...book, name: "Mój portfel", transactions: [], scenarios: [] };
    const ok = await apply(next, "Usunięto dane tego centrum portfela, budżet i limity z przeglądarki.");
    if (ok) {
      try { for (const key of [STORE, BUDGET, LIMITS]) localStorage.removeItem(key); }
      catch { setError("Przeglądarka zablokowała usuwanie zapisu. Usuń dane tej witryny w ustawieniach przeglądarki."); setNotice(""); }
      setBudget(createDefaultBudget("PLN")); setLimit("40"); setSaved(""); setCsv(""); setPreview(null); setBackup(null); setSelected(null); setDeleteConfirm(false);
    }
    deleting.current = false;
  }
  function navigate(value: Tab) { window.location.hash = value; setTab(value); }
  const result = output?.result;
  const detail = result?.positions.find((p) => p.symbol === selected);
  const firstDate = book?.market.series["AAPL"]?.rows[0]?.date;
  const isTrade = form.action === "buy" || form.action === "sell";
  const curve = result?.curve.flatMap((p) => curveMode === "twr" ? p.return_index === null ? [] : [{ date: p.day, value: (p.return_index - 1) * 100 }] : [{ date: p.day, value: Number(p[curveMode]) }]) ?? [];
  const marketOrigin = output?.price_provenance === "provider_snapshot" ? "Zweryfikowana migawka Yahoo Finance" : "Dane z kopii użytkownika · pochodzenie niezweryfikowane";
  const tradeOrigin = output?.transaction_provenance === "synthetic" ? "Fikcyjne transakcje" : output?.transaction_provenance === "mixed" ? "Transakcje mieszane · zawierają fikcyjne" : "Transakcje wpisane przez użytkownika";
  const reading = result ? <HistoryChart points={curve} label={curveMode === "profit" ? "Wynik po wpłatach i wypłatach" : curveMode === "equity" ? "Wartość portfela" : "Stopa zwrotu TWR"} unit={curveMode === "twr" ? "%" : "PLN"} /> : null;

  return <div className="iv-app">
    <a className="iv-skip" href="#investor-main">Przejdź do treści</a>
    <aside className="iv-sidebar"><a href="/" className="iv-brand"><b>Q</b><span>QuantOps<small>TWÓJ PORTFEL. TWOJA PERSPEKTYWA.</small></span></a><p className="iv-nav-label">PRZESTRZEŃ INWESTORA</p><nav aria-label="Centrum portfela">{tabs.map(([key, icon, label]) => <a key={key} href={`#${key}`} aria-current={tab === key ? "page" : undefined}><span aria-hidden="true">{icon}</span>{label}</a>)}</nav><div className="iv-sidebar-foot"><span className="iv-status-dot" /> Zapis na tym urządzeniu<p>Twoje transakcje zostają w tej przeglądarce. Obliczenia wykonuje lokalne API.</p><a href="/personal">Zaawansowana analiza FX →</a><a href="/research">Środowisko badawcze →</a></div></aside>
    <div className="iv-content"><header className="iv-topbar"><span>Moja przestrzeń <b>/</b> {tabs.find(([key]) => key === tab)?.[2]}</span><span>{busy ? "Obliczanie…" : saved ? `Zapis lokalny · ${saved}` : "Brak zapisu"}</span></header>
      <main id="investor-main" tabIndex={-1}>
        <div className="iv-page-title"><div><p className="iv-eyebrow">MNIEJ ZGADYWANIA. WIĘCEJ ZROZUMIENIA.</p><h1>{titles[tab][0]}</h1><p>{titles[tab][1]}</p></div><button disabled={!book || !output || busy} className="iv-button" onClick={() => downloadInvestor("QuantOps-raport.json", JSON.stringify({ workspace: book, analysis: output, exported_at: new Date().toISOString() }, null, 2))}>↓ Raport z danymi</button></div>
        {error ? <div className="iv-alert iv-error" role="alert">{error}{book ? <button className="iv-text" disabled={busy} onClick={() => void apply(book)}>Przelicz zapisany stan</button> : <button className="iv-text" onClick={() => void demo()}>Wczytaj demo zamiast zapisu</button>}</div> : null}
        {notice ? <p className="iv-notice" role="status">{notice}</p> : null}
        {book ? <div className="iv-provenance"><span><i /> <strong>{tradeOrigin}</strong> · rzeczywiste instrumenty</span><span>Ceny do <strong>{book.market.as_of}</strong> · {book.market.provider} · nie na żywo</span><button className="iv-text" onClick={() => navigate("data")}>Źródła i daty ↗</button></div> : <div className="iv-panel"><p>{busy ? "Wczytywanie portfela i cen…" : "Brak dostępnego portfela."}</p></div>}
        {busy && book ? <p className="iv-notice" role="status">Sprawdzam dane i przeliczam wyniki. Poprzednie wartości są ukryte do zakończenia.</p> : null}

        {result && (tab === "overview" || tab === "risk") ? <div className="iv-metrics" aria-label="Wynik i ryzyko portfela">
          <Tile title="Wartość portfela" value={money(result.equity)} note="Gotówka + aktywa + wynik instrumentów pochodnych" featured />
          <Tile title="Wynik po kosztach" value={money(result.profit)} note={`Wpłaty netto ${money(result.net_deposits)} · uwzględnione wpisane opłaty`} />
          <Tile title="Stopa zwrotu TWR" value={pct(result.twr)} note="Zmiana wartości po oddzieleniu wpłat i wypłat" />
          <Tile title="Największe obsunięcie" value={pct(result.max_drawdown)} note="Największy spadek indeksu TWR od szczytu" />
        </div> : null}

        {tab === "overview" && result ? <>
          <div className="iv-grid iv-main-grid"><Panel title="Jak zmieniał się Twój portfel?" eyebrow="WYNIK Z UWZGLĘDNIENIEM HISTORII">
            <div className="iv-segment" aria-label="Rodzaj wykresu">{([['profit','Wynik w PLN'],['equity','Wartość'],['twr','Zwrot TWR']] as const).map(([key,label]) => <button key={key} aria-pressed={curveMode === key} onClick={() => setCurveMode(key)}>{label}</button>)}</div>{reading}<p className="iv-note">Daty i ilości transakcji w przykładzie są fikcyjne. Ceny są historycznymi notowaniami. Dywidendy i koszty wpływają na wynik wyłącznie, gdy wpiszesz je do historii.</p>
          </Panel><Panel title="Co faktycznie posiadasz?" eyebrow="ROZKŁAD EKSPOZYCJI"><AllocationChart positions={result.positions} /><p className="iv-note">Udziały nominałów brutto. Gotówka jest pokazana osobno; nominał futures nie jest wartością majątku.</p><button className="iv-text" onClick={() => navigate("allocation")}>Zobacz dywersyfikację →</button></Panel></div>
          <div className="iv-grid iv-thirds"><Panel title="Koncentracja" eyebrow="01 · ROZŁOŻENIE RYZYKA"><strong className="iv-big">{pct(result.top_weight)}</strong><p>Największa pozycja w ekspozycji brutto. Twój próg: {limit}%.</p><span className={`iv-pill ${result.top_weight !== null && result.top_weight > Number(limit) / 100 ? "iv-amber" : ""}`}>{result.top_weight !== null && result.top_weight > Number(limit) / 100 ? "Powyżej własnego limitu" : "W granicach własnego limitu"}</span></Panel><Panel title="Ekspozycja a kapitał" eyebrow="02 · DŹWIGNIA"><strong className="iv-big">{result.leverage === null ? "—" : `${number(result.leverage)}×`}</strong><p>Nominały brutto {money(result.gross_exposure)} wobec wartości portfela. Futures i forex zwiększają ekspozycję.</p><button className="iv-text" onClick={() => navigate("risk")}>Zrozum wpływ na ryzyko →</button></Panel><Panel title="Bufor gotówki" eyebrow="03 · PŁYNNOŚĆ"><strong className="iv-big">{money(result.cash_after_margin)}</strong><p>Gotówka po rezerwie depozytowej {money(result.margin_estimate)} według przyjętych założeń.</p><span className="iv-pill">Depozyt modelowy, nie wymaganie brokera</span></Panel></div>
          <Panel title="Pozycje w skrócie"><div className="iv-position-cards">{result.positions.map((p, i) => <button key={p.symbol} className="iv-position-card" onClick={() => { setSelected(p.symbol); navigate("holdings"); }}><span className="iv-ticker" style={{ color: palette[i % palette.length] }}>{p.symbol.replace(".NYM", "").replace("=X", "")}</span><strong>{p.name}</strong><small>Od {p.opened} · {p.holding_days} dni</small><span>{money(p.unrealized_pnl)}<small>Niezrealizowany wynik</small></span></button>)}</div></Panel>
        </> : null}

        {tab === "holdings" && book ? <>
          <Panel title="Twoje pozycje" eyebrow="WALUTA BAZOWA · PLN"><p className="iv-note">Kliknij nazwę, aby zobaczyć szczegóły. Dla akcji/ETF wartość to cena × ilość; dla futures/forex wartość to niezrealizowany wynik modelu.</p>
            <div className="iv-table-wrap" role="region" aria-label="Pozycje portfela" tabIndex={0}><table><thead><tr><th>Instrument</th><th>Od kiedy</th><th>Ilość</th><th>Cena średnia / teraz USD</th><th>Wartość w PLN</th><th>Wynik niezrealizowany</th></tr></thead><tbody>{result?.positions.map((p) => <tr key={p.symbol}><th><button className="iv-text" onClick={() => setSelected(p.symbol)}>{p.name}</button><small>{kindLabels[p.kind]} · {p.symbol}</small></th><td>{p.opened}<small>{p.holding_days} dni</small></td><td>{number(p.quantity)}<small>{p.kind === "future" ? "kontraktów × 1000 baryłek" : p.kind === "forex" ? "EUR nominału" : "sztuk"}</small></td><td>{number(p.average_price, 4)} / {number(p.price, 4)}</td><td>{money(p.value)}</td><td>{money(p.unrealized_pnl)}</td></tr>)}</tbody></table></div>
            {result?.positions.length === 0 ? <p className="iv-empty">Portfel jest pusty. Zacznij od wpłaty i transakcji poniżej.</p> : null}
          </Panel>
          {detail ? <Panel title={detail.name} eyebrow="SZCZEGÓŁY INSTRUMENTU"><div className="iv-detail-metrics"><Tile title="Od otwarcia obecnej pozycji" value={`${detail.holding_days} dni`} note={detail.opened} /><Tile title="Nominał brutto" value={money(detail.notional)} note="Nie jest saldem kapitału" /><Tile title="Rezerwa depozytowa" value={money(detail.margin)} note={detail.kind === "future" ? `Model 10% nominału · wygaśnięcie ${detail.expiry}` : detail.kind === "forex" ? "Model 5% nominału · bez swapu" : "Zakup gotówkowy, bez dźwigni"} /></div><HistoryChart points={(book.market.series[detail.symbol]?.rows ?? []).filter((p) => p.date >= detail.opened && p.date <= book.market.as_of).map((p) => ({ date: p.date, value: Number(p.close) }))} label={`Notowanie ${detail.name} od otwarcia`} unit="USD" /><p className="iv-note">Cena niekorygowana o dywidendy. WTI CL jest kontraktem fizycznie rozliczanym; ten panel pokazuje model wyceny przed zamknięciem, nie obsługuje dostawy ani rolowania. Forex to model ekspozycji, nie połączenie z rachunkiem.</p></Panel> : null}
          <Panel title="Dodaj wpis do historii" eyebrow="TRANSAKCJE, PRZEPŁYWY I KOSZTY"><form className="iv-form-grid" onSubmit={(e) => { e.preventDefault(); const row: Transaction = { id: crypto.randomUUID(), action: form.action, date: form.date, symbol: isTrade || form.action === "dividend" ? form.symbol : "", quantity: isTrade ? form.quantity : "0", price: isTrade ? form.price : "0", amount_pln: isTrade ? "0" : form.amount_pln, fee_pln: form.fee_pln, source: "user" }; void apply({ ...book, transactions: [...book.transactions, row] }); }}>
            <label>Rodzaj wpisu<select value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value as Action })}>{Object.entries(actionLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
            <label>Data wpisu<input required type="date" min={firstDate} max={book.market.as_of} value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /></label>
            {isTrade || form.action === "dividend" ? <label>Instrument<select value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })}>{book.market.catalog.map((i) => <option key={i.symbol} value={i.symbol}>{i.name}</option>)}</select></label> : null}
            {isTrade ? <><label>Ilość / nominał<input required type="number" min="0.000001" step={form.symbol === "CLZ26.NYM" ? "1" : "any"} value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></label><label>Cena wykonania (USD)<input required type="number" step="any" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} /></label><button type="button" className="iv-button" onClick={() => { const close = book.market.series[form.symbol]?.rows.find((r) => r.date === form.date)?.close; if (close) setForm({ ...form, price: close }); else setError("Brak ceny dla wybranej daty. Wybierz sesję notowań."); }}>Użyj ceny z tej daty</button></> : <label>Kwota przepływu (PLN)<input required type="number" min="0.01" step="0.01" value={form.amount_pln} onChange={(e) => setForm({ ...form, amount_pln: e.target.value })} /></label>}
            <label>Prowizja / opłata dodatkowa (PLN)<input required type="number" min="0" step="0.01" value={form.fee_pln} onChange={(e) => setForm({ ...form, fee_pln: e.target.value })} /></label><button disabled={busy || book.transactions.length >= 2000} className="iv-button iv-primary">Dodaj i przelicz</button>
          </form><p className="iv-note">Ceny wykonania i kwoty wpisujesz samodzielnie. Referencyjny kurs USD/PLN pochodzi z dnia wpisu; rzeczywiste koszty przewalutowania dodaj jako opłatę. Nowy wpis jest deklaracją użytkownika, nie potwierdzeniem transakcji od brokera.</p></Panel>
          <Panel title={`Historia · ${book.transactions.length} wpisów`}><div className="iv-actions"><button className="iv-button" onClick={() => downloadInvestor("QuantOps-transakcje.csv", transactionsCsv(book.transactions), "text/csv;charset=utf-8")}>Eksport CSV</button><span>Zakupy, sprzedaż, przepływy, prowizje i dywidendy.</span></div><div className="iv-table-wrap" role="region" aria-label="Historia transakcji" tabIndex={0}><table><thead><tr><th>Data</th><th>Zdarzenie</th><th>Symbol</th><th>Ilość / cena USD</th><th>Przepływ / koszt PLN</th><th>Pochodzenie</th><th>Akcja</th></tr></thead><tbody>{book.transactions.map((t) => <tr key={t.id}><td>{t.date}</td><td>{actionLabels[t.action]}</td><td>{t.symbol || "—"}</td><td>{number(t.quantity)} / {number(t.price, 4)}</td><td>{money(t.amount_pln)} / {money(t.fee_pln)}</td><td>{t.source === "synthetic" ? "Fikcyjny" : "Użytkownik"}</td><td><button className="iv-text" disabled={busy} aria-label={`Usuń wpis ${t.symbol || t.action} ${t.date}`} onClick={() => void apply({ ...book, transactions: book.transactions.filter((row) => row.id !== t.id) })}>Usuń</button></td></tr>)}</tbody></table></div></Panel>
          <Panel title="Import transakcji CSV z podglądem"><p className="iv-note">Kolumny: id,date,action,symbol,quantity,price,amount_pln,fee_pln,source. Eksport powyżej jest gotowym wzorem. Identyfikator UUID chroni przed powtórnym dodaniem tego samego wpisu.</p><label className="iv-label">Plik transakcji<input type="file" accept=".csv,text/csv" onChange={(e) => { const file = e.target.files?.[0]; if (!file) return; if (file.size > 600000) { setError("Maksymalny rozmiar CSV: 600 kB."); return; } importing.current++; setPreview(null); void file.text().then(setCsv).catch(() => setError("Nie można odczytać pliku.")); }} /></label><label className="iv-label">Treść transakcji CSV<textarea rows={5} value={csv} onChange={(e) => { importing.current++; setPreview(null); setCsv(e.target.value); }} /></label><button className="iv-button" disabled={!csv || busy} onClick={() => void inspectCsv()}>Sprawdź import</button>
            {preview ? <div className="iv-preview"><strong>Podgląd: {preview.rows.length} wpisów</strong><ul>{preview.errors.map((issue, i) => <li key={i}>Wiersz {issue.row}: {issue.message}</li>)}</ul><p>{preview.rows.slice(0, 5).map((row) => `${row.date} · ${row.symbol || row.action} · ${row.source}`).join(" / ")}</p><label>Sposób importu<select value={importMode} onChange={(e) => setImportMode(e.target.value as "append" | "replace")}><option value="append">Dodaj do historii</option><option value="replace">Zastąp historię po zatwierdzeniu</option></select></label><button className="iv-button iv-primary" disabled={!preview.importable || busy} onClick={() => { void apply({ ...book, transactions: importMode === "append" ? [...book.transactions, ...preview.rows] : preview.rows }).then((ok) => { if (ok) setPreview(null); }); }}>Zatwierdź import transakcji</button></div> : null}
          </Panel>
        </> : null}

        {tab === "allocation" && result ? <>
          <div className="iv-grid"><Panel title="Udziały nominalnej ekspozycji" eyebrow="INSTRUMENTY"><AllocationChart positions={result.positions} /><p className="iv-note">Wagi to bezwzględny nominał / suma nominałów brutto. Nie pokazują udziału w kapitale ani gotówki; pozycje short nie znoszą tu long.</p></Panel><Panel title="Czy jest równomiernie?" eyebrow="KONCENTRACJA"><strong className="iv-big">{result.effective_positions === null ? "—" : number(result.effective_positions)}</strong><p>Efektywna liczba równych pozycji. Sześć instrumentów z jedną dominującą pozycją może przypominać tylko dwie równoważne ekspozycje.</p><p>Największy udział: <strong>{pct(result.top_weight)}</strong>. Liczba instrumentów: <strong>{result.positions.length}</strong>.</p><details><summary>Jak to liczymy?</summary><p>HHI = suma kwadratów wag nominalnych. Efektywna liczba = 1 / HHI. Ta miara nie uwzględnia korelacji ani ryzyka emitenta.</p></details></Panel></div>
          <Panel title="Ekspozycja według grup" eyebrow="ZOBACZ, CO SIĘ NAKŁADA"><div className="iv-bars">{Array.from(new Set(result.positions.map((p) => p.sector))).map((sector, i) => { const weight = result.positions.filter((p) => p.sector === sector).reduce((sum, p) => sum + p.weight, 0); return <div key={sector}><span>{sector}<b>{pct(weight)}</b></span><div><i style={{ width: `${weight * 100}%`, background: palette[i % palette.length] }} /></div></div>; })}</div><p className="iv-explanation">Apple i Microsoft należą do technologii, a ETF SPY również może zawierać te spółki. Nie mamy tutaj aktualnego składu ETF — grupy nie udają pełnej analizy udziałów pośrednich. Wszystkie pokazane instrumenty mają notowanie USD; EUR/USD dodaje ekspozycję na euro, nie zwykły zakup akcji w dolarze.</p></Panel>
          <Panel title="Które ceny poruszały się razem?" eyebrow="KORELACJA HISTORYCZNA"><p>Blisko +1: podobny kierunek zmian. Blisko 0: słaby związek liniowy. Blisko −1: często przeciwne kierunki. Zależności mogą się zmienić.</p><div className="iv-table-wrap" role="region" aria-label="Macierz korelacji" tabIndex={0}><table className="iv-correlation"><thead><tr><th>Instrument</th>{result.correlation_symbols.map((s) => <th key={s}>{s.replace(".NYM", "").replace("=X", "")}</th>)}</tr></thead><tbody>{result.correlations.map((row, index) => <tr key={index}><th>{result.correlation_symbols[index]}</th>{row.map((value, column) => <td key={column} style={{ background: value === null ? "#f5f5f0" : value >= .6 ? "#cee3d3" : value < 0 ? "#e7e1f0" : "#eef3ea" }}>{value === null ? "Brak" : number(value)}</td>)}</tr>)}</tbody></table></div><p className="iv-note">Wspólne daty. Akcje i ETF: zmiany wartości ceny w PLN. Forex i futures: zmiany notowania w USD. To korelacja cen, a nie korelacja samych nominałów ani gwarancja zabezpieczenia.</p></Panel>
        </> : null}

        {tab === "risk" && result ? <>
          <div className="iv-grid iv-main-grid"><Panel title="Mapa zwrotu i wahań" eyebrow="HISTORYCZNY ZWROT ≠ PRZYSZŁY ZYSK"><RiskReturnChart points={result.market_points} /><p className="iv-note">Wspólny okres do {result.as_of}, maksymalnie 252 zwroty. Zmienność = odchylenie standardowe dziennych zmian × √252. Nie jest to granica efektywna ani propozycja optymalnego portfela.</p></Panel><Panel title="Ile wynosiłaby trudniejsza sesja?" eyebrow="DZISIEJSZE POZYCJE · DAWNE ZMIANY CEN"><div className="iv-risk-number"><span>VaR 95% · jedna obserwacja</span><strong>{money(result.var95)}</strong><p>Próg straty przekraczany w około 5% zmian z tej próby. Nie oznacza maksymalnej straty.</p></div><div className="iv-risk-number"><span>ES 95% · średnio poza progiem</span><strong>{money(result.es95)}</strong><p>Średnia strata w historycznym ogonie. Rzeczywiste straty mogą być większe.</p></div><span className="iv-pill">{result.observations} obserwacji · {result.risk_status === "ok" ? "obliczono" : "brak wystarczających danych lub dodatniego kapitału"}</span></Panel></div>
          <div className="iv-grid"><Panel title="Spadki od poprzedniego szczytu" eyebrow="OBSUNIĘCIE WYNIKU TWR"><HistoryChart points={result.curve.flatMap((p) => p.drawdown === null ? [] : [{ date: p.day, value: p.drawdown * 100 }])} label="Obsunięcie indeksu wyniku" unit="%" /><p className="iv-note">Wpłaty nie tworzą pozornego nowego zysku. Krzywa dotyczy wpisanej historii i kosztów.</p></Panel><Panel title="Co najbardziej napędzało wahania?" eyebrow="WKŁAD DO WARIANCJI"><div className="iv-risk-contributions">{result.market_points.map((p, i) => <div key={p.symbol}><span>{p.symbol.replace(".NYM", "").replace("=X", "")}<b>{pct(p.risk_contribution)}</b></span><div><i style={{ width: `${Math.min(100, Math.abs(p.risk_contribution ?? 0) * 100)}%`, background: palette[i % palette.length] }} /></div>{(p.risk_contribution ?? 0) < 0 ? <small>Historycznie zmniejszała wariancję całości.</small> : null}</div>)}</div><details><summary>Co oznacza wkład do ryzyka?</summary><p>Kowariancja dziennego wyniku pozycji z wynikiem całego portfela / wariancja portfela. Wkłady mogą być ujemne lub przekraczać 100%; nie są prawdopodobieństwami straty. Przy zerowej wariancji wynik jest niedostępny.</p></details></Panel></div>
          <Panel title="Bez jednej mylącej oceny bezpieczeństwa"><div className="iv-detail-metrics"><Tile title="Zmienność modelu obecnych pozycji" value={pct(result.annual_volatility)} note="Roczna skala √252, minimum 252 obserwacje" /><Tile title="Nominał / kapitał" value={result.leverage === null ? "—" : `${number(result.leverage)}×`} note="Im większa ekspozycja, tym większa wrażliwość" /><Tile title="Gotówka po rezerwie" value={money(result.cash_after_margin)} note="Rezerwa według założonej stopy depozytu" /></div><p className="iv-note">Ryzyko kredytowe, płynność rynku, poślizg, finansowanie, dostawa fizyczna i zmiany depozytu nie mieszczą się w jednej liczbie. VaR/ES używają historycznych zmian przy stałych obecnych ilościach; nie są prognozą.</p></Panel>
        </> : null}

        {tab === "scenarios" && book ? <>
          <Panel title={scenarioEdit ? "Zmień zapisany scenariusz" : "Zapisz własny scenariusz"} eyebrow="JAWNE ZAŁOŻENIA · BEZ PRAWDOPODOBIEŃSTWA"><form className="iv-form-grid" onSubmit={(e) => { e.preventDefault(); const next: SavedScenario = { id: scenarioEdit ?? crypto.randomUUID(), name: scenario.name, price_shock: String(Number(scenario.price) / 100), fx_shock: String(Number(scenario.fx) / 100), oil_shock: String(Number(scenario.oil) / 100), forex_shock: String(Number(scenario.forex) / 100) }; void apply({ ...book, scenarios: scenarioEdit ? book.scenarios.map((s) => s.id === scenarioEdit ? next : s) : [...book.scenarios, next] }).then((ok) => { if (ok) setScenarioEdit(null); }); }}><label>Nazwa scenariusza<input required maxLength={80} value={scenario.name} onChange={(e) => setScenario({ ...scenario, name: e.target.value })} /></label>{([['price','Akcje i ETF (%)'],['fx','USD/PLN (%)'],['oil','Ropa CLZ26 (%)'],['forex','EUR/USD (%)']] as const).map(([key,label]) => <label key={key}>{label}<input required type="number" step="any" min="-99.9" max="500" value={scenario[key]} onChange={(e) => setScenario({ ...scenario, [key]: e.target.value })} /></label>)}<button className="iv-button iv-primary" disabled={busy || (!scenarioEdit && book.scenarios.length >= 20)}>Zapisz scenariusz</button></form><p className="iv-note">Zmiana cen i USD/PLN jest liczona łącznie. Gotówka PLN nie podlega szokowi. Bez transakcji, rolowania, wymuszonego zamknięcia ani zmiany depozytu.</p></Panel>
          <div className="iv-grid">{output?.scenarios.map(({ scenario: s, result: r }) => <Panel key={s.id} title={s.name} eyebrow="PORÓWNANIE W TEJ SAMEJ WYCENIE"><strong className="iv-big">{money(r.pnl)}</strong><p>Wartość po scenariuszu: <strong>{money(r.equity_after)}</strong></p><div className="iv-chips"><span>Akcje/ETF {pct(Number(s.price_shock))}</span><span>USD/PLN {pct(Number(s.fx_shock))}</span><span>Ropa {pct(Number(s.oil_shock))}</span><span>EUR/USD {pct(Number(s.forex_shock))}</span></div><ul className="iv-impact-list">{Object.entries(r.impacts).map(([symbol, amount]) => <li key={symbol}><span>{symbol}</span><strong>{money(amount)}</strong></li>)}</ul><div className="iv-actions"><button className="iv-text" onClick={() => { setScenarioEdit(s.id); setScenario({ name: s.name, price: String(Number(s.price_shock) * 100), fx: String(Number(s.fx_shock) * 100), oil: String(Number(s.oil_shock) * 100), forex: String(Number(s.forex_shock) * 100) }); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Edytuj</button><button className="iv-text" disabled={busy} onClick={() => void apply({ ...book, scenarios: book.scenarios.filter((item) => item.id !== s.id) })}>Usuń scenariusz</button></div></Panel>)}</div>
        </> : null}

        {tab === "costs" && book ? <><div className="iv-metrics"><Tile title="Wpisane koszty łącznie" value={money(result?.fees ?? null)} note="Już odjęte od wyniku; nie odejmuj ponownie" featured /><Tile title="Wpisane dywidendy netto" value={money(result?.dividends ?? null)} note="Nie są automatycznie pobierane od emitentów" /><Tile title="Gotówka PLN" value={money(result?.cash ?? null)} note="Po transakcjach, przepływach i kosztach" /><Tile title="Wynik zamkniętych pozycji" value={money(result?.realized_pnl ?? null)} note="Średni koszt, przed osobno pokazanymi opłatami" /></div><Panel title="Dodawaj rzeczywiste opłaty do historii"><p>Prowizję dopisz do transakcji. Podatek, finansowanie lub swap dodaj jako wpis „Koszt”. W ten sposób opłata trafia do wyniku dokładnie raz.</p><button className="iv-button" onClick={() => { setForm({ ...form, action: "fee" }); navigate("holdings"); }}>Dodaj koszt do historii →</button></Panel><div className="iv-legacy"><CashBudgetPanel currency="PLN" portfolioCash={result?.cash ?? null} budget={budget} onChange={(next) => { setBudget(next); try { localStorage.setItem(BUDGET, JSON.stringify(next)); setBudgetNotice("Budżet zapisany lokalnie."); } catch { setBudgetNotice("Nie udało się zapisać budżetu. Pobierz pełną kopię danych."); } }} /></div><p role="status">{budgetNotice}</p></> : null}

        {tab === "learn" ? <div className="iv-legacy"><EducationLab /><ForecastQuiz /></div> : null}

        {tab === "data" && book ? <>
          <Panel title="Rzeczywiste notowania, jawne daty" eyebrow="POCHODZENIE DANYCH"><p><strong>{marketOrigin}</strong>. Pobrano {new Date(book.market.fetched_at).toLocaleString("pl-PL")}. Wspólna data wyceny: {book.market.as_of}.</p><div className="iv-actions"><button className="iv-button iv-primary" disabled={busy} onClick={() => void refresh()}>Odśwież ceny z dostawcy</button><span>Dane dzienne mogą być opóźnione. Błąd pobrania pozostawia dotychczasową migawkę.</span></div><div className="iv-table-wrap" role="region" aria-label="Źródła cen" tabIndex={0}><table><thead><tr><th>Seria</th><th>Okres</th><th>Obserwacje</th><th>Źródło</th></tr></thead><tbody>{Object.entries(book.market.series).map(([symbol, series]) => <tr key={symbol}><th>{symbol === "PLN=X" ? "USD/PLN" : symbol}</th><td>{series.rows[0]?.date} — {series.rows.at(-1)?.date}</td><td>{series.rows.length}</td><td><a href={`https://finance.yahoo.com/quote/${encodeURIComponent(symbol)}/history/`} target="_blank" rel="noreferrer">Yahoo Finance ↗</a></td></tr>)}</tbody></table></div><p className="iv-note">Zapisane notowania zamknięcia są niekorygowane o dywidendy. Dane z różnych rynków nie pochodzą z tej samej sekundy. Importowana lub zmieniona migawka traci status zweryfikowanego pochodzenia. Publiczny dostawca może ograniczyć dostęp; aplikacja nie obiecuje notowań na żywo.</p></Panel>
          <div className="iv-grid"><Panel title="Automatyczny zapis i kopia">
            <p>Portfel, transakcje, ceny i scenariusze zapisują się po poprawnej analizie. Budżet i limit zapisują się osobno w tej samej przeglądarce. To lokalny zapis, bez konta w chmurze i bez szyfrowania.</p>
            <button className="iv-button iv-primary" disabled={!output || busy} onClick={() => downloadInvestor("QuantOps-kopia.json", JSON.stringify({ version: 1, workspace: book, budget, concentration_limit: limit }, null, 2))}>Pobierz pełną kopię JSON</button>
            <label className="iv-label">Przywróć kopię JSON<input type="file" accept="application/json,.json" onChange={(e) => { const file = e.target.files?.[0]; if (file) void readBackup(file); }} /></label>
            {backup ? <div className="iv-preview"><p>Kopia: {backup.workspace.transactions?.length ?? 0} wpisów. Zatwierdzenie zastąpi portfel, budżet i limit po walidacji.</p><button className="iv-button" disabled={busy} onClick={() => void restoreBackup()}>Zatwierdź przywrócenie portfela</button></div> : null}
          </Panel><Panel title="Twój limit koncentracji"><label className="iv-label">Maksymalny udział jednej pozycji (%)<input type="number" min="0" max="100" value={limit} onChange={(e) => setLimit(e.target.value)} /></label><button className="iv-button" onClick={() => { if (limit.trim() && Number.isFinite(Number(limit)) && Number(limit) >= 0 && Number(limit) <= 100) { try { localStorage.setItem(LIMITS, limit); setNotice("Zapisano własny limit. To preferencja, nie rekomendacja."); } catch { setError("Nie udało się zapisać limitu."); } } else setError("Limit musi mieścić się między 0 a 100%."); }}>Zapisz limit</button><p className="iv-note">Limit dotyczy ekspozycji brutto. To sygnał do sprawdzenia, a nie automatyczna decyzja inwestycyjna.</p></Panel></div>
          <Panel title="Metody w prostych słowach"><details><summary>Jak liczymy wynik, wpłaty i czas posiadania?</summary><p>Wartość = gotówka PLN + wartość akcji/ETF + niezrealizowany wynik futures/forex. Wynik = wartość minus wpłaty netto. TWR łączy dzienne stopy z oddzieleniem przepływów na koniec dnia; pierwszy depozyt rozpoczyna serię. W obrębie dnia zachowujemy kolejność wpisów. Średnia cena służy rozliczeniu częściowych zamknięć. Data posiadania to początek obecnej niezerowej pozycji. Brak dodatniego kapitału uniemożliwia wiarygodny TWR.</p></details><details><summary>Futures na ropę i forex</summary><p>CLZ26 to grudniowy WTI: 1 kontrakt × 1000 baryłek, notowanie USD/baryłkę. Wartość modelowa = liczba kontraktów × 1000 × (cena obecna − średnia) × USD/PLN. Nominału nie dodajemy do majątku. Depozyt 10% futures i 5% forex to jawne założenia, nie tabela brokera. Model pomija faktyczne dzienne przepływy variation margin, swap i dostawę. Po wygaśnięciu trzeba wpisać zamknięcie; nie rolujemy kontraktu automatycznie.</p><a href="https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.contractSpecs.html" target="_blank" rel="noreferrer">Specyfikacja WTI — CME Group ↗</a></details><details><summary>Ryzyko, ceny i ograniczenia</summary><p>Minimum 252 wspólne zwroty dla VaR/ES. Obecne ilości przeliczamy na historycznych zmianach cen. Dla akcji uwzględniamy zmianę ceny i FX; dla pochodnych zmianę notowania × mnożnik × datowany FX, bez finansowania. Horyzont to jedna wspólna obserwacja; luki mogą obejmować więcej niż dzień. Nie rekonstruujemy automatycznie dywidend, podatków, splitów ani składu ETF. Import ze splitami wymaga osobnej korekty ilości; automatyczne odświeżenie taką serię odrzuca.</p></details></Panel>
          <Panel title="Zarządzanie danymi"><div className="iv-actions"><button className="iv-button" disabled={busy} onClick={() => void demo()}>Przywróć portfel demonstracyjny</button><button className="iv-button iv-danger" disabled={busy} onClick={() => setDeleteConfirm(true)}>Usuń dane centrum portfela</button></div>{deleteConfirm ? <div className="iv-preview"><p>Usuniesz lokalne transakcje, scenariusze, budżet i limit tego centrum. Eksportowana kopia pozostanie na Twoim dysku. Osobny dawny warsztat /personal ma własny zapis.</p><button className="iv-button iv-danger" disabled={busy} onClick={() => void removeData()}>Potwierdzam usunięcie</button><button className="iv-text" onClick={() => setDeleteConfirm(false)}>Anuluj</button></div> : null}</Panel>
        </> : null}
        {result?.warnings.filter((w) => warningCopy[w]).length ? <aside className="iv-model-notes" aria-label="Uwagi do danych">{result.warnings.filter((w) => warningCopy[w]).map((w) => <p key={w}>ⓘ {warningCopy[w]}</p>)}</aside> : null}
      </main><footer className="iv-footer">QuantOps · Analiza ryzyka przed decyzją.<span>Bez zleceń i rekomendacji kupna/sprzedaży.</span></footer>
    </div>
  </div>;
}
