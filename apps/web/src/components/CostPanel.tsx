import { useEffect, useRef, useState } from "react";

import { retailRequest } from "../data/retailApi";

const categories = { commission: "Prowizja", spread: "Spread", conversion: "Przewalutowanie", financing: "Finansowanie / swap", product: "Opłata produktu", slippage: "Poślizg", hedge: "Zabezpieczenie", rebalance: "Rebalancing" };
interface Item { id: string; category: keyof typeof categories; amount: string; frequency: "one_off" | "monthly" | "annual"; source: "actual" | "estimated" | "user"; included_in_prices: boolean }
export interface CostSummary { one_off: string; recurring_annual: string; excluded_from_total: string[]; model_version: string }
const money = (value: string, currency: string) => new Intl.NumberFormat("pl-PL", { style: "currency", currency }).format(Number(value));

export function CostPanel({ currency, onResult }: { currency: string; onResult: (value: CostSummary | null) => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [category, setCategory] = useState<Item["category"]>("commission");
  const [amount, setAmount] = useState("");
  const [frequency, setFrequency] = useState<Item["frequency"]>("one_off");
  const [source, setSource] = useState<Item["source"]>("user");
  const [included, setIncluded] = useState(false);
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [error, setError] = useState("");
  const latest = useRef(0);
  const callback = useRef(onResult); callback.current = onResult;
  useEffect(() => { setItems([]); setSummary(null); callback.current(null); latest.current++; }, [currency]);
  async function update(next: Item[]) {
    const token = ++latest.current; setItems(next); setSummary(null); callback.current(null); setError("");
    try {
      const value = await retailRequest<CostSummary>("cost-budget", { items: next });
      if (token === latest.current) { setSummary(value); callback.current(value); }
    } catch (err: unknown) { if (token === latest.current) setError(err instanceof Error ? err.message : "Błąd kosztów."); }
  }
  return <section className="qo-panel" id="costs"><div className="qo-panel-heading"><div><p className="qo-eyebrow">MAŁE KWOTY. DUŻA RÓŻNICA W CZASIE.</p><h2>Budżet kosztów portfela</h2></div><span className="qo-tag">Kwoty w {currency}</span></div><p className="qo-muted">Oddziel opłaty jednorazowe od kosztów utrzymania. Wpisane koszty są osobnym budżetem; nie odejmujemy ich ponownie od wyników cen ani modelu forward.</p>
    {error ? <p className="qo-alert qo-error" role="alert">{error}</p> : null}
    <form className="qo-cost-form" onSubmit={(e) => { e.preventDefault(); void update([...items, { id: crypto.randomUUID(), category, amount, frequency, source, included_in_prices: included }]); setAmount(""); }}>
      <label className="qo-field">Rodzaj kosztu<select value={category} onChange={(e) => setCategory(e.target.value as Item["category"])}>{Object.entries(categories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label className="qo-field">Kwota kosztu ({currency})<input required type="number" min="0" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
      <label className="qo-field">Okres opłaty<select value={frequency} onChange={(e) => setFrequency(e.target.value as Item["frequency"])}><option value="one_off">Jednorazowo</option><option value="monthly">Co miesiąc</option><option value="annual">Co rok</option></select></label>
      <label className="qo-field">Źródło kosztu<select value={source} onChange={(e) => setSource(e.target.value as Item["source"])}><option value="user">Wprowadzone</option><option value="estimated">Szacunek</option><option value="actual">Rzeczywista opłata</option></select></label>
      <label className="qo-checkbox"><input type="checkbox" checked={included} onChange={(e) => setIncluded(e.target.checked)} /> Już zawarty w cenach produktu</label>
      <button className="qo-button qo-primary" type="submit" disabled={items.length >= 200}>Dodaj koszt</button>
    </form>
    {items.length ? <ul className="qo-cost-list">{items.map((item) => <li key={item.id}><div><strong>{categories[item.category]}</strong><small>{item.source === "actual" ? "Rzeczywisty" : item.source === "estimated" ? "Szacunek" : "Wprowadzony"} · {item.frequency === "one_off" ? "jednorazowo" : item.frequency === "monthly" ? "miesięcznie" : "rocznie"}{item.included_in_prices ? " · wyłączony z sumy (w cenie)" : ""}</small></div><span>{money(item.amount, currency)}</span><button className="qo-text-button" onClick={() => void update(items.filter((p) => p.id !== item.id))} aria-label={`Usuń koszt ${categories[item.category]}`}>Usuń</button></li>)}</ul> : <p className="qo-note">Brak wpisanych opłat nie oznacza, że portfel jest bezkosztowy.</p>}
    {summary ? <div className="qo-cost-totals" aria-live="polite"><div><span>Koszty jednorazowe</span><strong>{money(summary.one_off, currency)}</strong></div><div><span>Koszty okresowe / rok</span><strong>{money(summary.recurring_annual, currency)}</strong></div><small>{summary.excluded_from_total.length} opłat już w cenach wyłączono z sumy.</small></div> : null}
    <p className="qo-note">Miesięczne opłaty mnożymy przez 12; bez kapitalizacji i bez inflacji. Finansowanie i swap muszą pochodzić ze specyfikacji instrumentu. Nie wyliczamy podatków ani kosztu transakcji na podstawie samej ilości; wpisz znaną opłatę lub jawny szacunek. Zmiana waluty bazowej czyści budżet zamiast przeliczać go nieaktualnym kursem. Dane pozostają w bieżącej sesji.</p>
  </section>;
}
