// E2E: authentication lifecycle against the live backend + MongoDB.
// No mocking — register creates a real user document, login issues a real
// JWT, /auth/me is hit for real, logout clears real localStorage state.
const { test, expect } = require('@playwright/test');
const { uniqueUsername, registerAndLogin, logout } = require('./helpers');

test.describe('Authentication', () => {
  test('landing page renders for a signed-out visitor', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Natural Language/i })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Login' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign Up Free' })).toBeVisible();
  });

  test('a new user can register and lands on the authenticated Search view', async ({ page }) => {
    const { username } = await registerAndLogin(page);
    // AppShell nav + SearchView chrome should be present.
    await expect(page.getByPlaceholder(/Search your library/i)).toBeVisible();
    await expect(page.locator('nav button[title]').last()).toHaveAttribute('title', username);
  });

  test('registering the same username twice is rejected', async ({ page }) => {
    const username = uniqueUsername('dupe');
    await registerAndLogin(page, { username });
    await logout(page);

    // Second registration attempt with the same username against the live API.
    await page.goto('/');
    await page.getByRole('button', { name: 'Sign Up Free' }).click();
    await page.getByPlaceholder('Enter your username').fill(username);
    await page.getByPlaceholder('••••••••').first().fill('password123');
    await page.getByPlaceholder('••••••••').nth(1).fill('password123');
    await page.getByRole('button', { name: 'Create Secure Index' }).click();

    await expect(page.getByText(/already registered/i)).toBeVisible();
  });

  test('logging in with the wrong password is rejected', async ({ page }) => {
    const username = uniqueUsername('wrongpw');
    await registerAndLogin(page, { username });
    await logout(page);

    await page.goto('/');
    await page.locator('header').getByRole('button', { name: 'Login' }).click();
    await page.getByPlaceholder('Enter your username').fill(username);
    await page.getByPlaceholder('••••••••').first().fill('not-the-right-password');
    await page.locator('form').getByRole('button', { name: 'Login' }).click();

    await expect(page.getByText(/error occurred|invalid/i)).toBeVisible();
  });

  test('logout returns the user to the landing page and clears the session', async ({ page }) => {
    await registerAndLogin(page);
    await logout(page);
    await expect(page.getByRole('button', { name: 'Sign Up Free' })).toBeVisible();

    // A fresh reload must not silently re-authenticate.
    await page.reload();
    await expect(page.getByRole('button', { name: 'Sign Up Free' })).toBeVisible();
  });

  test('a signed-in session survives a page reload', async ({ page }) => {
    await registerAndLogin(page);
    await page.reload();
    await expect(page.getByPlaceholder(/Search your library/i)).toBeVisible();
  });
});
