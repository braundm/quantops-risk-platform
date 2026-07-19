import { describe, expect, it } from "vitest";

import { demoBundle, localDemoAdapter, parseDemoMode } from "../src/data/demoAdapter";

describe("local deterministic data adapter", () => {
  it("keeps portfolio value and signed risk contributions reconciled", () => {
    const positionValue = demoBundle.portfolio.positions.reduce((sum, position) => sum + position.marketValue, 0);
    const riskContribution = demoBundle.portfolio.positions.reduce((sum, position) => sum + position.contribution, 0);

    expect(positionValue).toBeCloseTo(demoBundle.portfolio.value, 4);
    expect(riskContribution).toBeCloseTo(14_566.539654722888, 8);
    expect(demoBundle.portfolio.metrics.find((metric) => metric.label === "Parametric VaR")?.value).toBe(14_566.539654722888);
  });

  it("parses only supported deterministic state modes", () => {
    expect(parseDemoMode("?state=stale")).toBe("stale");
    expect(parseDemoMode("?state=partial")).toBe("partial");
    expect(parseDemoMode("?state=unknown")).toBe("normal");
    expect(parseDemoMode("")).toBe("normal");
  });

  it("removes untrustworthy risk values in insufficient-history mode", async () => {
    const result = await localDemoAdapter.load("insufficient");
    expect(result.data?.portfolio.metrics.every((metric) => metric.status === "insufficient_data")).toBe(true);
    expect(result.data?.portfolio.metrics.every((metric) => metric.value === null)).toBe(true);
    expect(result.warnings[0]).toMatch(/18 observations/);
  });
});
