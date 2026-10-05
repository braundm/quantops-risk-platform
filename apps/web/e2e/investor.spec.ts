import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("sourced investor workspace, readable charts and accessible navigation", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Twój portfel. Pełniejszy obraz." })).toBeVisible();
  await expect(page.locator(".iv-position-card")).toHaveCount(6);
  await expect(page.locator(".iv-provenance")).toContainText("Fikcyjne transakcje");
  await expect(page.locator(".iv-provenance")).toContainText("Yahoo Finance");
  await page.screenshot({ path: `../../artifacts/investor-overview-${testInfo.project.name}.png`, fullPage: true });
  const tabs = ["Przegląd", "Portfel i transakcje", "Dywersyfikacja", "Ryzyko i zwrot", "Scenariusze", "Budżet i koszty", "Nauka", "Dane i ustawienia"];
  for (const tab of tabs) {
    await page.getByRole("link", { name: tab, exact: true }).click();
    await expect(page.locator("h1")).toHaveCount(1);
    const audit = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(audit.violations, `${tab}: ${JSON.stringify(audit.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })))}`).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await page.getByRole("link", { name: "Ryzyko i zwrot", exact: true }).click();
  await page.screenshot({ path: `../../artifacts/investor-risk-${testInfo.project.name}.png`, fullPage: true });
  await expect(page.getByRole("heading", { name: "Mapa zwrotu i wahań" })).toBeVisible();
  await page.getByRole("link", { name: "Portfel i transakcje", exact: true }).click();
  await page.getByRole("button", { name: "Apple", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Apple", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Pozycje portfela" })).toContainText("2025-04-01");
});

test("transactions, saved scenarios and backup survive reload", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".iv-position-card")).toHaveCount(6);
  await page.getByRole("link", { name: "Portfel i transakcje", exact: true }).click();
  await page.getByLabel("Rodzaj wpisu").selectOption("fee");
  await page.getByLabel("Data wpisu").fill("2026-09-01");
  await page.getByLabel("Kwota przepływu (PLN)").fill("123");
  await page.getByRole("button", { name: "Dodaj i przelicz" }).click();
  await expect(page.getByRole("heading", { name: "Historia · 8 wpisów" })).toBeVisible();
  await page.getByRole("link", { name: "Scenariusze", exact: true }).click();
  await page.getByLabel("Nazwa scenariusza").fill("Mój test trwałości");
  await page.getByRole("button", { name: "Zapisz scenariusz", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Mój test trwałości", exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Mój test trwałości", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Dane i ustawienia", exact: true }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Pobierz pełną kopię JSON" }).click();
  const saved = await download;
  const stream = await saved.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk as Uint8Array));
  const content = Buffer.concat(chunks);
  const parsed = JSON.parse(content.toString()) as { workspace: { transactions: unknown[] } };
  expect(parsed.workspace.transactions).toHaveLength(8);
  await page.getByRole("button", { name: "Usuń dane centrum portfela" }).click();
  await page.getByRole("button", { name: "Potwierdzam usunięcie" }).click();
  await expect.poll(() => page.evaluate(() => localStorage.getItem("quantops.investor-workspace.v1"))).toBeNull();
  await page.getByLabel("Przywróć kopię JSON").setInputFiles({ name: "backup.json", mimeType: "application/json", buffer: content });
  await page.getByRole("button", { name: "Zatwierdź przywrócenie portfela" }).click();
  await page.getByRole("link", { name: "Portfel i transakcje", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Historia · 8 wpisów" })).toBeVisible();
});

test("CSV duplicate import cannot overwrite the last valid saved portfolio", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".iv-position-card")).toHaveCount(6);
  await page.getByRole("link", { name: "Portfel i transakcje", exact: true }).click();
  const previous = await page.evaluate(() => localStorage.getItem("quantops.investor-workspace.v1"));
  const row = "00000000-0000-4000-8000-000000000001,2025-04-01,deposit,,0,0,1000,0,user\n";
  await page.getByLabel("Treść transakcji CSV").fill("id,date,action,symbol,quantity,price,amount_pln,fee_pln,source\n" + row + row);
  await page.getByRole("button", { name: "Sprawdź import" }).click();
  await expect(page.getByRole("button", { name: "Zatwierdź import transakcji" })).toBeDisabled();
  expect(await page.evaluate(() => localStorage.getItem("quantops.investor-workspace.v1"))).toBe(previous);
  await page.getByRole("link", { name: "Dane i ustawienia", exact: true }).click();
  await page.route("**/api/v1/investor/refresh", (route) => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Provider unavailable" }) }));
  await page.getByRole("button", { name: "Odśwież ceny z dostawcy" }).click();
  await expect(page.getByRole("alert")).toContainText("Provider unavailable");
  expect(await page.evaluate(() => localStorage.getItem("quantops.investor-workspace.v1"))).toBe(previous);
});
