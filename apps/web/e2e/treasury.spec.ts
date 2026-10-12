import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("Treasury sensitivity, report and invalidation work on desktop and mobile", async ({ page }) => {
  await page.goto("/treasury");
  await expect(page.getByRole("heading", { name: "Treasury and liquidity lab" })).toBeVisible();
  await expect(page.getByText("SYNTHETIC EXAMPLE · UNVERIFIED INPUTS", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Calculate risk" }).click();
  const results = page.getByRole("region", { name: "Treasury results", exact: true });
  await expect(results).toContainText("treasury@1.0.0");
  await expect(results).toContainText("Estimated days: 8");
  await expect(page.getByRole("region", { name: "Rate shock table" })).toContainText("+200 bp");
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export HTML report" }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe("quantops-treasury-report.html");
  if (process.env.QUANTOPS_CAPTURE_TREASURY === "1" && test.info().project.name === "desktop-chromium") {
    await results.screenshot({ path: "../../docs/images/quantops-treasury-lab.png" });
    if (process.env.QUANTOPS_TREASURY_REPORT_PATH) await download.saveAs(process.env.QUANTOPS_TREASURY_REPORT_PATH);
  }
  const audit = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(audit.violations).toEqual([]);
  await page.getByRole("button", { name: "Offsetting sensitivities" }).click();
  await expect(results).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Export HTML report" })).toBeDisabled();
  await page.getByRole("button", { name: "Calculate risk" }).click();
  await expect(results).toContainText("Absolute net DV01 limit: OK");
  await page.getByLabel("Volume sessions", { exact: false }).fill("");
  await expect(results).toHaveCount(0);
  await page.getByRole("button", { name: "Calculate risk" }).click();
  await expect(results).toContainText("INSUFFICIENT");
  await expect(results).toContainText("Estimated days: Unavailable");
});

test("Treasury rejects malformed volume and shows service failures", async ({ page }) => {
  await page.goto("/treasury");
  await page.getByLabel("Volume sessions", { exact: false }).fill("2026-10-01,10,extra");
  await page.getByRole("button", { name: "Calculate risk" }).click();
  await expect(page.getByRole("alert")).toContainText("exactly a date and volume");
  await page.getByRole("button", { name: "Long duration" }).click();
  await page.route("**/api/v1/treasury/analyze", route => route.fulfill({ status: 503, json: { detail: "Analysis temporarily unavailable" } }));
  await page.getByRole("button", { name: "Calculate risk" }).click();
  await expect(page.getByRole("alert")).toContainText("Analysis temporarily unavailable");
  await expect(page.getByRole("button", { name: "Export HTML report" })).toBeDisabled();
});
