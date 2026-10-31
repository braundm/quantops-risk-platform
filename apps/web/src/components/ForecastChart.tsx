/** Chart for the forecast quiz: history to NOW, optional revealed future. */

export function ForecastChart({
  history,
  future,
  title,
}: {
  readonly history: number[];
  readonly future?: number[];
  readonly title: string;
}) {
  if (history.length < 2) return <p className="qo-muted">Za mało obserwacji historii.</p>;

  const futureSeries = future ?? [];
  const revealed = futureSeries.length > 0;
  const values = revealed ? [...history, ...futureSeries] : history;
  const nowIndex = history.length - 1;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || Math.max(1, max * 0.05);
  const low = min - range * 0.08;
  const high = max + range * 0.08;
  const left = 48;
  const right = 660;
  const top = 28;
  const bottom = 190;
  const totalSteps = revealed ? values.length - 1 : history.length - 1 + Math.max(futureSeries.length || 20, 1);
  const xAt = (index: number) => left + (index / totalSteps) * (right - left);
  const yAt = (value: number) => bottom - ((value - low) / (high - low)) * (bottom - top);
  const histPath = history
    .map((value, index) => `${index === 0 ? "M" : "L"}${xAt(index).toFixed(2)},${yAt(value).toFixed(2)}`)
    .join(" ");
  const futurePath = revealed
    ? futureSeries
        .map((value, index) => {
          const i = history.length + index;
          return `${index === 0 ? `M${xAt(nowIndex).toFixed(2)},${yAt(history[nowIndex]!).toFixed(2)} L` : "L"}${xAt(i).toFixed(2)},${yAt(value).toFixed(2)}`;
        })
        .join(" ")
    : "";
  const shadeRight = xAt(totalSteps);
  const number = (n: number) => new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 0 }).format(n);

  return (
    <div className="qo-line-chart qo-forecast-chart">
      <svg viewBox="0 0 690 235" role="img" aria-label={title}>
        <title>{title}</title>
        {[0, 0.5, 1].map((fraction) => {
          const y = bottom - fraction * (bottom - top);
          return (
            <g key={fraction}>
              <line x1={left} x2={right} y1={y} y2={y} stroke="#e3eae7" strokeDasharray="3 5" />
              <text x={left - 8} y={y + 4} textAnchor="end" fill="#60756e" fontSize="11">
                {number(low + fraction * (high - low))}
              </text>
            </g>
          );
        })}
        {!revealed ? (
          <rect
            x={xAt(nowIndex)}
            y={top}
            width={Math.max(0, shadeRight - xAt(nowIndex))}
            height={bottom - top}
            fill="#8aa396"
            opacity="0.08"
          />
        ) : null}
        <path d={histPath} stroke="#237b62" strokeWidth="2.6" fill="none" strokeLinejoin="round" strokeLinecap="round" />
        {revealed ? (
          <path d={futurePath} stroke="#c0782a" strokeWidth="2.6" fill="none" strokeLinejoin="round" strokeLinecap="round" />
        ) : null}
        <line
          x1={xAt(nowIndex)}
          x2={xAt(nowIndex)}
          y1={top}
          y2={bottom}
          stroke="#6b8578"
          strokeDasharray="4 4"
        />
        <circle cx={xAt(nowIndex)} cy={yAt(history[nowIndex]!)} r="4.5" fill="#237b62" stroke="#fff" strokeWidth="2" />
        <text x={left} y={220} fill="#60756e" fontSize="11">−6 mies.</text>
        <text x={xAt(nowIndex)} y={220} textAnchor="middle" fill="#335845" fontSize="11" fontWeight="700">TERAZ</text>
        <text x={right} y={220} textAnchor="end" fill="#60756e" fontSize="11">+1 mies.</text>
      </svg>
    </div>
  );
}
