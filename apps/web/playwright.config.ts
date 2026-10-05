import { defineConfig, devices } from "@playwright/test";

const isCi = Boolean(process.env.CI);
const apiPort = process.env.QUANTOPS_E2E_API_PORT ?? "8001";
const webPort = process.env.QUANTOPS_E2E_WEB_PORT ?? "4173";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: isCi,
  retries: isCi ? 1 : 0,
  workers: isCi ? 2 : undefined,
  reporter: isCi
    ? [["line"], ["html", { open: "never", outputFolder: "playwright-report" }]]
    : "list",
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    colorScheme: "dark",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  expect: {
    timeout: 5_000,
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"] },
    },
  ],
  webServer: [{
    command: process.platform === "win32"
      ? `.venv\\Scripts\\python.exe -m uvicorn quantops_api.main:app --host 127.0.0.1 --port ${apiPort}`
      : `.venv/bin/python -m uvicorn quantops_api.main:app --host 127.0.0.1 --port ${apiPort}`,
    cwd: "../..",
    env: { QUANTOPS_EXPENSIVE_RATE_LIMIT: "1000" },
    url: `http://127.0.0.1:${apiPort}/api/v1/health`,
    reuseExistingServer: !isCi,
    timeout: 120_000,
  }, {
    command: `pnpm exec vite --host 127.0.0.1 --port ${webPort} --configLoader runner`,
    env: { QUANTOPS_API_URL: `http://127.0.0.1:${apiPort}` },
    url: `http://127.0.0.1:${webPort}`,
    reuseExistingServer: !isCi,
    timeout: 120_000,
  }],
});
