import { useEffect, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "./components/Primitives";
import { Shell } from "./components/Shell";
import {
  localDemoAdapter,
  parseDemoMode,
  type DemoMode,
  type DemoResult,
} from "./data/demoAdapter";
import { ArchitecturePage } from "./pages/ArchitecturePage";
import { DashboardPage } from "./pages/DashboardPage";
import { EvidencePage } from "./pages/EvidencePage";
import { LandingPage } from "./pages/LandingPage";
import { MethodologyPage } from "./pages/MethodologyPage";
import { AuditPage, MarketPage, ModelsPage } from "./pages/OperationalPages";
import { PipelinePage } from "./pages/PipelinePage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { ScenarioPage } from "./pages/ScenarioPage";

type DataRoute = "dashboard" | "portfolio" | "scenarios" | "pipelines" | "evidence" | "briefs" | "market";

type ResourceState =
  | { readonly kind: "loading" }
  | { readonly kind: "error"; readonly message: string }
  | { readonly kind: "ready"; readonly result: DemoResult };

function useDemoData(mode: DemoMode): ResourceState {
  const [state, setState] = useState<ResourceState>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    setState({ kind: "loading" });
    void localDemoAdapter
      .load(mode)
      .then((result) => {
        if (active) setState({ kind: "ready", result });
      })
      .catch((error: unknown) => {
        if (!active) return;
        const message = error instanceof Error ? error.message : "An unknown local adapter error occurred.";
        setState({ kind: "error", message });
      });
    return () => {
      active = false;
    };
  }, [mode]);

  return state;
}

function DataPage({ mode, route }: { readonly mode: DemoMode; readonly route: DataRoute }) {
  const resource = useDemoData(mode);
  if (resource.kind === "loading") return <LoadingState />;
  if (resource.kind === "error") return <ErrorState message={resource.message} />;
  if (resource.result.data === null) return <EmptyState />;

  switch (route) {
    case "dashboard":
      return <DashboardPage result={resource.result} />;
    case "portfolio":
      return <PortfolioPage result={resource.result} />;
    case "scenarios":
      return <ScenarioPage result={resource.result} />;
    case "pipelines":
      return <PipelinePage result={resource.result} />;
    case "evidence":
    case "briefs":
      return <EvidencePage result={resource.result} />;
    case "market":
      return <MarketPage result={resource.result} />;
  }
}

function routeFor(path: string): DataRoute | "methodology" | "architecture" | "models" | "audit" | "not-found" {
  if (path === "/dashboard") return "dashboard";
  if (path === "/pipelines") return "pipelines";
  if (path === "/evidence") return "evidence";
  if (path === "/market") return "market";
  if (path === "/models") return "models";
  if (path === "/audit") return "audit";
  if (path === "/methodology") return "methodology";
  if (path === "/architecture") return "architecture";
  if (/^\/portfolios\/[^/]+\/scenarios\/?$/.test(path)) return "scenarios";
  if (/^\/portfolios\/[^/]+\/briefs\/?$/.test(path)) return "briefs";
  if (/^\/portfolios\/[^/]+\/?$/.test(path)) return "portfolio";
  return "not-found";
}

function NotFoundPage() {
  return (
    <section className="resource-state">
      <span className="empty-mark" aria-hidden="true">404</span>
      <h1>View not found</h1>
      <p>The requested QuantOps route is not part of this demo.</p>
      <a className="button button-primary" href="/dashboard">Open dashboard</a>
    </section>
  );
}

export function App() {
  const path = window.location.pathname.replace(/\/$/, "") || "/";
  if (path === "/") return <LandingPage />;

  const route = routeFor(path);
  const content = (() => {
    switch (route) {
      case "methodology":
        return <MethodologyPage />;
      case "architecture":
        return <ArchitecturePage />;
      case "models":
        return <ModelsPage />;
      case "audit":
        return <AuditPage />;
      case "not-found":
        return <NotFoundPage />;
      default:
        return <DataPage mode={parseDemoMode(window.location.search)} route={route} />;
    }
  })();

  return <Shell path={path}>{content}</Shell>;
}
