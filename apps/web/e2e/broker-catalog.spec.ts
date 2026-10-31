import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("Public catalog separates equities and CFDs and exposes missing coverage", async ({ page }) => {
  await page.goto("/instruments");
  await expect(page.getByRole("heading", { name: "Katalog instrumentów Bossa i XTB" })).toBeVisible();
  await page.getByLabel("Źródło", { exact: true }).selectOption("xtb");
  await page.getByLabel("Symbol, nazwa lub ISIN").fill("AAPL");
  await expect(page.getByRole("button", { name: "AAPL.US — xtb — equity", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "AAPL.US — xtb — cfd", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "AAPL.US — xtb — cfd", exact: true }).click();
  await expect(page.getByRole("region", { name: "Szczegóły instrumentu" })).toContainText("Analiza pochodnych wymaga");
  await page.getByLabel("Typ instrumentu").selectOption("option");
  await expect(page.getByText("Brak wpisów w pobranym zakresie.", { exact: false })).toBeVisible();
  await expect(page.getByRole("region", { name: "Szczegóły instrumentu" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Pokrycie źródeł" })).toContainText("BRAK POKRYCIA");
  const audit = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(audit.violations).toEqual([]);
});

test("Catalog pagination and service errors remain visible", async ({ page }) => {
  await page.goto("/instruments");
  await page.getByRole("button", { name: "Następna strona" }).click();
  await expect(page.getByRole("status")).toContainText("strona 2");
  await page.route("**/api/v1/broker-catalog?*", route => route.fulfill({ status: 503, json: { detail: "Unavailable" } }));
  await page.getByLabel("Symbol, nazwa lub ISIN").fill("Synthetic offline test");
  await expect(page.getByRole("alert")).toContainText("Katalog jest niedostępny");
  await expect(page.getByRole("region", { name: "Wyniki katalogu" })).toHaveCount(0);
});
