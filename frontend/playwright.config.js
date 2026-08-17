// Playwright E2E config for PixQuery.
//
// These specs run against the REAL app: a natively-running FastAPI backend
// (backend/api_main.py) talking to live MongoDB, RabbitMQ and Weaviate, plus
// a natively-running CRA dev server for the frontend. Nothing here is mocked.
//
// Start both before running `npm run test:e2e` — see frontend/e2e/README.md.
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false, // specs share a live DB; keep runs deterministic
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.PIXQUERY_BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
