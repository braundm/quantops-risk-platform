import { useId, useRef, useState } from "react";
import { downloadInvestor, number, pct, type MarketPoint, type Position } from "../data/investorApi";

export const palette = ["#26775f", "#375d7e", "#8c4b20", "#665187", "#923c4b", "#386663"];

export function HistoryChart({ points, label, unit = "PLN" }: { points: { date: string; value: number }[]; label: string; unit?: string }) {
  const gradient = useId().replaceAll(":", "");
  const [selected, setSelected] = useState<number | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  if (points.length < 2) return <p className="iv-empty">Dodaj transakcje i co najmniej dwie wspólne daty notowań, aby zobaczyć wykres.</p>;
  const min = Math.min(...points.map((p) => p.value)), max = Math.max(...points.map((p) => p.value));
  const span = max - min || Math.max(1, Math.abs(max) * .1);
  const low = min - span * .1, high = max + span * .1;
  const x = (i: number) => 75 + i / (points.length - 1) * 620;
  const y = (value: number) => 210 - (value - low) / (high - low) * 175;
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.value)}`).join(" ");
  const active = Math.min(selected ?? points.length - 1, points.length - 1);
  return <div className="iv-chart">
    <div className="iv-chart-heading"><span>{points[active]!.date}<strong>{number(points[active]!.value)} {unit}</strong></span><button className="iv-text" onClick={() => { if (svg.current) downloadInvestor("QuantOps-wykres.svg", new XMLSerializer().serializeToString(svg.current), "image/svg+xml"); }}>Pobierz wykres SVG ↗</button></div>
    <svg ref={svg} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 730 250" role="img" aria-label={label}>
      <title>{label}</title><rect width="730" height="250" fill="#fff" />
      <defs><linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#3c957a" stopOpacity=".22" /><stop offset="100%" stopColor="#3c957a" stopOpacity="0" /></linearGradient></defs>
      {[0, .5, 1].map((f) => <g key={f}><line x1="75" x2="695" y1={y(low + (high - low) * f)} y2={y(low + (high - low) * f)} stroke="#dce7df" strokeDasharray="3 5" /><text x="65" y={y(low + (high - low) * f) + 4} textAnchor="end" fontSize="12" fill="#50675e">{number(low + (high - low) * f, 0)}</text></g>)}
      <path d={`${path} L695,215 L75,215 Z`} fill={`url(#${gradient})`} /><path d={path} stroke="#23755b" fill="none" strokeWidth="2.5" />
      <line x1={x(active)} x2={x(active)} y1="30" y2="215" stroke="#769184" strokeDasharray="3 4" /><circle cx={x(active)} cy={y(points[active]!.value)} r="4" fill="#23755b" stroke="#fff" strokeWidth="2" />
      <text x="75" y="245" fontSize="12" fill="#50675e">{points[0]!.date}</text><text x="695" y="245" fontSize="12" fill="#50675e" textAnchor="end">{points.at(-1)!.date}</text>
    </svg>
    <label className="iv-range">Odczyt wykresu<input aria-label={`Odczyt: ${label}`} type="range" min="0" max={points.length - 1} value={active} onChange={(e) => setSelected(Number(e.target.value))} /></label>
  </div>;
}

export function AllocationChart({ positions }: { positions: Position[] }) {
  let offset = 0;
  return <div className="iv-allocation"><svg viewBox="0 0 230 230" role="img" aria-label="Udział instrumentów w ekspozycji brutto, nie w wartości majątku">
    <title>Ekspozycja brutto według instrumentów</title><circle cx="115" cy="115" r="84" fill="none" stroke="#e6ece6" strokeWidth="27" />
    {positions.map((p, i) => { const before = offset; offset += p.weight; return <circle key={p.symbol} cx="115" cy="115" r="84" pathLength="100" fill="none" stroke={palette[i % palette.length]} strokeWidth="27" strokeDasharray={`${p.weight * 100} ${100 - p.weight * 100}`} strokeDashoffset={-before * 100} transform="rotate(-90 115 115)"><title>{p.name}: {pct(p.weight)}</title></circle>; })}
    <text x="115" y="110" textAnchor="middle" fill="#183b30" fontSize="30" fontWeight="600">{positions.length}</text><text x="115" y="135" textAnchor="middle" fill="#526b5e" fontSize="12">instrumentów</text>
  </svg><ul className="iv-legend">{positions.map((p, i) => <li key={p.symbol}><i style={{ background: palette[i % palette.length] }} /><span>{p.symbol.replace(".NYM", "").replace("=X", "")}</span><strong>{pct(p.weight)}</strong></li>)}</ul></div>;
}

export function RiskReturnChart({ points }: { points: MarketPoint[] }) {
  const [chosen, setChosen] = useState<string | null>(null);
  const selected = points.find((p) => p.symbol === chosen) ?? points[0];
  const maxX = Math.max(.1, ...points.map((p) => p.annual_volatility)) * 1.25;
  const minY = Math.min(0, ...points.map((p) => p.period_return)) - .08;
  const maxY = Math.max(.1, ...points.map((p) => p.period_return)) + .1;
  const x = (n: number) => 65 + n / maxX * 595;
  const y = (n: number) => 260 - (n - minY) / (maxY - minY) * 220;
  return <div className="iv-scatter"><svg viewBox="0 0 730 330" role="img" aria-label="Mapa historycznej zmiany ceny i zmienności. Niższa zmienność nie oznacza gwarancji bezpieczeństwa.">
    <title>Historyczny zwrot ceny a zmienność, wspólna próba</title>
    {[0, .25, .5, .75, 1].map((f) => <g key={f}><line x1={x(f * maxX)} x2={x(f * maxX)} y1="40" y2="260" stroke="#e0e8df" /><text x={x(f * maxX)} y="284" textAnchor="middle" fill="#526b5e" fontSize="11">{pct(f * maxX)}</text><line x1="65" x2="660" y1={y(minY + f * (maxY - minY))} y2={y(minY + f * (maxY - minY))} stroke="#e0e8df" /><text x="54" y={y(minY + f * (maxY - minY)) + 4} textAnchor="end" fill="#526b5e" fontSize="11">{pct(minY + f * (maxY - minY))}</text></g>)}
    <line x1="65" x2="660" y1={y(0)} y2={y(0)} stroke="#839b8d" strokeDasharray="4 4" />
    {points.map((p, i) => <g key={p.symbol}><circle cx={x(p.annual_volatility)} cy={y(p.period_return)} r={selected?.symbol === p.symbol ? 10 : 7} fill={palette[i % palette.length]} stroke="#fff" strokeWidth="2"><title>{p.name}: zmiana {pct(p.period_return)}, zmienność {pct(p.annual_volatility)}</title></circle><text x={x(p.annual_volatility) + 13} y={y(p.period_return) + (i % 2 ? 17 : -10)} fill="#244d3e" fontSize="11">{p.symbol.replace(".NYM", "").replace("=X", "")}</text></g>)}
    <text x="65" y="21" fill="#526b5e" fontSize="12">Zmiana ceny w okresie ↑</text><text x="363" y="318" textAnchor="middle" fill="#526b5e" fontSize="12">Mniejsze wahania ← Zmienność roczna → Większe wahania</text>
  </svg><div className="iv-chips">{points.map((p) => <button key={p.symbol} aria-pressed={selected?.symbol === p.symbol} onClick={() => setChosen(p.symbol)}>{p.symbol.replace(".NYM", "").replace("=X", "")}</button>)}</div>
    {selected ? <p className="iv-explanation"><strong>{selected.name}:</strong> zmiana ceny {pct(selected.period_return)}, zmienność {pct(selected.annual_volatility)}. To opis historii, nie przewidywany wynik ani ocena „bezpieczne”. Akcje i ETF w PLN; forex i futures: zmiana notowania w USD, bez dźwigni.</p> : <p>Do porównania potrzebne jest co najmniej 60 wspólnych obserwacji.</p>}
  </div>;
}
