import { useId, useState } from "react";

export function RetailChart({ values, labels, currency, title, compact = false }: {
  values: number[]; labels?: string[]; currency?: string; title: string; compact?: boolean;
}) {
  const id = useId().replaceAll(":", "");
  const [selected, setSelected] = useState<number | null>(null);
  if (values.length < 2) return <p className="qo-muted">Potrzebne są co najmniej dwie obserwacje.</p>;
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || Math.max(1, max * 0.05);
  const low = min - range * 0.12, high = max + range * 0.12;
  const point = (i: number) => [56 + i / (values.length - 1) * 604, 190 - (values[i]! - low) / (high - low) * 160];
  const path = values.map((_, i) => `${i === 0 ? "M" : "L"}${point(i).join(",")}`).join(" ");
  const number = (n: number) => new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 0 }).format(n);
  const active = Math.min(selected ?? values.length - 1, values.length - 1);
  return <div className={`qo-line-chart ${compact ? "qo-chart-compact" : ""}`}>
    <div className="qo-chart-readout"><span>{labels?.[active] ?? `Obserwacja ${active + 1}`}</span><strong>{number(values[active]!)} {currency ?? "pkt"}</strong></div>
    <svg viewBox="0 0 690 235" role="img" aria-label={title}>
      <title>{title}</title>
      <defs><linearGradient id={id} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#4b9b82" stopOpacity=".24" /><stop offset="100%" stopColor="#4b9b82" stopOpacity="0" /></linearGradient></defs>
      {[0, 0.5, 1].map((fraction) => {
        const y = 190 - fraction * 160;
        return <g key={fraction}><line x1="56" x2="660" y1={y} y2={y} stroke="#e3eae7" strokeDasharray="3 5" /><text x="46" y={y + 4} textAnchor="end" fill="#60756e" fontSize="11">{number(low + fraction * (high - low))}</text></g>;
      })}
      <path d={`${path} L660,195 L56,195 Z`} fill={`url(#${id})`} />
      <path d={path} stroke="#237b62" strokeWidth="2.8" fill="none" strokeLinejoin="round" strokeLinecap="round" />
      <line x1={point(active)[0]} x2={point(active)[0]} y1="28" y2="195" stroke="#91b3a5" strokeDasharray="3 4" />
      <circle cx={point(active)[0]} cy={point(active)[1]} r="4.5" fill="#237b62" stroke="#fff" strokeWidth="2" />
      <text x="56" y="225" fill="#60756e" fontSize="11">{labels?.[0] ?? "Początek"}</text>
      <text x="660" y="225" textAnchor="end" fill="#60756e" fontSize="11">{labels?.at(-1) ?? "Ostatnia dostępna obserwacja"}</text>
    </svg>
    {!compact ? <label className="qo-chart-slider">Odczyt wykresu<input aria-label={`Odczyt: ${title}`} type="range" min="0" max={values.length - 1} value={active} onChange={(e) => setSelected(Number(e.target.value))} /></label> : null}
  </div>;
}
