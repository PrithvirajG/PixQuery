// E2E: Pipelines page — create a pipeline against the live API/Mongo.
// No mocking.
const { test, expect } = require('@playwright/test');
const { registerAndLogin } = require('./helpers');

test.describe('Pipelines', () => {
  test('create a new pipeline and see it in the list', async ({ page }) => {
    await registerAndLogin(page);
    await page.goto('/pipelines');
    await expect(page.getByText(/defined$/)).toBeVisible();

    const name = `e2e-pipeline-${Date.now()}`;
    await page.getByRole('button', { name: '+ New pipeline' }).click();
    await page.getByPlaceholder('pipeline name').fill(name);
    await page.getByPlaceholder('pipeline name').press('Enter');

    await expect(page.getByText(name).first()).toBeVisible({ timeout: 15_000 });
  });

  test('pipelines page is reachable from the Control Room nav', async ({ page }) => {
    await registerAndLogin(page);
    await page.goto('/search');
    await page.getByTitle('Pipelines').click();
    await expect(page).toHaveURL(/\/pipelines/);
  });
});
