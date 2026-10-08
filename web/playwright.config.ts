import { defineConfig, devices } from "@playwright/test";

/**
 * Real-browser journeys (Sprint 52, ADR-062).
 *
 * The stack under test is the **production build**, not `next dev`: the CSP is looser in dev, the
 * service worker registers only in a production build, and `sw.js`'s DENY list is a security
 * boundary that nothing else exercises. The API is the real one on the `iism_e2e` database that
 * `make seed-e2e` fills from the NSQF test fixture, with `ENVIRONMENT=test` so the sign-in code
 * is returned and the form prints it.
 *
 * Ports are 8100 and 3100, never 8000 and 3000, so these never collide with `make api` and
 * `make web`. The database, Redis db and secret are likewise the tests' own.
 */
const API = "http://localhost:8100";
const WEB = "http://localhost:3100";

const database = process.env.E2E_DATABASE_URL ?? "postgresql+asyncpg://iism:iism@localhost:5433/iism_e2e";
const redis = process.env.E2E_REDIS_URL ?? "redis://localhost:6380/1";

export const E2E = { API, WEB, database, redis };

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  // Each test registers its own people, so order does not matter; two workers keep a laptop and
  // a small CI runner from drowning one Postgres.
  fullyParallel: true,
  workers: 2,
  // One retry in CI, none locally. A test that needs more than that is rewritten around a
  // web-first assertion or deleted -- a flaky journey teaches people to ignore red.
  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: WEB,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    // India-first: the dates the pages print must not depend on where the tests run.
    timezoneId: "Asia/Kolkata",
    locale: "en-IN",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: ".venv/bin/uvicorn api.main:app --port 8100",
      cwd: "..",
      url: `${API}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: {
        DATABASE_URL: database,
        REDIS_URL: redis,
        ENVIRONMENT: "test",
        RATE_LIMIT_ENABLED: "false",
        JWT_SECRET_KEY: "e2e-only-key-" + "x".repeat(40),
        WEB_BASE_URL: WEB,
        API_BASE_URL: API,
      },
    },
    {
      command: "npm run start:e2e",
      url: `${WEB}/en`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
