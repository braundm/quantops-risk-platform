import { useEffect, useRef, useState } from "react";
import { money, pct } from "../data/investorApi";
import type { MonteCarloResult } from "../data/monteCarloApi";
import type { RiskInput } from "../data/portfolioRiskApi";
import { xtbRequest } from "../data/xtbApi";
import "../styles/monteCarlo.css";

export function MonteCarloPanel({ portfolio, hasVariant }: { portfolio: RiskInput; hasVariant: boolean }) {
  const [days, setDays] = useState(252);
  const [simulations, setSimulations] = useState(5000);
  const [drift, setDrift] = useState("0");
  const [allocation, setAllocation] = useState("before");
  const [result, setResult] = useState<MonteCarloResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);
  function clear() { pending.current?.abort(); setResult(null); setError(""); setBusy(false); }
  async function run() {
    clear();
    const controller = new AbortController(); pending.current = controller; setBusy(true);
    try {
      const next = await xtbRequest<MonteCarloResult>("monte-carlo", {
        portfolio, days, simulations, seed: 42, annual_drift: Number(drift)/100, allocation,
      }, controller.signal);
      if (!controller.signal.aborted) setResult(next);
    } catch (reason) {
      if (!controller.signal.aborted) {
        const message = reason instanceof Error ? reason.message : "";
        setError(message.includes("252 aligned") ? "Potrzeba co najmniej 252 wspólnych obserwacji zwrotu."
          : message.includes("stale") ? "Odśwież ceny: ostatnia wycena jest starsza niż 7 dni."
          : message.includes("Work limit") ? "Zmniejsz liczbę scenariuszy lub horyzont dla tak dużego portfela."
          : message.includes("Build") || message.includes("native") || message.includes("ABI")
            ? "Moduł symulacji jest niedostępny na tym serwerze."
          : "Nie można przeprowadzić symulacji. Sprawdź kompletność historii i zakres portfela.");
      }
    } finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <section className="iv-panel qmc-panel" aria-label="Symulacja Monte Carlo" onChange={event => event.stopPropagation()}>
    <p className="iv-eyebrow">TYSIĄCE HIPOTETYCZNYCH SCENARIUSZY</p>
    <h2>Jak szeroki może być zakres wyników?</h2>
    <p>Symulujemy wspólne ruchy obecnych pozycji na podstawie historycznej zmienności i korelacji. To wyniki przy założeniach modelu, nie prognoza ani rekomendacja.</p>
    <div className="iv-form-grid">
      <label>Horyzont symulacji<select value={days} onChange={e => { clear(); setDays(Number(e.target.value)); }}><option value={21}>21 sesji · około miesiąca</option><option value={63}>63 sesje · około kwartału</option><option value={252}>252 sesje · około roku</option><option value={756}>756 sesji · około 3 lat</option></select></label>
      <label>Liczba scenariuszy<select value={simulations} onChange={e => { clear(); setSimulations(Number(e.target.value)); }}><option value={1000}>1 000</option><option value={5000}>5 000</option><option value={10000}>10 000</option></select></label>
      <label>Założony trend roczny<select value={drift} onChange={e => { clear(); setDrift(e.target.value); }}><option value="-10">−10%</option><option value="0">0% · bez zakładanego wzrostu</option><option value="5">+5%</option><option value="10">+10%</option></select></label>
      {hasVariant && <label>Badana alokacja<select value={allocation} onChange={e => { clear(); setAllocation(e.target.value); }}><option value="before">Obecny skład</option><option value="after">Zapisany wariant</option></select></label>}
    </div>
    <p className="iv-note">Trend jest jawnym założeniem dla aktywów, nie estymacją ich przyszłego zysku. Gotówka w walucie bazowej nie ma oprocentowania. Poziom ufności: {pct(Number(portfolio.confidence))}.</p>
    <button className="iv-button iv-primary" disabled={busy} onClick={() => void run()}>{busy ? "Symuluję scenariusze…" : "Uruchom Monte Carlo"}</button>
    {error && <p className="iv-alert iv-error" role="alert">{error}</p>}
    {result && <>
      <p className="iv-alert" role="status">{result.synthetic_input ? "DANE SYNTETYCZNE · " : ""}Wyniki hipotetyczne · {result.simulations.toLocaleString("pl-PL")} scenariuszy · {result.days} sesji · kapitał {money(result.initial_value,result.base_currency)}</p>
      <div className="qr-metric-grid">
        <article className="qr-metric"><span>Udział scenariuszy ze stratą</span><strong>{pct(result.probability_of_loss)}</strong><small>Na koniec horyzontu, przy założeniach modelu</small></article>
        <article className="qr-metric"><span>VaR {pct(result.confidence)} · próg straty</span><strong>{money(result.var_amount,result.base_currency)}</strong><small>Nie jest maksymalną możliwą stratą</small></article>
        <article className="qr-metric"><span>ES {pct(result.confidence)} · średnia strata w ogonie</span><strong>{money(result.es_amount,result.base_currency)}</strong><small>Dokładnie najgorsze {pct(1-result.confidence)} masy scenariuszy</small></article>
      </div>
      <MonteCarloChart result={result} />
      <p className="iv-note">Ujemna kwota VaR lub ES oznacza zysk w odpowiednim fragmencie rozkładu. Pasmo 5–95% dotyczy każdego punktu osobno; nie jest gwarancją przebiegu całej ścieżki.</p>
      <details><summary>Założenia, dane i odtwarzalność symulacji</summary>
        <p>Wycena: {result.valuation_date}. Kalibracja: {result.calibration_start} — {result.calibration_end}; {result.observations} wspólnych zwrotów. Seed: {result.seed}. Metoda: {result.methodology}.</p>
        <p>Model lognormalny, stała kowariancja, 252 sesje na rok. Brak rebalancingu, skoków cen, zmian reżimu zmienności, kosztów, podatków i ograniczeń płynności. FX zawiera się w historycznych zwrotach w walucie bazowej; nie jest losowany ponownie. Dywidendy są już ujęte w skorygowanych cenach. Więcej scenariuszy nie usuwa błędów założeń.</p>
        <button className="iv-button" onClick={() => {
          const url = URL.createObjectURL(new Blob([JSON.stringify({ inputs: { portfolio, days, simulations, annual_drift: Number(drift)/100, allocation, seed: 42 }, result },null,2)],{type:"application/json"}));
          const a=document.createElement("a");a.href=url;a.download="quantops-monte-carlo.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
        }}>Pobierz symulację z założeniami</button>
      </details>
    </>}
  </section>;
}

function MonteCarloChart({ result }: { result: MonteCarloResult }) {
  const [mode,setMode] = useState("paths");
  const [selected,setSelected] = useState(0);
  const host = useRef<HTMLDivElement>(null);
  const [width,setWidth] = useState(600);
  useEffect(() => {
    const observer = new ResizeObserver(entries => { const w=entries[0]?.contentRect.width; if(w) setWidth(w); });
    if(host.current) observer.observe(host.current);
    return () => observer.disconnect();
  },[]);
  const w=Math.max(width,260),h=290,left=72,right=w-16,top=18,bottom=235;
  const values = result.sample_paths.flat().map(Number).concat(result.bands.flatMap(b=>[Number(b.low),Number(b.high)]),Number(result.initial_value));
  const low=mode==="paths"?Math.min(...values):Math.min(...result.histogram.map(b=>Number(b.low)));
  const high=mode==="paths"?Math.max(...values):Math.max(...result.histogram.map(b=>Number(b.high)));
  const span=Math.max(high-low,1), ymin=Math.max(0,low-span*.05),ymax=high+span*.05;
  const y=(v:number)=>bottom-(v-ymin)/(ymax-ymin)*(bottom-top);
  const x=(day:number)=>left+day/result.days*(right-left);
  const line=(points:number[])=>points.map((v,i)=>(i?"L":"M")+x(result.bands[i]!.day)+","+y(v)).join(" ");
  const band=line(result.bands.map(b=>Number(b.high)))+" "+result.bands.slice().reverse().map(b=>"L"+x(b.day)+","+y(Number(b.low))).join(" ")+" Z";
  const histX=(v:number)=>left+(v-low)/span*(right-left);
  const countMax=Math.max(...result.histogram.map(b=>b.count),1);
  const point=result.bands[Math.min(selected,result.bands.length-1)]!;
  return <div className="qmc-chart" ref={host}>
    <label>Widok wyników<select value={mode} onChange={e=>setMode(e.target.value)}><option value="paths">Ścieżki i pasmo wyników</option><option value="histogram">Rozkład wartości końcowej</option></select></label>
    <svg viewBox={"0 0 "+w+" "+h} role="img" aria-label={mode==="paths"?"Ścieżki Monte Carlo i pasmo 5–95%":"Rozkład wartości końcowej Monte Carlo"}>
      <title>{mode==="paths"?"12 ścieżek, mediana oraz punktowe pasmo 5–95%":"Liczba scenariuszy w przedziałach wartości końcowej"}</title>
      <rect x={left} y={top} width={right-left} height={bottom-top} className="qmc-frame"/>
      {mode==="paths"?<>
        <path d={band} className="qmc-band"/>
        {result.sample_paths.map((p,i)=><path key={i} d={line(p.map(Number))} className="qmc-path"/>)}
        <path d={line(result.bands.map(b=>Number(b.median)))} className="qmc-median"/>
        <line x1={left} x2={right} y1={y(Number(result.initial_value))} y2={y(Number(result.initial_value))} className="qmc-reference"/>
        <line x1={x(point.day)} x2={x(point.day)} y1={top} y2={bottom} className="qmc-reference"/>
        {[0,1,2,3].map(i=><g key={i}><text x={left-8} y={top+(bottom-top)*i/3+4} textAnchor="end">{Math.round((ymax-(ymax-ymin)*i/3)/1000)} tys.</text><text x={left+(right-left)*i/3} y={bottom+22} textAnchor="middle">{Math.round(result.days*i/3)}</text></g>)}
      </>:<>
        {result.histogram.map((b,i)=><rect key={i} x={histX(Number(b.low))} y={bottom-b.count/countMax*(bottom-top)} width={Math.max(1,histX(Number(b.high))-histX(Number(b.low))-1)} height={b.count/countMax*(bottom-top)} className="qmc-bin"><title>{money(b.low,result.base_currency)} — {money(b.high,result.base_currency)}: {b.count} scenariuszy</title></rect>)}
        {[0,1,2,3].map(i=><g key={i}><text x={left-8} y={top+(bottom-top)*i/3+4} textAnchor="end">{Math.round(countMax*(1-i/3))}</text><text x={left+(right-left)*i/3} y={bottom+22} textAnchor="middle">{Math.round((low+span*i/3)/1000)} tys.</text></g>)}
      </>}
      <text x={(left+right)/2} y={h-9} textAnchor="middle">{mode==="paths"?"Sesje symulacji":"Wartość końcowa ("+result.base_currency+")"}</text>
      <text transform={"translate(15,"+(top+bottom)/2+") rotate(-90)"} textAnchor="middle">{mode==="paths"?"Wartość ("+result.base_currency+")":"Liczba scenariuszy"}</text>
    </svg>
    {mode==="paths"&&<><p className="iv-note">Pasmo: środkowe 90% · linia ciągła: mediana · cienkie linie: 12 przykładów · linia przerywana: kapitał początkowy / odczyt</p><label>Odczyt sesji Monte Carlo<input type="range" min={0} max={result.bands.length-1} value={selected} onChange={e=>setSelected(Number(e.target.value))}/></label><p role="status">Sesja {point.day}: mediana {money(point.median,result.base_currency)}; pasmo {money(point.low,result.base_currency)} — {money(point.high,result.base_currency)}.</p></>}
  </div>;
}
