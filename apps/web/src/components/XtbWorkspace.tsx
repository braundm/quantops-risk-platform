import { useEffect, useRef, useState, type FormEvent } from "react";
import { money } from "../data/investorApi";
import { fileBase64, xtbRequest, type ImportedQuote, type XtbAnalysis, type XtbMerge, type XtbPreview, type XtbValuation } from "../data/xtbApi";
import type { StockQuote } from "../data/stocksApi";
import { downloadXtbBackup, emptyXtbAccounts, readXtbAccounts, xtbKey, type XtbAccount, type XtbAccounts } from "../lib/xtbAccounts";
import "../styles/xtb.css";

const holdingStatus: Record<string, string> = { unknown: "Stan portfela nieznany", incomplete: "Historia niepełna", snapshot: "Stan z raportu otwartych pozycji", reconstructed: "Stan odtworzony z zakupów i sprzedaży" };
const valueStatus: Record<string, string> = { unpriced: "Czeka na cenę", priced: "Cena zweryfikowana", corporate_action_review: "Split: sprawdź liczbę i koszt", derivative_or_unclassified: "Wycena wymaga osobnego modelu", incomplete_history: "Brak pełnej historii" };

export type WorkspaceView = "overview" | "holdings" | "accounts" | "import" | "history" | "settings";

export function XtbWorkspace({ userId, onBusy, view, onNavigate, brokers }: { userId: string; onBusy: (busy: boolean) => void; view: WorkspaceView; onNavigate: (view: WorkspaceView) => void; brokers: ("xtb" | "bossa")[] }) {
  const key = xtbKey(userId);
  const [initial] = useState(() => {
    try { const raw = localStorage.getItem(key); return { raw, registry: readXtbAccounts(raw), error: "" }; }
    catch (reason) { return { raw: null, registry: emptyXtbAccounts(), error: reason instanceof Error ? reason.message : "Nie można odczytać kont." }; }
  });
  const lastRaw = useRef(initial.raw);
  const alive = useRef(true);
  const controller = useRef<AbortController | null>(null);
  const [registry, setRegistry] = useState<XtbAccounts>(initial.registry);
  const [blocked, setBlocked] = useState(Boolean(initial.error));
  const [error, setError] = useState(initial.error);
  const [notice, setNotice] = useState("");
  const [selectedBroker, setBroker] = useState<"xtb" | "bossa">(brokers.includes("xtb") ? "xtb" : "bossa");
  const broker = brokers.includes(selectedBroker) ? selectedBroker : brokers[0] ?? "xtb";
  const [label, setLabel] = useState("");
  const [number, setNumber] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<XtbAnalysis | null>(null);
  const [valuation, setValuation] = useState<XtbValuation | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [pasted, setPasted] = useState("");
  const [observed, setObserved] = useState(new Date().toISOString().slice(0, 16));
  const [preview, setPreview] = useState<XtbPreview | null>(null);
  const [completeSnapshot, setCompleteSnapshot] = useState(false);
  const [completeLedger, setCompleteLedger] = useState(false);
  const [automatic, setAutomatic] = useState(false);
  const account = registry.accounts.find(item => item.id === registry.selected) ?? null;
  useEffect(() => { onBusy(busy || loading); return () => onBusy(false); }, [busy, loading, onBusy]);
  useEffect(() => { alive.current = true; return () => { alive.current = false; controller.current?.abort(); }; }, []);
  useEffect(() => {
    const changed = (event: StorageEvent) => { if (event.key === key) { setBlocked(true); setError("Dane kont zmieniły się w innej karcie. Odśwież stronę przed dalszym zapisem."); controller.current?.abort(); } };
    window.addEventListener("storage", changed); return () => window.removeEventListener("storage", changed);
  }, [key]);
  useEffect(() => {
    const pending = new AbortController();
    setAnalysis(null); setValuation(null); setPreview(null); setCompleteSnapshot(false); setCompleteLedger(false);
    if (!account || blocked) { setLoading(false); return; }
    setLoading(true);
    void Promise.all([
      xtbRequest<XtbAnalysis>("analyze", account.book, pending.signal),
      xtbRequest<XtbValuation>("value", { book: account.book, marks: account.marks }, pending.signal),
    ]).then(([next, values]) => { if (!pending.signal.aborted) { setAnalysis(next); setValuation(values); } })
      .catch((reason: unknown) => { if (!pending.signal.aborted) setError(reason instanceof Error ? reason.message : "Nie można sprawdzić konta."); })
      .finally(() => { if (!pending.signal.aborted) setLoading(false); });
    return () => pending.abort();
  }, [account, blocked]);

  function save(next: XtbAccounts) {
    if (!alive.current) return;
    if (blocked || localStorage.getItem(key) !== lastRaw.current) throw new Error("Zapis zmienił się w innej karcie; odśwież stronę.");
    const raw = JSON.stringify(next); localStorage.setItem(key, raw); lastRaw.current = raw; setRegistry(next);
  }
  function replace(next: XtbAccount) { save({ ...registry, accounts: registry.accounts.map(item => item.id === next.id ? next : item) }); }
  function fail(reason: unknown) { if (alive.current) setError(reason instanceof Error ? reason.message : "Operacja nie powiodła się."); }
  function invalidate() { setPreview(null); setCompleteSnapshot(false); setCompleteLedger(false); setNotice(""); }
  function addAccount(event: FormEvent) {
    event.preventDefault(); setError("");
    try {
      if (registry.accounts.length >= 50 || registry.accounts.some(item => item.book.account_number === number.trim())) throw new Error("Konto już istnieje albo osiągnięto limit 50 kont.");
      const next: XtbAccount = { id: crypto.randomUUID(), label: label.trim(), broker: "xtb", marks: [], imports: [], book: { account_number: number.trim(), currency, records: [], open_snapshot_at: null, ledger_complete: false } };
      save({ ...registry, selected: next.id, accounts: [...registry.accounts, next] }); setLabel(""); setNumber(""); setNotice("Dodano konto. Teraz wczytaj jego raport."); onNavigate("import");
    } catch (reason) { fail(reason); }
  }
  async function previewReport() {
    if (!account) return;
    const pending = new AbortController(); controller.current = pending;
    setBusy(true); setError(""); setPreview(null); setNotice("");
    try {
      const selectedFile = pasted.trim() ? new File([pasted], "wklejony-raport.csv", { type: "text/csv" }) : file;
      if (!selectedFile) throw new Error("Wybierz plik albo wklej treść CSV.");
      const result = await xtbRequest<XtbPreview>("preview", { account_number: account.book.account_number, currency: account.book.currency, observed_at: `${observed}:00Z`, filename: selectedFile.name, content_base64: await fileBase64(selectedFile) }, pending.signal);
      if (alive.current && !pending.signal.aborted) setPreview(result);
    } catch (reason) { if (!pending.signal.aborted) fail(reason); }
    finally { if (alive.current) setBusy(false); }
  }
  async function confirmReport() {
    if (!account || !preview) return;
    const pending = new AbortController(); controller.current = pending;
    setBusy(true); setError("");
    try {
      const result = await xtbRequest<XtbMerge>("merge", { current: account.book, preview, complete_snapshot: completeSnapshot, complete_ledger: completeLedger }, pending.signal);
      if (!alive.current || pending.signal.aborted) return;
      const entry = { hash: preview.report_hash, at: new Date().toISOString(), filename: pasted.trim() ? "wklejony-raport.csv" : file?.name ?? "Raport", records: preview.book.records.length };
      const marks = account.marks.filter(mark => {
        const holdings = result.analysis.holdings.filter(row => row.symbol === mark.symbol && row.status === "spot");
        return holdings.length > 0 && result.analysis.holdings_status !== "incomplete" && mark.quote.requested_date === holdings.map(row => row.opened_at.slice(0, 10)).sort()[0];
      });
      replace({ ...account, book: result.book, marks, imports: account.imports.some(item => item.hash === entry.hash) ? account.imports : [...account.imports, entry] });
      setPreview(null); setNotice(`Raport zapisany. Pominięte duplikaty: ${result.duplicates}. Ceny można teraz odświeżyć.`); onNavigate("holdings");
    } catch (reason) { if (!pending.signal.aborted) fail(reason); }
    finally { if (alive.current) setBusy(false); }
  }
  async function refreshPrices() {
    if (!account || !analysis || blocked || busy || loading) return;
    const pending = new AbortController(); controller.current = pending;
    setBusy(true); setError("");
    try {
      const symbols = [...new Set(analysis.holdings.filter(item => item.status === "spot").map(item => item.symbol))];
      if (symbols.length > 20) throw new Error("Jednorazowe odświeżenie obsługuje do 20 różnych instrumentów; większy portfel wymaga kolejki notowań.");
      const marks: ImportedQuote[] = [...account.marks];
      const failures: string[] = [];
      for (const symbol of symbols) {
        try {
          const quote = await xtbRequest<StockQuote>("quote", { book: account.book, symbol }, pending.signal);
          const index = marks.findIndex(item => item.symbol === symbol);
          if (index >= 0) marks.splice(index, 1); marks.push({ symbol, quote });
        } catch (reason) { if (pending.signal.aborted) throw reason; failures.push(symbol); }
      }
      await xtbRequest<XtbValuation>("value", { book: account.book, marks }, pending.signal);
      if (!alive.current || pending.signal.aborted) return;
      replace({ ...account, marks });
      setNotice(`Odświeżono ceny: ${symbols.length - failures.length}.`);
      if (failures.length) setError(`Brak zweryfikowanej ceny: ${failures.join(", ")}. Zachowano poprzednie ceny i ich daty.`);
    } catch (reason) { if (!pending.signal.aborted) fail(reason); }
    finally { if (alive.current) setBusy(false); }
  }
  useEffect(() => {
    if (!automatic || !account) return;
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void refreshPrices(); }, 15 * 60 * 1000);
    return () => clearInterval(timer);
  });

  return <>
    {view === "overview" ? <section className="qo-overview-grid" aria-label="Podsumowanie przestrzeni"><article className="iv-panel"><span className="qo-kicker">TWOI BROKERZY</span><strong>{brokers.length}</strong><p>{brokers.map(item => item === "xtb" ? "XTB" : "Bossa").join(" · ")}</p></article><article className="iv-panel"><span className="qo-kicker">RACHUNKI XTB</span><strong>{registry.accounts.length}</strong><p>Oddzielne dane i waluty</p></article><article className="iv-panel"><span className="qo-kicker">WCZYTANE RAPORTY</span><strong>{registry.accounts.reduce((sum, item) => sum + item.imports.length, 0)}</strong><p>Historia bez duplikowania zdarzeń</p></article></section> : null}
    {view === "overview" ? <section className="iv-panel qo-next-step"><div><p className="iv-eyebrow">TWÓJ NASTĘPNY KROK</p><h2>{registry.accounts.length ? "Utrzymuj aktualny stan portfela" : "Dodaj pierwszy rachunek"}</h2><p>{registry.accounts.length ? "Nowe zakupy i sprzedaże wymagają aktualnego raportu. Ceny mają osobną datę." : "Nadaj mu nazwę, wybierz walutę i przygotuj plik od brokera."}</p></div><button className="iv-button iv-primary" onClick={() => onNavigate(registry.accounts.length && brokers.includes("xtb") ? "import" : "accounts")}>{registry.accounts.length && brokers.includes("xtb") ? "Wczytaj nowy raport →" : "Przejdź do kont →"}</button></section> : null}
    {view === "accounts" ? <section className="iv-panel" id="broker"><p className="iv-eyebrow">IMPORT RAPORTÓW · BEZ ŁĄCZENIA Z RACHUNKIEM</p><h2>Rachunki u brokera</h2>
      <div className="xtb-brokers">{brokers.map(item => <button key={item} className={`xtb-broker ${broker === item ? "selected" : ""}`} aria-pressed={broker === item} disabled={busy || loading} onClick={() => { setBroker(item); invalidate(); }}><img src={`/brands/${item}.svg`} alt={item === "xtb" ? "XTB" : "Bossa"} /><span>{item === "xtb" ? "Import CSV, XLSX i ZIP" : "Importer w przygotowaniu"}</span></button>)}</div>
      {broker === "bossa" ? <p>Na razie importujemy wyłącznie raporty XTB. Import Bossa pojawi się po sprawdzeniu formatu ich raportów.</p> : <p>Dodaj każde konto XTB osobno, również konta w tej samej walucie. Numery służą do sprawdzenia zgodności raportu; nie podawaj hasła ani danych logowania.</p>}
    </section> : null}
    {error ? <div className="iv-alert iv-error" role="alert">{error}</div> : null}
    {notice ? <p className="iv-notice" role="status">{notice}</p> : null}
    {blocked ? <section className="iv-panel"><h2>Odzyskaj zapis kont</h2><button className="iv-button" onClick={() => downloadXtbBackup(userId)}>Pobierz kopię zapisu</button><button className="iv-button" onClick={() => window.location.reload()}>Wczytaj ponownie</button></section> : null}
    {brokers.includes("xtb") && (broker === "xtb" || view !== "accounts") && !blocked && view !== "settings" ? <>
      <section className="iv-panel" id="accounts"><h2>{view === "accounts" ? "Twoje konta XTB" : "Wybrane konto XTB"}</h2>
        {registry.accounts.length ? <div className="xtb-account-list" role="group" aria-label="Konta XTB">{registry.accounts.map(item => <button className={`iv-button ${item.id === account?.id ? "iv-primary" : ""}`} key={item.id} disabled={busy || loading} aria-pressed={item.id === account?.id} onClick={() => { try { save({ ...registry, selected: item.id }); setNotice(""); invalidate(); } catch (reason) { fail(reason); } }}>{item.label} · {item.book.currency} · ••••{item.book.account_number.slice(-4)}</button>)}</div> : <p>Nie masz jeszcze kont. Dodaj konto, z którego pochodzi raport.</p>}
        {view === "accounts" ? <form onSubmit={addAccount}><fieldset disabled={busy || loading}><legend>Dodaj konto</legend><div className="iv-form-grid"><label>Nazwa konta<input required maxLength={64} value={label} placeholder="np. Główne USD, IKE" onChange={event => setLabel(event.target.value)} /></label><label>Numer konta XTB<input required inputMode="numeric" pattern="[0-9]{1,20}" maxLength={20} value={number} onChange={event => setNumber(event.target.value)} /></label><label>Waluta konta<select value={currency} onChange={event => setCurrency(event.target.value)}>{["USD", "PLN", "EUR", "GBP", "CHF"].map(value => <option key={value}>{value}</option>)}</select></label></div><button className="iv-button iv-primary">Dodaj konto XTB</button></fieldset></form> : !registry.accounts.length ? <button className="iv-button iv-primary" onClick={() => onNavigate("accounts")}>Dodaj rachunek XTB →</button> : null}
      </section>
      {account ? <>
        {view === "import" ? <section className="iv-panel" id="import"><p className="iv-eyebrow">{account.label} · {account.book.currency}</p><h2>Wczytaj raport XTB</h2><p>Wybierz CSV, XLSX lub ZIP z raportem albo wklej CSV. Najpierw pokażemy podgląd; zapis nastąpi dopiero po zatwierdzeniu.</p>
          <fieldset disabled={busy || loading}><legend>Źródło raportu</legend><div className="iv-form-grid"><label>Plik raportu<input type="file" accept=".csv,.xlsx,.zip" onChange={event => { setFile(event.target.files?.[0] ?? null); setPasted(""); invalidate(); }} /></label><label>Stan raportu — data i godzina UTC<input type="datetime-local" required value={observed} onChange={event => { setObserved(event.target.value); invalidate(); }} /></label></div><label className="iv-label">Lub wklej treść CSV<textarea rows={5} maxLength={8000000} value={pasted} placeholder="Instrument,Category,Ticker,Type,Volume,Open Price,Open Time (UTC),Position ID" onChange={event => { setPasted(event.target.value); setFile(null); invalidate(); }} /></label><button className="iv-button iv-primary" disabled={!file && !pasted.trim()} onClick={() => void previewReport()}>Pokaż podgląd raportu</button></fieldset>
          <p className="iv-note">Stan raportu nie jest dzisiejszym stanem konta, jeśli plik jest starszy. Daty „Date to (UTC)” z raportu mają pierwszeństwo przed późniejszą datą formularza. Plik jest przetwarzany przez API tej aplikacji, bez przesyłania do brokera lub dostawcy cen.</p>
          {preview ? <section className="iv-preview" aria-label="Podgląd raportu XTB"><h3>Sprawdź przed zapisem</h3><div className="iv-metrics"><article className="iv-tile"><span>Zamknięte pozycje</span><strong>{preview.closed_count}</strong></article><article className="iv-tile"><span>Otwarte pozycje</span><strong>{preview.open_count}</strong></article><article className="iv-tile"><span>Transakcje kupna/sprzedaży</span><strong>{preview.fill_count}</strong></article><article className="iv-tile"><span>Operacje gotówkowe</span><strong>{preview.cash_count}</strong></article></div>
            {!preview.has_open_section && !preview.fill_count ? <p className="iv-alert">Ten raport nie zawiera otwartych pozycji ani historii zakupów. Zapiszemy historię zamknięć i gotówki, ale bieżący portfel pozostanie nieznany.</p> : null}
            {preview.book.records.some(row => row.asset_type === "cfd") ? <p>CFD zachowamy w historii. Nie wyceniamy ich jak akcji ani nie używamy depozytu jako wartości pozycji.</p> : null}
            <p>Import do wybranego konta · {preview.book.currency} · zapisów: {preview.book.records.length}. Jeśli CSV nie zawiera numeru rachunku lub waluty, sprawdź je samodzielnie przed zatwierdzeniem.</p>
            {preview.has_open_section ? <label className="sq-check"><input type="checkbox" checked={completeSnapshot} onChange={event => setCompleteSnapshot(event.target.checked)} />Potwierdzam pełny stan wszystkich otwartych pozycji tego konta na {preview.snapshot_at?.slice(0, 19).replace("T", " ")} UTC; zastąpi poprzedni stan.</label> : null}
            {preview.fill_count ? <label className="sq-check"><input type="checkbox" checked={completeLedger} onChange={event => setCompleteLedger(event.target.checked)} />Potwierdzam pełną historię zakupów i sprzedaży od początku konta, łącznie z poprzednimi importami.</label> : null}
            <div className="iv-actions"><button className="iv-button iv-primary" disabled={busy || (preview.has_open_section && !completeSnapshot)} onClick={() => void confirmReport()}>Zatwierdź import na to konto</button><button className="iv-button" disabled={busy} onClick={invalidate}>Anuluj podgląd</button></div>
          </section> : null}
        </section> : null}
        {busy || loading ? <p role="status">Sprawdzam dane…</p> : null}
        {analysis && valuation && (view === "holdings" || view === "overview") ? <section className="iv-panel" id="owned" aria-label="Portfel z raportów"><p className="iv-eyebrow">{account.label} · {holdingStatus[analysis.holdings_status]}</p><h2>Portfel z raportów XTB</h2>
          <div className="iv-metrics"><article className="iv-tile"><span>Zamknięte pozycje w historii</span><strong>{analysis.closed_count}</strong><small>Wynik podany w raporcie: {money(analysis.reported_realized_pnl, account.book.currency)}</small></article><article className="iv-tile"><span>Operacje gotówkowe w historii</span><strong>{analysis.cash_count}</strong><small>Przepływy netto: {money(analysis.cash_movement, account.book.currency)} · to nie saldo konta</small></article>{valuation.totals.map(total => <article className="iv-tile" key={total.currency}><span>Pokryta wycena · {total.currency}</span><strong>{money(total.value, total.currency)}</strong><small>Zmiana niezrealizowana: {money(total.unrealized, total.currency)}</small></article>)}</div>
          {analysis.holdings_status === "unknown" ? <p className="iv-alert">Bieżący stan jest nieznany. Potrzebny raport otwartych pozycji albo pełna historia zakupów i sprzedaży; historia zamknięć nie oznacza pustego portfela.</p> : null}
          {analysis.holdings_status === "incomplete" ? <p className="iv-alert">Niepełna historia lub nierozpoznany instrument. Wycena jest wstrzymana do uzupełnienia danych.</p> : null}
          {account.book.open_snapshot_at ? <p>Stan pozycji na: {account.book.open_snapshot_at.slice(0, 19).replace("T", " ")} UTC. Nowe zakupy i sprzedaże wymagają kolejnego raportu.</p> : null}
          {analysis.holdings.length && view === "holdings" ? <><div className="iv-actions"><button className="iv-button iv-primary" disabled={busy || loading || analysis.holdings_status === "incomplete" || !analysis.holdings.some(item => item.status === "spot")} onClick={() => void refreshPrices()}>Odśwież ceny otwartych akcji i ETF</button><label className="sq-check"><input type="checkbox" checked={automatic} onChange={event => setAutomatic(event.target.checked)} />Odświeżaj co 15 minut, gdy ta karta jest widoczna</label></div><div className="iv-table-wrap" role="region" aria-label="Otwarte pozycje XTB" tabIndex={0}><table><thead><tr><th>Instrument</th><th>Typ</th><th>Strona</th><th>Ilość</th><th>Wycena</th><th>Data ceny</th><th>Pokrycie</th></tr></thead><tbody>{valuation.positions.map(row => { const holding = analysis.holdings.find(item => item.symbol === row.symbol && item.asset_type === row.asset_type && item.side === row.side); const mark = account.marks.find(item => item.symbol === row.symbol); return <tr key={`${row.symbol}:${row.asset_type}:${row.side}`}><th>{holding?.name}<small className="sq-block">{row.symbol}</small></th><td>{row.asset_type}</td><td>{row.side}</td><td>{row.quantity}</td><td>{row.currency ? money(row.value, row.currency) : "Brak wyceny"}</td><td>{row.price_date ?? "Brak ceny"}{mark && row.price_date ? <small className="sq-block"><a href={mark.quote.source_url} target="_blank" rel="noreferrer">Źródło ↗</a>{mark.quote.warnings.includes("stale_provider_close") ? " · Cena starsza niż 7 dni" : ""}</small> : null}</td><td>{valueStatus[row.status] ?? row.status}</td></tr>; })}</tbody></table></div></> : analysis.holdings_status !== "unknown" && analysis.holdings_status !== "incomplete" ? <p>W dostarczonym stanie nie ma otwartych pozycji.</p> : null}
          <p className="iv-note">Wartości pozostają w walutach instrumentów, bez dodawania USD do PLN. Ceny to datowane zamknięcia, nie notowania w czasie rzeczywistym. Brakujące dane, CFD i niepełna historia nie dają kompletnej miary ryzyka portfela. Wynik zamknięć i operacje „Close trade” pokazujemy osobno, bez podwójnego liczenia.</p>
        </section> : null}
        {view === "overview" && analysis?.holdings.length ? <button className="iv-button" onClick={() => onNavigate("holdings")}>Przejdź do pozycji i cen →</button> : null}
        {view === "history" ? <section className="iv-panel"><h2>Historia importów i kopia danych</h2><p>{account.imports.length} raportów · {account.book.records.length} unikalnych zapisów. Ponowne wczytanie tych samych zdarzeń nie powiększa portfela.</p><button className="iv-button" onClick={() => downloadXtbBackup(userId)}>Pobierz kopię kont XTB</button><button className="iv-button iv-danger" disabled={busy || loading} onClick={() => { if (!window.confirm(`Usunąć konto ${account.label} i wszystkie jego importy z tej przeglądarki?`)) return; try { const accounts = registry.accounts.filter(item => item.id !== account.id); save({ ...registry, selected: accounts[0]?.id ?? null, accounts }); } catch (reason) { fail(reason); } }}>Usuń to konto i jego dane</button>{account.imports.length ? <div className="iv-table-wrap" role="region" aria-label="Zaimportowane raporty" tabIndex={0}><table><thead><tr><th>Plik</th><th>Data importu</th><th>Zapisy w raporcie</th></tr></thead><tbody>{[...account.imports].reverse().map(item => <tr key={item.hash}><th>{item.filename}</th><td>{new Date(item.at).toLocaleString("pl-PL")}</td><td>{item.records}</td></tr>)}</tbody></table></div> : <p>Historia pojawi się po zatwierdzeniu pierwszego raportu.</p>}</section> : null}
      </> : null}
    </> : null}
    {!brokers.includes("xtb") && view !== "settings" ? <section className="iv-panel"><h2>Bossa — importer w przygotowaniu</h2><p>Twój wybór został zapisany. Na razie raporty można importować z XTB.</p><button className="iv-button" onClick={() => onNavigate("accounts")}>Zarządzaj brokerami</button></section> : null}
  </>;
}
