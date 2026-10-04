import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("historical risk, insufficient sample and accessible chart", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Wczytaj syntetyczną historię demo" }).click();
  await expect(page.locator(".qo-history-status")).toContainText("Obliczono · 339");
  await expect(page.locator(".qo-risk-strip").first()).toContainText("2118");
  await page.getByLabel("Odczyt: Historyczna symulacja wartości obecnych pozycji").fill("10");
  await page.locator("#risk").screenshot({ path: `../../artifacts/risk-${testInfo.project.name}.png` });
  const result = await new AxeBuilder({ page }).include("#risk").withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(result.violations).toEqual([]);
  await page.getByLabel("Poziom ufności").selectOption("0.99");
  await expect(page.locator(".qo-risk-strip")).toHaveCount(0);
  await page.getByRole("button", { name: "Uruchom analizę ryzyka" }).click();
  await expect(page.locator(".qo-history-status")).toContainText("Niewystarczająca historia");
  await expect(page.locator(".qo-history-status")).toContainText("wymagane 500");
  await expect(page.locator(".qo-risk-strip article strong").first()).toHaveText("—");
});

test("education reveals ten decisions and costs only after commitment", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Rozpocznij ćwiczenie" }).click();
  await expect(page.locator(".qo-lab-progress")).toContainText("Próby: 0 / 10");
  await expect(page.locator("#lab .qo-chart-readout")).toContainText("Obserwacja 40");
  for (let step = 1; step <= 10; step++) {
    await page.getByRole("button", { name: "Brak transakcji · odsłoń" }).click();
    await expect(page.locator(".qo-lab-progress")).toContainText(`Próby: ${step} / 10`);
    await expect(page.locator("#lab .qo-chart-readout")).toContainText(`Obserwacja ${40 + 5 * step}`);
  }
  await expect(page.getByRole("heading", { name: "Ćwiczenie zakończone" })).toBeVisible();
  await expect(page.locator(".qo-lab-stats article").nth(1).locator("strong")).toHaveText("0%");
});

test("cost exclusions, preference consistency and session data removal", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".qo-hedge-cards article")).toHaveCount(3);
  await page.getByLabel("Kwota kosztu (PLN)").fill("10");
  await page.getByLabel("Okres opłaty").selectOption("monthly");
  await page.getByRole("button", { name: "Dodaj koszt", exact: true }).click();
  await expect(page.locator(".qo-cost-totals")).toContainText("120,00");
  await page.getByLabel("Kwota kosztu (PLN)").fill("100");
  await page.getByLabel("Już zawarty w cenach produktu").check();
  await page.getByRole("button", { name: "Dodaj koszt", exact: true }).click();
  await expect(page.locator(".qo-cost-totals")).toContainText("1 opłat");
  await expect(page.locator(".qo-cost-totals")).toContainText("120,00");
  await page.getByLabel("Tolerowana strata w pieniądzu").fill("20000");
  await page.getByRole("button", { name: "Sprawdź odpowiedzi i zastosuj limit" }).click();
  await expect(page.locator(".qo-preference-review")).toContainText("niespójne");
  await expect(page.locator(".qo-preference-review")).toContainText("przekracza finansową zdolność");
  await page.getByRole("button", { name: "Usuń moje dane" }).click();
  await expect(page.locator(".qo-cost-list")).toHaveCount(0);
  await expect(page.locator(".qo-preference-review")).toHaveCount(0);
  await expect(page.getByLabel("Tolerowana strata w pieniądzu")).toHaveValue("0");
});
