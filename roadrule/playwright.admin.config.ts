import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/admin-browser",
  workers: 1,
  fullyParallel: false,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  globalTeardown: "./tests/admin-browser/teardown.ts",
  reporter: [
    ["list"],
    [
      "json",
      { outputFile: "docs/evidence/phase04i/admin-browser-results.json" },
    ],
  ],
  use: {
    baseURL: "http://127.0.0.1:3100",
    channel: "chrome",
    headless: true,
    trace: "off",
    screenshot: "off",
    video: "off",
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
      timeout: 60_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: "npm run start -- --hostname 127.0.0.1 --port 3100",
      url: "http://127.0.0.1:3100/admin/login",
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        ADMIN_API_ORIGIN: "http://127.0.0.1:8310",
        ADMIN_FRONTEND_ORIGIN: "http://127.0.0.1:3100",
        ADMIN_LOCAL_DEVELOPMENT: "1",
      },
    },
  ],
});
