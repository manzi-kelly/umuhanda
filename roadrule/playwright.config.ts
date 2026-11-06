import { defineConfig } from "@playwright/test";

const accessFixture = { PHASE04D_BROWSER_ACCESS: "1" };
export default defineConfig({
  globalTeardown: "./tests/browser/teardown.ts",
  testDir: "./tests/browser",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: [
    ["list"],
    [
      "json",
      { outputFile: "docs/evidence/phase04i/public-browser-results.json" },
    ],
  ],
  use: {
    baseURL: "http://127.0.0.1:3100",
    channel: "chrome",
    headless: true,
    trace: "off",
    screenshot: "off",
  },
  projects: [
    { name: "390px", use: { viewport: { width: 390, height: 844 } } },
    { name: "834px", use: { viewport: { width: 834, height: 1112 } } },
    { name: "1440px", use: { viewport: { width: 1440, height: 1000 } } },
  ],
  webServer: [
    {
      cwd: "backend",
      command:
        ".venv\\Scripts\\python.exe -m scripts.admin_browser_fixture serve",
      url: "http://127.0.0.1:8310/api/v1/health",
      reuseExistingServer: false,
      timeout: 90000,
      env: accessFixture,
    },
    {
      command: "npm run start -- --hostname 127.0.0.1 --port 3100",
      url: "http://127.0.0.1:3100",
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        ADMIN_API_ORIGIN: "http://127.0.0.1:8310",
        ADMIN_FRONTEND_ORIGIN: "http://127.0.0.1:3100",
        ADMIN_LOCAL_DEVELOPMENT: "1",
      },
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
