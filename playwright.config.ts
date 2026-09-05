import { defineConfig, devices } from "@playwright/test";
import { randomUUID } from "node:crypto";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  expect: { timeout: 15000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "on",
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
  webServer: [
    {
      command:
        "uv run python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001",
      url: "http://127.0.0.1:8001/api/health",
      reuseExistingServer: false,
      timeout: 90000,
      env: {
        TRUST_DB_PATH: `data/e2e-${randomUUID()}.db`,
        OPENAI_API_KEY: "",
        RAZORPAY_KEY_ID: "",
        RAZORPAY_KEY_SECRET: "",
      },
    },
    {
      command: "npm run dev -- --port 5174",
      env: { TRUST_API_TARGET: "http://127.0.0.1:8001" },
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
