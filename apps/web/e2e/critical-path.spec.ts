import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const portfolioId = "11111111-1111-4111-8111-111111111111";

const auditedPages = [
  { name: "landing", path: "/" },
  { name: "dashboard", path: "/dashboard" },
  { name: "scenario lab", path: `/portfolios/${portfolioId}/scenarios` },
  { name: "grounded brief", path: `/portfolios/${portfolioId}/briefs` },
  { name: "model and drift", path: "/models" },
  { name: "pipeline quality", path: "/pipelines" },
] as const;

async function expectNoWcagViolations(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();

  const summary = result.violations
    .map((violation) => {
      const targets = violation.nodes.map((node) => node.target.join(" > ")).join(", ");
      return `${violation.id}: ${targets}`;
    })
    .join("\n");

  expect(result.violations.length, summary).toBe(0);
}

test.describe("accessibility smoke", () => {
  for (const auditedPage of auditedPages) {
    test(`${auditedPage.name} has no automated WCAG A/AA violations`, async ({ page }) => {
      await page.goto(auditedPage.path);
      await expect(page.locator("#main-content")).toBeVisible();
      await expect(page.locator("h1")).toHaveCount(1);
      await expectNoWcagViolations(page);
    });
  }
});

test("keyboard entry, scenario result, and evidence citation remain navigable", async ({ page }) => {
  await page.goto("/");

  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  await page.keyboard.press("Tab");
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();

  await page.getByRole("link", { name: "Explore synthetic demo" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Risk at a glance" })).toBeVisible();
  await expect(page.getByText("$1,503,208.45")).toBeVisible();

  await page.getByRole("link", { name: "Run scenario" }).click();
  await page.getByLabel("System scenario").selectOption("combined_liquidity_stress");
  await expect(page.getByText("-$168,940.02")).toBeVisible();
  await expect(page.getByText("$1,334,268.43")).toBeVisible();
  await expect(page.getByText(/hypothetical sensitivity results, not predictions/i)).toBeVisible();

  await page.getByRole("link", { name: "Evidence", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Latest bounded risk brief" })).toBeVisible();
  await expect(page.getByRole("link", { name: "[1]" })).toHaveAttribute(
    "href",
    "#evidence-risk-001",
  );
  await expect(page.getByRole("heading", { name: "Buy/sell recommendation refused" })).toBeVisible();
});
