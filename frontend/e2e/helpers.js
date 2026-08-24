// Shared helpers for PixQuery E2E specs.
const { expect } = require('@playwright/test');

// Generates a unique username per test run so repeated runs against the same
// live MongoDB never collide on "Username already registered".
function uniqueUsername(prefix = 'e2e') {
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 1e6)}`;
}

// Drives the real LandingPage auth modal to register + auto-login a fresh
// user, then waits for the authenticated Dashboard shell to mount.
async function registerAndLogin(page, { username, password = 'password123' } = {}) {
  const user = username || uniqueUsername();
  await page.goto('/');
  await page.getByRole('button', { name: 'Sign Up Free' }).click();
  await page.getByPlaceholder('Enter your username').fill(user);
  await page.getByPlaceholder('••••••••').first().fill(password);
  await page.getByPlaceholder('••••••••').nth(1).fill(password);
  await page.getByRole('button', { name: 'Create Secure Index' }).click();

  // Successful register+login lands on the authenticated shell (default
  // route is /search per App.js's catch-all redirect).
  await expect(page).toHaveURL(/\/search/, { timeout: 15_000 });
  return { username: user, password };
}

async function logout(page) {
  // AppShell's avatar button opens a menu with "Sign out".
  await page.locator('nav button[title]').last().click();
  await page.getByRole('button', { name: 'Sign out' }).click();
}

module.exports = { uniqueUsername, registerAndLogin, logout };
