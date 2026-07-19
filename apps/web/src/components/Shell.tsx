import type { ReactNode } from "react";

import { DEMO_PORTFOLIO_ID } from "../data/demoAdapter";

interface NavigationItem {
  readonly href: string;
  readonly label: string;
  readonly group: "Research" | "Assurance";
  readonly icon: "grid" | "portfolio" | "scenario" | "market" | "model" | "pipeline" | "evidence" | "audit" | "method" | "architecture";
}

const navigation: readonly NavigationItem[] = [
  { href: "/dashboard", label: "Overview", group: "Research", icon: "grid" },
  {
    href: `/portfolios/${DEMO_PORTFOLIO_ID}`,
    label: "Portfolio",
    group: "Research",
    icon: "portfolio",
  },
  {
    href: `/portfolios/${DEMO_PORTFOLIO_ID}/scenarios`,
    label: "Scenarios",
    group: "Research",
    icon: "scenario",
  },
  { href: "/market", label: "Market data", group: "Research", icon: "market" },
  { href: "/models", label: "Models", group: "Research", icon: "model" },
  { href: "/pipelines", label: "Data quality", group: "Assurance", icon: "pipeline" },
  { href: "/evidence", label: "Evidence", group: "Assurance", icon: "evidence" },
  { href: "/audit", label: "Audit", group: "Assurance", icon: "audit" },
  { href: "/methodology", label: "Methodology", group: "Assurance", icon: "method" },
  { href: "/architecture", label: "Architecture", group: "Assurance", icon: "architecture" },
];

function Mark() {
  return (
    <svg aria-hidden="true" className="brand-mark" viewBox="0 0 40 40">
      <path d="M9 9h15a7 7 0 0 1 7 7v15H16a7 7 0 0 1-7-7V9Z" />
      <path d="m20 15 8 13m-12-2 11-7" />
    </svg>
  );
}

function NavIcon({ name }: { readonly name: NavigationItem["icon"] }) {
  const paths: Record<NavigationItem["icon"], ReactNode> = {
    grid: <path d="M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z" />,
    portfolio: <path d="M4 6h16v14H4zM8 6V3h8v3M4 11h16M10 15h4" />,
    scenario: <path d="M4 19V5m0 14h16M8 15l3-4 3 2 5-7" />,
    market: <path d="M3 18h18M5 15V9m5 6V5m5 10v-3m5 3V7" />,
    model: <path d="M12 3v4m0 10v4M3 12h4m10 0h4M6 6l3 3m6 6 3 3m0-12-3 3m-6 6-3 3M9 9h6v6H9z" />,
    pipeline: <path d="M4 5h6v6H4zm10 8h6v6h-6zM10 8h4a3 3 0 0 1 3 3v2" />,
    evidence: <path d="M6 3h9l4 4v14H6zM15 3v5h4M9 12h7m-7 4h7" />,
    audit: <path d="M12 3 4 6v6c0 5 3 8 8 10 5-2 8-5 8-10V6zM9 12l2 2 4-5" />,
    method: <path d="M5 4h14v16H5zM9 8h6m-6 4h6m-6 4h3" />,
    architecture: <path d="M9 3h6v5H9zM3 16h6v5H3zm12 0h6v5h-6zM12 8v4M6 16v-4h12v4" />,
  };
  return (
    <svg aria-hidden="true" className="nav-icon" viewBox="0 0 24 24">
      {paths[name]}
    </svg>
  );
}

interface ShellProps {
  readonly path: string;
  readonly children: ReactNode;
}

function isCurrent(path: string, href: string): boolean {
  if (href === "/dashboard") return path === href;
  return path === href;
}

export function Shell({ path, children }: ShellProps) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="QuantOps home">
          <Mark />
          <span>
            Quant<span>Ops</span>
          </span>
        </a>

        <div className="demo-identity" aria-label="Current environment">
          <span className="status-dot" aria-hidden="true" />
          <span>
            <strong>Synthetic demo</strong>
            <small>Historical replay · local</small>
          </span>
        </div>

        <nav aria-label="Primary navigation">
          {(["Research", "Assurance"] as const).map((group) => (
            <div className="nav-group" key={group}>
              <p>{group}</p>
              <ul>
                {navigation
                  .filter((item) => item.group === group)
                  .map((item) => (
                    <li key={item.href}>
                      <a
                        aria-current={isCurrent(path, item.href) ? "page" : undefined}
                        href={item.href}
                      >
                        <NavIcon name={item.icon} />
                        {item.label}
                      </a>
                    </li>
                  ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="sidebar-notice">
          <span aria-hidden="true">i</span>
          <p>Research and engineering use only. No investment advice or trade execution.</p>
        </div>
      </aside>

      <div className="app-column">
        <header className="topbar">
          <div>
            <span className="topbar-label">Environment</span>
            <strong>Deterministic fixture 1.0.0</strong>
          </div>
          <div className="topbar-actions">
            <a className="quiet-link" href="/evidence">
              View evidence
            </a>
            <span className="historical-label">Not live</span>
          </div>
        </header>
        <main id="main-content" tabIndex={-1}>
          {children}
        </main>
        <footer className="app-footer">
          <span>QuantOps synthetic market-risk observability</span>
          <span>All timestamps shown in UTC</span>
        </footer>
      </div>
    </div>
  );
}
