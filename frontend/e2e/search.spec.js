// E2E: Search / Gallery view — keyword & semantic search against the live
// backend, Weaviate and MongoDB. With no images ingested the assertions
// focus on the real request/response cycle and UI state, not on specific
// result content (this is a fresh, isolated E2E user/session, so the
// account's accessible asset set is empty by construction).
const { test, expect } = require('@playwright/test');
const { registerAndLogin } = require('./helpers');

test.describe('Search', () => {
  test('search view loads and defaults to keyword mode', async ({ page }) => {
    await registerAndLogin(page);
    await expect(page).toHaveURL(/\/search/);
    await expect(page.getByPlaceholder(/Search your library/i)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Keyword ✦' })).toBeVisible();
  });

  test('typing a query and submitting hits the live /search endpoint', async ({ page }) => {
    await registerAndLogin(page);

    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes('/search?') && r.request().method() === 'GET'),
      (async () => {
        await page.getByPlaceholder(/Search your library/i).fill('sunset beach');
        await page.locator('form').getByRole('button', { name: 'Search' }).click();
      })(),
    ]);

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(Array.isArray(body)).toBe(true); // real backend contract: a list of image results
  });

  test('switching to semantic mode re-queries with the new mode', async ({ page }) => {
    await registerAndLogin(page);

    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes('/search?') && r.url().includes('mode=semantic')),
      page.getByRole('button', { name: 'Semantic', exact: true }).click(),
    ]);
    expect(response.status()).toBe(200);
  });

  test('workspace filter narrows the search request to a workspace_id', async ({ page }) => {
    await registerAndLogin(page);

    // Create a real workspace via the live API so the dropdown has an entry.
    await page.goto('/workspaces');
    await page.getByRole('button', { name: '+ New workspace' }).first().click();
    const wsName = `e2e-search-ws-${Date.now()}`;
    await page.getByPlaceholder('design-refs').fill(wsName);
    await page.getByPlaceholder(/Photos.*C:\\Users/).fill('/tmp');
    await page.getByRole('button', { name: 'Create workspace' }).click();
    await expect(page.getByText(wsName)).toBeVisible({ timeout: 15_000 });

    await page.goto('/search');
    await page.getByText('All workspaces').click();
    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes('/search?') && r.url().includes('workspace_id=')),
      page.getByText(wsName).click(),
    ]);
    expect(response.status()).toBe(200);
  });
});
