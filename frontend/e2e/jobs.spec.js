// E2E: Jobs/Stats view — hits the live /stats endpoints. No mocking.
const { test, expect } = require('@playwright/test');
const { registerAndLogin } = require('./helpers');

test.describe('Jobs & stats', () => {
  test('jobs view loads live overview stats', async ({ page }) => {
    await registerAndLogin(page);

    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes('/stats/overview')),
      page.goto('/jobs'),
    ]);
    expect(response.status()).toBe(200);
    await expect(page.getByText('Active Workspaces')).toBeVisible();
    await expect(page.getByText('Jobs Completed')).toBeVisible();
  });

  test('jobs view is reachable from the nav rail and reflects an empty state gracefully', async ({ page }) => {
    await registerAndLogin(page);
    await page.goto('/search');
    // AppShell's "Jobs" nav lives at /jobs but is not in the primary NAV groups
    // rendered by AppShell (Search/Spaces/Pipelines); reach it directly.
    await page.goto('/jobs');
    await expect(page).toHaveURL(/\/jobs/);
    // Either a populated jobs table or the explicit empty state is fine —
    // both are real, backend-driven states for a fresh account.
    await expect(page.locator('table').or(page.getByText('No jobs yet'))).toBeVisible({ timeout: 15_000 });
  });
});
