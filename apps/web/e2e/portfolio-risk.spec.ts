import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import type { RiskResult } from "../src/data/portfolioRiskApi";

async function openRisk(page: Page, login = "admin1") {
  await page.goto("/");
  await page.getByLabel("Login", { exact: true }).fill(login);
  await page.getByLabel("Hasło", { exact: true }).fill(login);
  await page.getByRole("button", { name: "Otwórz mój portfel" }).click();
  await page.getByRole("navigation", { name: "Centrum portfela" }).getByRole("button", { name: "Analiza ryzyka", exact: true }).click();
  if (login === "admin1") await expect(page.getByRole("heading", { name: "Analiza ryzyka portfela" })).toBeVisible();
}
const tab = (page: Page, name: string) => page.getByRole("tab", { name: new RegExp(name) });

async function loadExample(page: Page): Promise<RiskResult> {
  await page.getByRole("tabpanel").getByRole("button", { name: "Wczytaj przykład syntetyczny", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "Źródło portfela" })).toContainText("DANE SYNTETYCZNE");
  const response = page.waitForResponse(r => r.url().endsWith("/api/v1/xtb/risk"));
  await page.getByRole("button", { name: "Oblicz analizę i scenariusze", exact: true }).click();
  const data = await (await response).json() as RiskResult;
  await expect(page.getByRole("heading", { name: "Ogólny profil ryzyka", exact: true })).toBeVisible();
  return data;
}

test("equity dashboard has a sourced score, clickable concentration, correlation and drawdown tabs", async ({ page }, testInfo) => {
  await openRisk(page);
  await expect(page.getByRole("tab")).toHaveCount(7);
  await expect(tab(page,"Przegląd")).toHaveAttribute("aria-selected","true");
  await expect(page.getByRole("figure", { name: "Indeks ryzyka od 0 do 100" })).toHaveCount(0);
  const saved = await page.evaluate(() => Object.fromEntries(Object.entries(localStorage).filter(([k]) => k.startsWith("quantops.xtb"))));
  const data = await loadExample(page);
  expect(data.asset_scope).toBe("equities_only");
  expect(data.before?.diagnostics.score.status).toBe("available");
  await expect(page.getByRole("figure", { name: "Indeks ryzyka od 0 do 100" })).toContainText(String(data.before?.diagnostics.score.value));
  await page.getByText("Jak powstaje wynik 0–100?", { exact: true }).click();
  await expect(page.getByRole("region", { name: "Zasady indeksu ryzyka" })).toContainText("Koncentracja HHI");
  const scan = await new AxeBuilder({ page }).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze();
  expect(scan.violations).toEqual([]);
  await page.getByText("Jak powstaje wynik 0–100?", { exact: true }).click();
  await page.evaluate(() => window.scrollTo({ top:0, behavior:"instant" }));
  if (process.env.QUANTOPS_CAPTURE_RISK === "1") {
    await page.screenshot({ path: testInfo.outputPath("risk-overview.png"), fullPage: true });
    await page.getByRole("tabpanel").screenshot({ path: testInfo.outputPath("risk-overview-panel.png") });
  }
  await tab(page,"Koncentracja").click();
  await expect(page.getByRole("img", { name: "Podział wartości portfela" })).toBeVisible();
  await page.getByRole("button", { name: /JPM.US/ }).click();
  await expect(page.getByRole("complementary", { name: "Szczegóły wybranej spółki" })).toContainText("JPM.US");
  await expect(page.getByText("Efektywna liczba pozycji", { exact: true })).toBeVisible();
  await expect(page.getByText("Technologia", { exact: true })).toBeVisible();
  await page.evaluate(() => window.scrollTo({ top:0, behavior:"instant" }));
  if (process.env.QUANTOPS_CAPTURE_RISK === "1") await page.screenshot({ path: testInfo.outputPath("risk-concentration.png"), fullPage: true });
  await tab(page,"Koncentracja").focus();
  await page.keyboard.press("ArrowRight");
  await expect(tab(page,"Dywersyfikacja")).toHaveAttribute("aria-selected","true");
  await expect(page.getByRole("region", { name: "Macierz korelacji" })).toBeVisible();
  await page.getByRole("button", { name: /^AAPL.US i MSFT.US: korelacja/ }).click();
  await expect(page.getByRole("tabpanel").getByRole("status")).toContainText("AAPL.US × MSFT.US");
  await page.getByText("Szczegóły liczbowe — wkład pozycji w ryzyko", { exact: true }).click();
  await expect(page.getByRole("region", { name: "Wkład pozycji w ryzyko" })).toContainText("JNJ.US");
  expect((await new AxeBuilder({ page }).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze()).violations).toEqual([]);
  if (process.env.QUANTOPS_CAPTURE_RISK === "1") await page.screenshot({ path: testInfo.outputPath("risk-diversification.png"), fullPage: true });
  await tab(page,"Historia").click();
  await expect(page.getByRole("img", { name: "Historyczne obsunięcie obecnej alokacji" })).toBeVisible();
  await page.getByRole("slider", { name: "Odczyt: Historyczne obsunięcie obecnej alokacji", exact: true }).fill("10");
  await expect(page.getByRole("img", { name: "Symulowana wartość obecnej alokacji", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(await page.evaluate(() => Object.fromEntries(Object.entries(localStorage).filter(([k]) => k.startsWith("quantops.xtb"))))).toEqual(saved);
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Pobierz raport z danymi i założeniami" }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe("quantops-risk-report.json");
  const exported = JSON.parse(await readFile(await download.path(), "utf8")) as { result: RiskResult };
  expect(exported.result.before?.diagnostics.score.value).toBe(data.before?.diagnostics.score.value);
});

test("scenario selection and independent equity allocation preserve imported accounts", async ({ page }) => {
  await openRisk(page);
  const saved = await page.evaluate(() => Object.fromEntries(Object.entries(localStorage).filter(([k]) => k.startsWith("quantops.xtb"))));
  const data = await loadExample(page);
  await tab(page,"Możliwe spadki").click();
  await page.getByLabel("Wybierz próbny spadek").selectOption("0.1");
  await expect(page.getByRole("figure", { name: "Indeks ryzyka od 0 do 100" })).toHaveCount(0);
  const response = page.waitForResponse(r => r.url().endsWith("/api/v1/xtb/risk"));
  await page.getByRole("button", { name: "Wykonaj stress test", exact: true }).click();
  const stress = await (await response).json() as RiskResult;
  expect(Number(stress.before?.scenarios[0]?.pnl)).toBeCloseTo(-Number(data.before?.value)*0.1,5);
  await expect(page.getByRole("region", { name: "Spadek pojedynczej spółki" })).toContainText("XOM.US");
  await page.getByRole("button", { name: "Ruchy w badanej historii", exact: true }).click();
  await expect(page.getByText("Największe obsunięcie w trakcie", { exact: true })).toBeVisible();
  await expect(page.getByText(/Tolerancja dotyczy wyniku końcowego/)).toBeVisible();
  await tab(page,"Porównaj wariant").click();
  await page.getByRole("button", { name: "Utwórz kopię alokacji", exact: true }).click();
  const weights: Record<string,string> = { "AAPL.US":"30", "MSFT.US":"20", "JNJ.US":"20", "JPM.US":"20", "XOM.US":"10" };
  for (const [symbol,value] of Object.entries(weights)) await page.getByLabel(symbol + " — udział %").fill(value);
  await page.getByRole("button", { name: "Porównaj inny podział", exact: true }).click();
  await expect(page.getByRole("region", { name: "Porównanie wariantów" })).toContainText("Zmienność roczna");
  await expect(page.getByRole("complementary", { name: "Wniosek z obliczeń" })).toContainText("Historyczna zmienność roczna");
  expect(await page.evaluate(() => Object.fromEntries(Object.entries(localStorage).filter(([k]) => k.startsWith("quantops.xtb"))))).toEqual(saved);
});

test("real imported quantities use dated histories, disclose short samples, and remain account isolated", async ({ page }) => {
  await openRisk(page,"admin");
  const nav = page.getByRole("navigation", { name: "Centrum portfela" });
  await nav.getByRole("button", { name: "Brokerzy i konta", exact: true }).click();
  await page.getByLabel("Nazwa konta", { exact: true }).fill("Synthetic risk import");
  await page.getByLabel("Numer konta XTB").fill("987654");
  await page.getByRole("combobox", { name: "Waluta konta", exact: true }).selectOption("PLN");
  await page.getByRole("button", { name: "Dodaj konto XTB" }).click();
  await page.getByLabel("Lub wklej treść CSV").fill("Instrument,Category,Ticker,Type,Volume,Open Price,Open Time (UTC),Position ID\nSynthetic Apple,Stocks,AAPL.US,BUY,10,100,2026-06-01T00:00:00Z,synthetic-1");
  await page.getByLabel("Stan raportu — data i godzina UTC").fill("2026-07-01T00:00");
  await page.getByRole("button", { name: "Pokaż podgląd raportu" }).click();
  await page.getByLabel(/Potwierdzam pełny stan/).check();
  await page.getByRole("button", { name: "Zatwierdź import na to konto" }).click();
  await expect(page.getByRole("region", { name: "Otwarte pozycje XTB" })).toContainText("Synthetic Apple");
  await nav.getByRole("button", { name: "Analiza ryzyka", exact: true }).click();
  let requests = 0;
  let oldPrices = false;
  await page.route("**/api/v1/xtb/risk-history", route => {
    requests += 1;
    return route.fulfill({ json: { failures:{}, histories:[{
      symbol:"AAPL.US", currency:"USD", base_currency:"PLN", source:"Synthetic browser fixture",
      source_url:"https://example.com/synthetic", fx_source:"Synthetic USD/PLN", fetched_at:"2026-07-09T00:00:00Z",
      origin:"synthetic", price_basis:"split_dividend_adjusted", split_dates:[],
      rows:(oldPrices ? ["2026-06-25","2026-06-26","2026-06-29","2026-06-30"] : ["2026-07-01","2026-07-02","2026-07-03","2026-07-06","2026-07-07","2026-07-08"]).map(date => ({date,close:"100",adjusted_close:"100",fx_to_base:"4"})),
    }] } });
  });
  const response = page.waitForResponse(r => r.url().endsWith("/api/v1/xtb/risk"));
  await page.getByRole("button", { name: "Oblicz analizę i scenariusze", exact: true }).click();
  const result = await (await response).json() as RiskResult;
  expect(result.asset_scope).toBe("equities_only");
  expect(Number(result.before?.value)).toBe(4000);
  expect(result.before?.diagnostics.score.value).toBeNull();
  await expect(page.getByRole("figure", { name: "Indeks ryzyka od 0 do 100" })).toContainText("Ocena niedostępna");
  await expect(page.getByText(/Do indeksu potrzeba 252/)).toBeVisible();
  await tab(page,"Koncentracja").click();
  await expect(page.getByText("Brak udokumentowanych danych", { exact: true }).first()).toBeVisible();
  await tab(page,"Możliwe spadki").click();
  await page.getByLabel("Wybierz próbny spadek").selectOption("0.1");
  const presetResponse = page.waitForResponse(r => r.url().endsWith("/api/v1/xtb/risk"));
  await page.getByRole("button", { name: "Wykonaj stress test", exact: true }).click();
  const preset = await (await presetResponse).json() as RiskResult;
  expect(Number(preset.before?.scenarios[0]?.pnl)).toBe(-400);
  expect(Number(preset.before?.scenarios[0]?.value_after)).toBe(3600);
  expect(requests).toBe(1);
  await nav.getByRole("button", { name: "Brokerzy i konta", exact: true }).click();
  await page.getByLabel("Nazwa konta", { exact: true }).fill("Second synthetic account");
  await page.getByLabel("Numer konta XTB").fill("987655");
  await page.getByRole("button", { name: "Dodaj konto XTB" }).click();
  await nav.getByRole("button", { name: "Analiza ryzyka", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "Źródło portfela" })).toContainText("Second synthetic account");
  await expect(page.getByRole("figure", { name: "Indeks ryzyka od 0 do 100" })).toHaveCount(0);
  await page.getByRole("group", { name: "Konta XTB" }).getByRole("button", { name: /Synthetic risk import/ }).click();
  oldPrices = true;
  await page.getByRole("button", { name: "Oblicz analizę i scenariusze", exact: true }).click();
  await expect(page.getByText(/Zapisane pozycje są na 2026-07-01, a ostatnie wspólne ceny i kursy walut na 2026-06-30/)).toBeVisible();
  await expect(page.getByRole("figure", { name: "Indeks ryzyka od 0 do 100" })).toHaveCount(0);
  expect(requests).toBe(2);
});

test("missing sources, omitted ETFs, invalid weights and service failures cannot leave a reassuring score", async ({ page }) => {
  await openRisk(page);
  await page.route("**/api/v1/xtb/risk-history", route => route.fulfill({ json: { histories:[], failures:{"AAPL.US":"Synthetic source unavailable"} } }));
  await page.getByRole("button", { name: "Oblicz analizę i scenariusze", exact: true }).click();
  await expect(page.getByText("Wynik częściowy — brakuje danych do wyceny zapisanych pozycji.")).toBeVisible();
  await expect(page.getByText(/Poza zakresem:.*EUNL.DE/)).toBeVisible();
  await expect(page.getByRole("figure", { name: "Indeks ryzyka od 0 do 100" })).toHaveCount(0);
  await loadExample(page);
  await tab(page,"Porównaj wariant").click();
  await page.getByRole("button", { name: "Utwórz kopię alokacji" }).click();
  await page.getByLabel("AAPL.US — udział %").fill("0");
  await page.getByRole("button", { name: "Porównaj inny podział", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("100%");
  await page.getByRole("button", { name: "Odrzuć wariant" }).click();
  await page.route("**/api/v1/xtb/risk", route => route.fulfill({ status:503,json:{detail:"Synthetic API outage"} }));
  await page.getByRole("button", { name: "Oblicz analizę i scenariusze", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Synthetic API outage");
  await expect(page.getByRole("figure", { name: "Indeks ryzyka od 0 do 100" })).toHaveCount(0);
});
