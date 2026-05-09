import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for TD Pay E2E tests.
 *
 * Requirements for local run:
 * 1. Backend running: `docker compose up -d postgres redis backend`
 * 2. Frontend dev server: `pnpm dev` (port 3000)
 * 3. Test database migrated: `cd backend && alembic upgrade head`
 *
 * Run: `pnpm e2e`
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // Backend API для setup-действий
  webServer: process.env.CI
    ? []
    : [
        {
          command: "pnpm dev",
          url: "http://localhost:3000",
          reuseExistingServer: true,
        },
      ],
});
