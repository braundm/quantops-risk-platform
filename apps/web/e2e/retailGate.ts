import { expect, type Page } from "@playwright/test";

/** Local retail gate: display name + default full-access settings. */
export async function enterRetailWorkspace(page: Page, displayName = "E2E"): Promise<void> {
  await page.goto("/personal");
  const login = page.getByRole("heading", { name: "Zaloguj się lokalnie" });
  if (await login.isVisible().catch(() => false)) {
    await page.getByLabel("Nazwa użytkownika").fill(displayName);
    await page.getByRole("button", { name: /Zaloguj i przejdź do ankiety/ }).click();
  }
  const onboarding = page.getByRole("heading", { name: "Ankieta ryzyka — pierwszy krok" });
  if (await onboarding.isVisible().catch(() => false)) {
    await page.getByRole("button", { name: "Ustawienia domyślne — pełny dostęp" }).click();
  }
  await expect(page.getByRole("heading", { name: "Zrozum swój portfel." })).toBeVisible();
}
