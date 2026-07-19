import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../src/App";
import { DEMO_PORTFOLIO_ID } from "../src/data/demoAdapter";

function goTo(path: string) {
  window.history.replaceState({}, "", path);
}

afterEach(() => {
  cleanup();
  goTo("/");
});

describe("QuantOps frontend", () => {
  it("explains the product boundary and provides a keyboard-reachable demo entry", () => {
    goTo("/");
    render(<App />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("See the risk.Trace the reason.");
    expect(screen.getByText(/not investment advice/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /explore synthetic demo/i })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("link", { name: /skip to main content/i })).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("navigation", { name: /landing navigation/i })).toBeInTheDocument();
  });

  it("renders exact fixture risk numbers, method labels, and primary navigation", async () => {
    goTo("/dashboard");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Risk at a glance" })).toBeInTheDocument();
    expect(screen.getByText("$1,503,208.45")).toBeInTheDocument();
    const metrics = screen.getByRole("region", { name: "Latest risk metrics" });
    expect(within(metrics).getByText("Historical VaR")).toBeInTheDocument();
    expect(within(metrics).getByText("$7,964")).toBeInTheDocument();
    expect(within(metrics).getByText("Parametric VaR")).toBeInTheDocument();
    expect(within(metrics).getByText("$14,567")).toBeInTheDocument();
    expect(within(metrics).getByText("Expected Shortfall")).toBeInTheDocument();
    expect(within(metrics).getByText("$27,263")).toBeInTheDocument();
    expect(within(metrics).getByText("9.4%")).toBeInTheDocument();
    expect(within(metrics).getByText("3.6%")).toBeInTheDocument();
    expect(screen.getByText("Methodology version 1.0.0")).toBeInTheDocument();
    expect(screen.getByText("40 observations")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Portfolio" })).toHaveAttribute("href", `/portfolios/${DEMO_PORTFOLIO_ID}`);
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  });

  it("shows positions, correlation values, counts, and lineage on portfolio detail", async () => {
    goTo(`/portfolios/${DEMO_PORTFOLIO_ID}`);
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Synthetic Multi-Asset Research" })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /QTECH.*Equity index.*6,100.*95\.46.*582,289.*38\.7%.*Complete/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Correlation structure" })).toBeInTheDocument();
    expect(screen.getAllByTitle("520 observations").length).toBeGreaterThan(0);
    expect(screen.getByText("synthetic-market-data@1.0.0")).toBeInTheDocument();
    expect(screen.getByText("2,088 accepted")).toBeInTheDocument();
  });

  it.each([
    ["stale", "Stale replay watermark", /marked stale/i],
    ["partial", "Partial source coverage", /QWTI has partial source coverage/i],
    ["insufficient", "Insufficient history", /18 observations/i],
    ["offline", "Replay broker offline", /optional replay broker is offline/i],
  ])("renders the %s state with an explicit textual warning", async (mode, heading, warning) => {
    goTo(`/dashboard?state=${mode}`);
    render(<App />);

    const notice = await screen.findByRole("status");
    expect(within(notice).getByText(heading)).toBeInTheDocument();
    expect(within(notice).getByText(warning)).toBeInTheDocument();
  });

  it("renders loading, empty, and error resources without inventing values", async () => {
    goTo("/dashboard?state=loading");
    const loading = render(<App />);
    expect(screen.getByRole("heading", { name: "Loading deterministic fixture" })).toBeInTheDocument();
    expect(screen.getByText(/no external market service/i)).toBeInTheDocument();
    loading.unmount();

    goTo("/dashboard?state=empty");
    const empty = render(<App />);
    expect(await screen.findByRole("heading", { name: "No demo portfolio found" })).toBeInTheDocument();
    empty.unmount();

    goTo("/dashboard?state=error");
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("deterministic demo fixture could not be loaded");
  });

  it("validates custom scenario percentages and renders deterministic impacts", async () => {
    goTo(`/portfolios/${DEMO_PORTFOLIO_ID}/scenarios`);
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Explore hypothetical stress" })).toBeInTheDocument();

    const scenario = screen.getByLabelText("System scenario");
    fireEvent.change(scenario, { target: { value: "equity_selloff_15pct" } });
    expect(screen.getByText("-$87,343.34")).toBeInTheDocument();
    expect(screen.getByText("$1,415,865.11")).toBeInTheDocument();

    fireEvent.change(scenario, { target: { value: "custom" } });
    const shock = screen.getByLabelText("QTECH price shock (%)");
    fireEvent.change(shock, { target: { value: "101" } });
    expect(screen.getByRole("alert")).toHaveTextContent("between −100% and +100%");
    expect(screen.getByText(/correct the shock percentage/i)).toBeInTheDocument();

    fireEvent.change(shock, { target: { value: "-12.5" } });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("-$72,786.11")).toBeInTheDocument();
    expect(screen.getByText("(-4.8%)")).toBeInTheDocument();
    const exportLink = screen.getByRole("link", { name: "Export JSON" });
    expect(exportLink).toHaveAttribute("download", "scn-custom-local-preview.json");
    const exportHref = exportLink.getAttribute("href");
    expect(exportHref).not.toBeNull();
    const exportJson = decodeURIComponent(exportHref!.split(",", 2)[1]!);
    expect(JSON.parse(exportJson)).toMatchObject({
      stressed_value_usd: 1_430_422.3359,
      impact_usd: -72_786.1142,
      is_synthetic: true,
    });
    expect(screen.getByText(/without treating them as forecasts or trading signals/i)).toBeInTheDocument();
  });

  it("makes brief citations clickable and displays fallback and refusal boundaries", async () => {
    goTo(`/portfolios/${DEMO_PORTFOLIO_ID}/briefs`);
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Latest bounded risk brief" })).toBeInTheDocument();
    expect(screen.getByText(/deterministic fallback/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "[1]" })).toHaveAttribute("href", "#evidence-risk-001");
    expect(screen.getByRole("heading", { name: "Buy/sell recommendation refused" })).toBeInTheDocument();
    expect(screen.getByText(/no hidden prompts or private reasoning/i)).toBeInTheDocument();
  });

  it("shows pipeline quarantine, market replay, model, audit, methodology, and architecture truthfully", async () => {
    goTo("/pipelines");
    const pipelines = render(<App />);
    expect(await screen.findByRole("heading", { name: "Pipelines & data quality" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "OHLC_INVALID" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "BAR_MISSING" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "EVENT_LATE" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "EVENT_DUPLICATE" })).toBeInTheDocument();
    pipelines.unmount();

    goTo("/market");
    const market = render(<App />);
    expect(await screen.findByRole("heading", { name: "Prices & replay status" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /stopped.*historical batch available/i })).toBeInTheDocument();
    expect(screen.getByText(/no live feed is connected/i)).toBeInTheDocument();
    market.unmount();

    goTo("/models");
    const models = render(<App />);
    expect(screen.getByRole("heading", { name: "Regime evaluation, not market prediction" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Automated demo policy retained rule-baseline-v1" })).toBeInTheDocument();
    expect(screen.getByText("rejected_by_automated_demo_policy")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Operational drift detected" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "MLflow disabled" })).toBeInTheDocument();
    expect(screen.getByText(/not price direction or investment return/i)).toBeInTheDocument();
    models.unmount();

    goTo("/audit");
    const audit = render(<App />);
    expect(screen.getByRole("heading", { name: "Recorded actions, bounded detail" })).toBeInTheDocument();
    expect(screen.getByText("brief.request.refused")).toBeInTheDocument();
    expect(screen.getByText(/does not render credentials/i)).toBeInTheDocument();
    audit.unmount();

    goTo("/methodology");
    const methodology = render(<App />);
    expect(screen.getByRole("heading", { name: "Risk methods, without a black box" })).toBeInTheDocument();
    expect(screen.getByText(/no LLM calculations/i)).toBeInTheDocument();
    methodology.unmount();

    goTo("/architecture");
    render(<App />);
    expect(screen.getByRole("heading", { name: "Inward dependencies. Outward evidence." })).toBeInTheDocument();
    expect(screen.getByText(/no brokerage connection/i)).toBeInTheDocument();
  });
});
