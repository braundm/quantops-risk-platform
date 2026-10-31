import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const syntheticPassword = "Synthetic-passphrase-for-browser-test!";

test("local login, optional survey, multi-broker choice and password verification", async ({ page }) => {
  await page.goto("/");
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  await page.screenshot({ path: `../../artifacts/local-login-${test.info().project.name}.png`, fullPage: true });
  await page.getByRole("button", { name: "Załóż konto", exact: true }).click();
  await page.getByLabel("Nazwa wyświetlana").fill("Synthetic local owner");
  await page.getByLabel("Login", { exact: true }).fill("synthetic.owner");
  await page.getByLabel("Hasło", { exact: true }).fill(syntheticPassword);
  await page.getByLabel("Powtórz hasło").fill("Synthetic-wrong-repeat");
  await page.getByRole("button", { name: "Utwórz konto i kontynuuj" }).click();
  await expect(page.getByRole("alert")).toContainText("Hasła muszą być takie same");
  await page.getByLabel("Powtórz hasło").fill(syntheticPassword);
  await page.getByRole("button", { name: "Utwórz konto i kontynuuj" }).click();
  await expect(page.getByRole("heading", { name: "Najpierw portfel czy krótka ankieta?" })).toBeVisible();
  await page.getByRole("button", { name: "Pomiń ankietę i wybierz brokerów →" }).click();
  await page.getByRole("button", { name: /XTB Raporty CSV/ }).click();
  await page.getByRole("button", { name: /Bossa Importer/ }).click();
  await page.getByRole("button", { name: "Zapisz brokerów i przejdź dalej →" }).click();
  await expect(page.getByText("XTB · Bossa", { exact: true })).toBeVisible();
  await page.getByRole("navigation", { name: "Centrum portfela" }).getByRole("button", { name: "Ustawienia", exact: true }).click();
  await expect(page.getByText("Pominięta — możesz wrócić w dowolnym momencie")).toBeVisible();
  await page.getByRole("button", { name: "Uzupełnij ankietę", exact: true }).click();
  await page.getByRole("button", { name: "Zapisz ankietę", exact: true }).click();
  await expect(page.getByText("Uzupełniona", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Wyloguj się", exact: true }).click();
  await page.getByLabel("Login", { exact: true }).fill("synthetic.owner");
  await page.getByLabel("Hasło", { exact: true }).fill("Synthetic-incorrect-password");
  await page.getByRole("button", { name: "Otwórz mój portfel" }).click();
  await expect(page.getByRole("alert")).toContainText("Nieprawidłowy login lub hasło");
  await expect(page.getByRole("navigation", { name: "Centrum portfela" })).toHaveCount(0);
  await page.getByLabel("Hasło", { exact: true }).fill(syntheticPassword);
  await page.getByRole("button", { name: "Otwórz mój portfel" }).click();
  await expect(page.getByRole("heading", { name: "Przegląd", exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Przegląd", exact: true })).toBeVisible();
  const stored = await page.evaluate(() => localStorage.getItem("quantops.stock-users.v1"));
  expect(stored).not.toContain(syntheticPassword);
  expect(stored).toContain('"survey_status":"completed"');
  await page.evaluate(() => sessionStorage.clear()); await page.reload();
  await expect(page.getByRole("heading", { name: "Witaj ponownie" })).toBeVisible();
});

test("legacy profile can gain credentials without dropping its report account", async ({ page }) => {
  const id = "11111111-1111-4111-8111-111111111111";
  await page.goto("/");
  await page.evaluate(userId => {
    localStorage.setItem("quantops.stock-users.v1", JSON.stringify({ version: 1, active_id: userId, users: [
      { id: userId, name: "Synthetic legacy", created_at: "2026-07-01T00:00:00Z", answers: null, profile: null, positions: [] },
    ] }));
    localStorage.setItem(`quantops.xtb-books.v1.${userId}`, JSON.stringify({ version: 1, selected: "synthetic-account", accounts: [
      { id: "synthetic-account", label: "Synthetic retained", broker: "xtb", marks: [], imports: [], book: { account_number: "111111", currency: "USD", records: [], open_snapshot_at: null, ledger_complete: false } },
    ] }));
  }, id);
  await page.reload();
  await page.getByRole("button", { name: "Załóż konto", exact: true }).click();
  await page.getByLabel("Nazwa wyświetlana").fill("Synthetic migrated");
  await page.getByLabel("Login", { exact: true }).fill("synthetic.migrated");
  await page.getByLabel("Hasło", { exact: true }).fill(syntheticPassword);
  await page.getByLabel("Powtórz hasło").fill(syntheticPassword);
  await page.getByLabel("Wcześniejszy profil").selectOption(id);
  await page.getByRole("button", { name: "Utwórz konto i kontynuuj" }).click();
  await page.getByRole("button", { name: "Pomiń ankietę i wybierz brokerów →" }).click();
  await page.getByRole("button", { name: /XTB Raporty CSV/ }).click();
  await page.getByRole("button", { name: "Zapisz brokerów i przejdź dalej →" }).click();
  await expect(page.getByRole("button", { name: "Synthetic retained · USD · ••••1111" })).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `../../artifacts/workspace-accounts-${test.info().project.name}.png`, fullPage: true });
});
