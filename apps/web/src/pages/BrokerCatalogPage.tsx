import { useEffect, useState } from "react";
import "../styles/treasury.css";
import "../styles/brokerCatalog.css";

interface Instrument {
  id: string; broker: string; symbol: string; name: string; instrument_type: string;
  market: string; currency: string | null; isin: string | null; source_id: string;
  source_category: string; close_only: boolean | null; specifications: Record<string, string>;
}
interface Source {
  id: string; broker: string; url: string; fetched_at: string; effective_date: string | null;
  count: number; expected_count: number | null; status: string; note: string;
}
interface CatalogPage {
  total: number; items: Instrument[]; sources: Source[]; markets: string[]; instrument_types: string[];
}
const names: Record<string, string> = {
  equity: "Akcje / ADR / REIT", etf: "ETF", etc: "ETC", etn: "ETN", etp: "Pozostałe ETP",
  cfd: "CFD", option: "Opcje", future: "Kontrakty terminowe", bond: "Obligacje",
  right: "Prawa", warrant: "Warranty", certificate: "Certyfikaty", other: "Inne",
};
const sourceNames: Record<string, string> = {
  "bossa-world": "Bossa: zagranica", bossafx: "BOSSAFX: CFD", "bossa-akcje": "Bossa: GPW akcje i PDA",
  "bossa-newconnect": "Bossa: NewConnect", "bossa-globalconnect": "Bossa: GlobalConnect",
  "bossa-opcje": "Bossa: opcje", "bossa-kontrakty": "Bossa: futures", "bossa-etf": "Bossa: ETF GPW",
  "bossa-obligacje": "Bossa: obligacje", "bossa-certyfikaty": "Bossa: certyfikaty",
};
const specificationNames: Record<string, string> = {
  currencyCode: "Jednostka ceny w źródle", quotation_currency: "Jednostka ceny w źródle",
  nominal_value_one_lot: "Wartość nominalna lota (zapis źródłowy)", contract_size: "Rozmiar kontraktu",
  leverage: "Dźwignia w specyfikacji", trading_hours: "Godziny sesji w źródle",
  trading_days: "Dni sesji", settlement_method: "Rozliczenie", exercise_type: "Wykonanie",
  payoff_type: "Typ wypłaty", possible_trade_direction: "Kierunki w specyfikacji",
  value: "Wielkość kontraktu (zapis źródłowy)", min_value: "Minimalna zmiana ceny",
};

export function BrokerCatalogPage() {
  const [query, setQuery] = useState("");
  const [broker, setBroker] = useState("");
  const [kind, setKind] = useState("");
  const [market, setMarket] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<CatalogPage | null>(null);
  const [selected, setSelected] = useState<Instrument | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true); setError(""); setPage(null); setSelected(null);
      const params = new URLSearchParams({ q: query, offset: String(offset), limit: "50" });
      if (broker) params.set("broker", broker);
      if (kind) params.set("instrument_type", kind);
      if (market) params.set("market", market);
      void fetch(`/api/v1/broker-catalog?${params}`, { signal: controller.signal }).then(async response => {
        if (!response.ok) throw new Error("Katalog jest niedostępny. Sprawdź połączenie z lokalnym API.");
        const data = await response.json() as CatalogPage;
        if (!controller.signal.aborted) setPage(data);
      }).catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Nie udało się pobrać katalogu.");
      }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, broker, kind, market, offset, retry]);
  const source = page?.sources.find(item => item.id === selected?.source_id);
  return <div className="treasury-page broker-catalog-page">
    <a href="/stocks">← Wróć do portfela akcji</a>
    <p className="eyebrow">BOSSA · XTB · PUBLICZNE SPECYFIKACJE</p>
    <h1>Katalog instrumentów Bossa i XTB</h1>
    <p>Wyszukuj symbole, nazwy i ISIN. Akcja i CFD na tę akcję są osobnymi instrumentami.</p>
    <section className="panel catalog-notice" aria-label="Zakres obsługi">
      <h2>Pokrycie częściowe · dane referencyjne</h2>
      <p>Katalog obejmuje pobrane publiczne listy XTB Polska, listę zagraniczną Bossa i BOSSAFX. Krajowe listy Bossa, w tym serie opcji i futures, zwróciły puste dane: pozostają niepokryte.</p>
      <p>Wpis w katalogu nie potwierdza dostępności na Twoim rachunku ani bieżącej ceny. Ten ekran nie wycenia pozycji. Portfel akcji nadal korzysta ze swojego zweryfikowanego zestawu 40 symboli.</p>
    </section>
    <section className="panel" aria-label="Wyszukiwarka instrumentów">
      <h2>Znajdź instrument</h2>
      <div className="treasury-fields">
        <label>Symbol, nazwa lub ISIN<input maxLength={120} value={query} placeholder="np. AAPL, Apple, PL…" onChange={event => { setQuery(event.target.value); setOffset(0); }} /></label>
        <label>Źródło<select aria-label="Źródło" value={broker} onChange={event => { setBroker(event.target.value); setOffset(0); }}><option value="">Bossa i XTB</option><option value="bossa">Bossa / BOSSAFX</option><option value="xtb">XTB Polska</option></select></label>
        <label>Typ instrumentu<select value={kind} onChange={event => { setKind(event.target.value); setOffset(0); }}>{[["", "Wszystkie typy"], ...Object.entries(names)].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Rynek<select value={market} onChange={event => { setMarket(event.target.value); setOffset(0); }}><option value="">Wszystkie rynki</option>{(page?.markets ?? (market ? [market] : [])).map(value => <option key={value}>{value}</option>)}</select></label>
      </div>
      {loading ? <p role="status">Pobieram katalog…</p> : null}
      {error ? <div role="alert"><p>{error}</p><button className="button" onClick={() => setRetry(value => value + 1)}>Spróbuj ponownie</button></div> : null}
      {page && !loading ? <>
        <p role="status">Wyniki: {page.total.toLocaleString("pl-PL")} · strona {Math.floor(offset / 50) + 1}</p>
        {page.items.length ? <div className="treasury-table" role="region" aria-label="Wyniki katalogu" tabIndex={0}><table>
          <thead><tr><th scope="col">Symbol / szczegóły</th><th scope="col">Nazwa</th><th scope="col">Typ</th><th scope="col">Źródło</th><th scope="col">Rynek</th><th scope="col">Waluta</th></tr></thead>
          <tbody>{page.items.map(row => <tr key={row.id}><td><button className="button" aria-label={`${row.symbol} — ${row.broker} — ${row.instrument_type}`} onClick={() => setSelected(row)}>{row.symbol}</button></td><td className="catalog-name">{row.name}{row.close_only ? <strong> · Close only</strong> : null}</td><td>{names[row.instrument_type]}</td><td>{row.broker === "xtb" ? "XTB" : row.source_id === "bossafx" ? "BOSSAFX" : "Bossa"}</td><td>{row.market}</td><td>{row.currency ?? "Brak danych"}</td></tr>)}</tbody>
        </table></div> : <p>Brak wpisów w pobranym zakresie. Nie oznacza to braku instrumentu w ofercie brokera.</p>}
        <div className="treasury-actions"><button className="button" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 50))}>Poprzednia strona</button><button className="button" disabled={offset + 50 >= page.total} onClick={() => setOffset(value => value + 50)}>Następna strona</button></div>
      </> : null}
    </section>
    {selected && source ? <section className="panel" aria-label="Szczegóły instrumentu">
      <h2>{selected.symbol} · {selected.name}</h2>
      <p>{names[selected.instrument_type]} · {selected.market} · {selected.broker.toUpperCase()}</p>
      <p>ISIN: {selected.isin ?? "Brak w źródle"} · kategoria źródłowa: {selected.source_category}</p>
      <p><a href={source.url} target="_blank" rel="noreferrer">Oficjalne źródło ↗</a> · pobrano {new Date(source.fetched_at).toLocaleString("pl-PL", { timeZone: "UTC" })} UTC{source.effective_date ? ` · dokument na dzień ${source.effective_date}` : ""}</p>
      <dl>{Object.entries(selected.specifications).map(([key, value]) => <div className="catalog-spec" key={key}><dt>{specificationNames[key] ?? key}</dt><dd>{value}</dd></div>)}</dl>
      <p>Parametry zachowują zapis źródłowy; GBX oznacza pensy i nie jest traktowane jako GBP.</p>
      {selected.instrument_type === "cfd" || selected.instrument_type === "option" || selected.instrument_type === "future" ? <p>Analiza pochodnych wymaga zweryfikowanej waluty rozliczenia, mnożnika, depozytu i finansowania; opcje dodatkowo serii, terminu, strike, typu call/put i danych zmienności. Brakujących parametrów nie uzupełniamy domyślnymi wartościami.</p> : null}
      <button className="button" onClick={() => setSelected(null)}>Zamknij szczegóły</button>
    </section> : null}
    <section className="panel" aria-label="Pokrycie źródeł">
      <h2>Pokrycie i aktualność źródeł</h2>
      <p>„Pobrana lista” oznacza komplet pobranych wierszy danego źródła. Datowane dokumenty oraz bieżąca oferta mogą się różnić.</p>
      <div className="catalog-sources">{page?.sources.map(item => <article key={item.id}><h3>{sourceNames[item.id] ?? `XTB: ${item.id.replace("xtb-", "")}`}</h3><p><strong>{item.count.toLocaleString("pl-PL")} wpisów</strong> · {item.status === "source_complete" ? "Pobrana lista" : "BRAK POKRYCIA"}</p><p>{item.effective_date ? `Dokument: ${item.effective_date} · ` : ""}Pobrano: {item.fetched_at.slice(0, 10)}</p><a href={item.url} target="_blank" rel="noreferrer">Źródło ↗</a></article>)}</div>
    </section>
  </div>;
}
