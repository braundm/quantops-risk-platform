import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// All report and price data in this suite are synthetic.
const csv = "Instrument,Category,Ticker,Type,Volume,Open Price,Open Time (UTC),Position ID\nSynthetic Apple,Stocks,AAPL.US,BUY,10,100,2026-06-01T10:00:00Z,1001";
const syntheticPassword = "Synthetic-local-passphrase-2026!";
async function navigate(page: Page, name: string) {
  await page.getByRole("navigation", { name: "Centrum portfela" }).getByRole("button", { name, exact: true }).click();
}
async function createProfile(page: Page, name: string) {
  await page.getByRole("button", { name: "Załóż konto", exact: true }).click();
  await page.getByLabel("Nazwa wyświetlana").fill(name);
  await page.getByLabel("Login", { exact: true }).fill(name.toLowerCase().replaceAll(" ", "-"));
  await page.getByLabel("Hasło", { exact: true }).fill(syntheticPassword);
  await page.getByLabel("Powtórz hasło").fill(syntheticPassword);
  await page.getByRole("button", { name: "Utwórz konto i kontynuuj" }).click();
  await page.getByRole("button", { name: "Pomiń ankietę i wybierz brokerów →" }).click();
  await page.getByRole("button", { name: /XTB Raporty CSV/ }).click();
  await page.getByRole("button", { name: "Zapisz brokerów i przejdź dalej →" }).click();
  await expect(page.getByRole("heading", { name: "Brokerzy i konta", exact: true })).toBeVisible();
}
async function addAccount(page: Page, name: string, number: string) {
  await navigate(page, "Brokerzy i konta");
  await page.getByLabel("Nazwa konta", { exact: true }).fill(name);
  await page.getByLabel("Numer konta XTB").fill(number);
  await page.getByRole("button", { name: "Dodaj konto XTB" }).click();
  await expect(page.getByRole("heading", { name: "Wczytaj raport XTB" })).toBeVisible();
  await expect(page.getByText("Sprawdzam dane…")).toHaveCount(0);
}
async function importOpen(page: Page) {
  await navigate(page, "Import raportów");
  await page.getByLabel("Lub wklej treść CSV").fill(csv);
  await page.getByLabel("Stan raportu — data i godzina UTC").fill("2026-07-01T00:00");
  await page.getByRole("button", { name: "Pokaż podgląd raportu" }).click();
  await expect(page.getByRole("region", { name: "Podgląd raportu XTB" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Zatwierdź import na to konto" })).toBeDisabled();
  await page.getByLabel(/Potwierdzam pełny stan/).check();
  await page.getByRole("button", { name: "Zatwierdź import na to konto" }).click();
  await expect(page.getByRole("region", { name: "Otwarte pozycje XTB" })).toContainText("Synthetic Apple");
}

test("XTB preview, unsold shares, idempotency, prices and isolated accounts and profiles", async ({ page, request }) => {
  const mapping = await request.get("/api/v1/broker-catalog?broker=xtb&q=AAPL.US&limit=50");
  const data = await mapping.json() as { items: { symbol: string; name: string; market: string; instrument_type: string }[] };
  const instrument = data.items.find(item => item.symbol === "AAPL.US" && item.instrument_type === "equity");
  expect(instrument).toBeDefined();
  await page.route("**/api/v1/xtb/quote", route => route.fulfill({ json: {
    stock: { symbol: "AAPL", name: instrument!.name, market: instrument!.market, currency: "USD" },
    requested_date: "2026-06-01", purchase_reference_date: "2026-06-01", purchase_reference_close: "100",
    latest_date: "2026-06-30", latest_close: "120", fetched_at: "2026-07-01T00:00:00Z",
    provider: "Synthetic test fixture", source_url: "https://finance.yahoo.com/quote/AAPL/history/",
    corporate_action_review: false, warnings: [],
  } }));
  await page.goto("/");
  await createProfile(page, "Synthetic Anna");
  await expect(page.getByLabel("Szukaj spółki")).toHaveCount(0);
  await page.getByRole("button", { name: "Zmień wybór brokerów" }).click();
  await page.getByRole("button", { name: /Bossa Importer/ }).click();
  await page.getByRole("button", { name: "Zapisz brokerów i przejdź dalej →" }).click();
  await page.getByRole("button", { name: /Bossa/ }).click();
  await expect(page.getByText(/Na razie importujemy wyłącznie raporty XTB/)).toBeVisible();
  await page.getByRole("button", { name: /XTB Import/ }).click();
  await addAccount(page, "Synthetic USD", "111111");
  await importOpen(page);
  await importOpen(page);
  await expect(page.getByText(/Pominięte duplikaty: 1/)).toBeVisible();
  await page.getByRole("button", { name: "Odśwież ceny otwartych akcji i ETF" }).click();
  await expect(page.getByRole("region", { name: "Otwarte pozycje XTB" })).toContainText("Cena zweryfikowana");
  await page.route("**/api/v1/xtb/quote", route => route.fulfill({ status: 503, json: { detail: "Synthetic provider outage" } }));
  await page.getByRole("button", { name: "Odśwież ceny otwartych akcji i ETF" }).click();
  await expect(page.getByRole("alert")).toContainText("Zachowano poprzednie ceny");
  await page.reload();
  await navigate(page, "Portfel");
  await expect(page.getByRole("region", { name: "Otwarte pozycje XTB" })).toContainText("Cena zweryfikowana");
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `../../artifacts/xtb-import-${test.info().project.name}.png`, fullPage: true });
  await addAccount(page, "Synthetic second USD", "222222");
  await expect(page.getByRole("region", { name: "Otwarte pozycje XTB" })).toHaveCount(0);
  await page.getByRole("button", { name: "Synthetic USD · USD · ••••1111" }).click();
  await navigate(page, "Portfel");
  await expect(page.getByRole("region", { name: "Otwarte pozycje XTB" })).toContainText("Synthetic Apple");
  await page.getByRole("button", { name: "Wyloguj się", exact: true }).click();
  await createProfile(page, "Synthetic Jan");
  await expect(page.getByText("Nie masz jeszcze kont. Dodaj konto, z którego pochodzi raport.")).toBeVisible();
  await page.getByRole("button", { name: "Wyloguj się", exact: true }).click();
  await page.getByLabel("Login", { exact: true }).fill("synthetic-anna");
  await page.getByLabel("Hasło", { exact: true }).fill(syntheticPassword);
  await page.getByRole("button", { name: "Otwórz mój portfel" }).click();
  await navigate(page, "Portfel");
  await expect(page.getByRole("region", { name: "Otwarte pozycje XTB" })).toContainText("Synthetic Apple");
});

test("closed-only file upload preserves unknown current holdings", async ({ page }) => {
  await page.goto("/"); await createProfile(page, "Synthetic history");
  await addAccount(page, "Synthetic historical", "333333");
  const closed = csv.replace("Position ID", "Close Time (UTC),Profit/Loss,Position ID").replace(",1001", ",2026-06-03T10:00:00Z,25,1001");
  await page.getByLabel("Plik raportu").setInputFiles({ name: "synthetic-closed.csv", mimeType: "text/csv", buffer: Buffer.from(closed) });
  await page.getByRole("button", { name: "Pokaż podgląd raportu" }).click();
  await expect(page.getByText(/Ten raport nie zawiera otwartych pozycji/)).toBeVisible();
  await page.getByRole("button", { name: "Zatwierdź import na to konto" }).click();
  await expect(page.getByText(/Bieżący stan jest nieznany/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Otwarte pozycje XTB" })).toHaveCount(0);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
});
