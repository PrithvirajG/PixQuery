// E2E: Workspaces CRUD + scan trigger against the live API/Mongo, and
// workspace membership sharing. No mocking.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { test, expect } = require('@playwright/test');
const { registerAndLogin } = require('./helpers');

async function createWorkspace(page, name, dirPath) {
  await page.getByRole('button', { name: '+ New workspace' }).first().click();
  await page.getByPlaceholder('design-refs').fill(name);
  await page.getByPlaceholder(/Photos.*C:\\Users/).fill(dirPath);
  await page.getByRole('button', { name: 'Create workspace' }).click();
  await expect(page.getByText(name)).toBeVisible({ timeout: 15_000 });
}

test.describe('Workspaces', () => {
  let watchDir;

  test.beforeAll(() => {
    // The backend process runs natively on this same machine, so a real
    // directory here is a real, backend-resolvable workspace_path.
    watchDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pixquery-e2e-'));
  });

  test.afterAll(() => {
    fs.rmSync(watchDir, { recursive: true, force: true });
  });

  test('create, open, and delete a workspace', async ({ page }) => {
    await registerAndLogin(page);
    await page.goto('/workspaces');
    await expect(page.getByText(/spaces?$/i).first()).toBeVisible();

    const wsName = `e2e-space-${Date.now()}`;
    await createWorkspace(page, wsName, watchDir);

    // Open detail view (workspace name text isn't clickable — use the card's "Open ›" button)
    const card = page.locator('.ap-cell', { hasText: wsName });
    await card.getByRole('button', { name: 'Open ›' }).click();
    await expect(page).toHaveURL(/\/workspaces\/.+/);

    await page.goto('/workspaces');
    await expect(page.getByText(wsName)).toBeVisible();

    // Delete — confirm() is real window.confirm; auto-accept via dialog handler.
    page.once('dialog', (d) => d.accept());
    await page.locator('.ap-cell', { hasText: wsName }).getByTitle('Delete workspace').click();
    await expect(page.getByText(wsName)).not.toBeVisible({ timeout: 15_000 });
  });

  test('triggering a scan on an active workspace with no pipelines is blocked', async ({ page }) => {
    await registerAndLogin(page);
    await page.goto('/workspaces');

    const wsName = `e2e-scan-${Date.now()}`;
    await createWorkspace(page, wsName, watchDir);

    const card = page.locator('.ap-cell', { hasText: wsName });
    // No pipelines attached yet -> Scan button must be disabled per WsCard logic.
    await expect(card.getByTitle('Attach at least one pipeline before scanning')).toBeDisabled();
  });

  test('filtering the workspace list narrows results', async ({ page }) => {
    await registerAndLogin(page);
    await page.goto('/workspaces');

    const nameA = `e2e-filter-a-${Date.now()}`;
    const nameB = `e2e-filter-b-${Date.now()}`;
    await createWorkspace(page, nameA, watchDir);
    await createWorkspace(page, nameB, watchDir);

    await page.getByPlaceholder('Filter workspaces').fill(nameA);
    await expect(page.getByText(nameA)).toBeVisible();
    await expect(page.getByText(nameB)).not.toBeVisible();
  });
});
