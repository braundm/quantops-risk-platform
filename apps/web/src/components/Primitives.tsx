import type { ReactNode } from "react";

import type { DemoMode, RiskHistoryPoint, RiskMetric } from "../data/demoAdapter";
import { formatCurrency, formatDate, formatPercent } from "../lib/format";

interface PageHeadingProps {
  readonly eyebrow: string;
  readonly title: string;
  readonly description: string;
  readonly actions?: ReactNode;
}

export function PageHeading({ eyebrow, title, description, actions }: PageHeadingProps) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions === undefined ? null : <div className="page-actions">{actions}</div>}
    </header>
  );
}

interface BadgeProps {
  readonly tone?: "good" | "warning" | "danger" | "neutral" | "accent";
  readonly children: ReactNode;
}

export function Badge({ tone = "neutral", children }: BadgeProps) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function MetricCard({ metric }: { readonly metric: RiskMetric }) {
  const formatted =
    metric.value === null
      ? "Not available"
      : metric.kind === "currency"
        ? formatCurrency(metric.value)
        : formatPercent(metric.value);
  return (
    <article className="metric-card">
      <div className="metric-label">
        <span>{metric.label}</span>
        <span className="info-dot" title={metric.description} aria-label={metric.description}>
          i
        </span>
      </div>
      <strong className={metric.value === null ? "metric-unavailable" : undefined}>{formatted}</strong>
      <small>{metric.status === "valid" ? "95% · 1 day" : "Insufficient history"}</small>
    </article>
  );
}

interface StateNoticeProps {
  readonly mode: DemoMode;
  readonly warnings: readonly string[];
}

export function StateNotice({ mode, warnings }: StateNoticeProps) {
  if (warnings.length === 0) return null;
  const heading =
    mode === "partial"
      ? "Partial source coverage"
      : mode === "stale"
        ? "Stale replay watermark"
        : mode === "offline"
          ? "Replay broker offline"
          : "Insufficient history";
  return (
    <section className="state-notice" aria-labelledby="state-notice-title" role="status">
      <span className="notice-icon" aria-hidden="true">
        !
      </span>
      <div>
        <strong id="state-notice-title">{heading}</strong>
        {warnings.map((warning) => (
          <p key={warning}>{warning}</p>
        ))}
      </div>
    </section>
  );
}

export function LoadingState() {
  return (
    <section className="resource-state" aria-live="polite" aria-busy="true">
      <span className="loader" aria-hidden="true" />
      <h1>Loading deterministic fixture</h1>
      <p>Reading the versioned local dataset. No external market service is contacted.</p>
      <div className="skeleton-row" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </section>
  );
}

export function EmptyState() {
  return (
    <section className="resource-state">
      <span className="empty-mark" aria-hidden="true">0</span>
      <h1>No demo portfolio found</h1>
      <p>Generate or seed the deterministic synthetic fixture, then reload this view.</p>
      <a className="button button-secondary" href="/architecture">
        Review data flow
      </a>
    </section>
  );
}

export function ErrorState({ message }: { readonly message: string }) {
  return (
    <section className="resource-state resource-error" role="alert">
      <span className="empty-mark" aria-hidden="true">!</span>
      <h1>Demo data unavailable</h1>
      <p>{message}</p>
      <a className="button button-secondary" href="/dashboard">
        Retry fixture
      </a>
    </section>
  );
}

interface LineChartProps {
  readonly points: readonly RiskHistoryPoint[];
  readonly value: "portfolioValue" | "historicalVar";
  readonly label: string;
  readonly color?: "accent" | "amber";
}

export function LineChart({ points, value, label, color = "accent" }: LineChartProps) {
  const values = points.map((point) => point[value]);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const range = maximum - minimum || 1;
  const width = 620;
  const height = 180;
  const padding = 10;
  const coordinates = values.map((entry, index) => {
    const x = padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
    const y = height - padding - ((entry - minimum) / range) * (height - padding * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const area = `${padding},${height - padding} ${coordinates.join(" ")} ${width - padding},${height - padding}`;

  return (
    <figure className="line-chart">
      <svg role="img" aria-labelledby={`${value}-title ${value}-description`} viewBox={`0 0 ${width} ${height}`}>
        <title id={`${value}-title`}>{label}</title>
        <desc id={`${value}-description`}>
          {`${formatDate(points[0]?.date ?? "2024-01-01")}: ${formatCurrency(values[0] ?? 0)}; ${formatDate(points.at(-1)?.date ?? "2024-01-01")}: ${formatCurrency(values.at(-1) ?? 0)}.`}
        </desc>
        <defs>
          <linearGradient id={`${value}-fill`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color === "accent" ? "#4fd1c5" : "#f2b84b"} stopOpacity="0.25" />
            <stop offset="100%" stopColor={color === "accent" ? "#4fd1c5" : "#f2b84b"} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3].map((line) => (
          <line className="chart-gridline" key={line} x1="10" x2="610" y1={10 + line * 53} y2={10 + line * 53} />
        ))}
        <polygon fill={`url(#${value}-fill)`} points={area} />
        <polyline className={`chart-line chart-line-${color}`} points={coordinates.join(" ")} />
        {coordinates.map((coordinate, index) => {
          const [x = "0", y = "0"] = coordinate.split(",");
          return <circle className={`chart-point chart-point-${color}`} cx={x} cy={y} key={coordinate} r={index === coordinates.length - 1 ? 4 : 2} />;
        })}
      </svg>
      <figcaption>
        <span>{formatDate(points[0]?.date ?? "2024-01-01")}</span>
        <span>{formatDate(points.at(-1)?.date ?? "2024-01-01")}</span>
      </figcaption>
      <details>
        <summary>View chart values</summary>
        <ul>
          {points.map((point) => (
            <li key={point.date}>
              {formatDate(point.date)}: {formatCurrency(point[value])}
            </li>
          ))}
        </ul>
      </details>
    </figure>
  );
}
