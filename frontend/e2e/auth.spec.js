// Signing in, signing out, expired sessions, first-login password change.
import { test, expect } from '@playwright/test';
import { reseed, uiLogin, loginAs, apiLogin, API, NEWBIE_PASSWORD } from './helpers';

test.beforeAll(() => reseed());

test.describe('login form', () => {
  test('admin signs in and reaches the app', async ({ page }) => {
    await uiLogin(page, 'admin');
    await expect(page).not.toHaveURL(/\/login/);
    // main shows the business switcher, release the Feeds dashboard
    await expect(page.getByText(/Choose a business to manage|Today's Dashboard/)).toBeVisible();
  });

  test('supervisor lands on the Feeds dashboard', async ({ page }) => {
    await uiLogin(page, 'sup_a');
    await expect(page.getByRole('heading', { name: "Today's Dashboard" })).toBeVisible();
  });

  test('feed-mill user lands on Feed', async ({ page }) => {
    await uiLogin(page, 'mill');
    await expect(page).toHaveURL(/\/feed$/);
    await expect(page.getByRole('heading', { name: 'Feed Stock & Orders' })).toBeVisible();
  });

  test('wrong password is refused with a message', async ({ page }) => {
    await uiLogin(page, 'admin', 'not-the-password');
    await expect(page.getByText('Invalid username or password')).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test('unknown user is refused', async ({ page }) => {
    await uiLogin(page, 'nobody', 'whatever-123');
    await expect(page.getByText('Invalid username or password')).toBeVisible();
  });
});

test.describe('session', () => {
  test('protected pages send a signed-out visitor to login', async ({ page }) => {
    for (const path of ['/farms', '/feed', '/reports', '/users']) {
      await page.goto(path);
      await expect(page).toHaveURL(/\/login/);
    }
  });

  test('logout ends the session', async ({ page }) => {
    await loginAs(page, 'sup_a', '/farms');
    await expect(page.getByRole('heading', { name: /Farms/ })).toBeVisible();
    await page.locator('.nav-user-trigger').hover();                   // user menu (top right)
    await page.locator('.nav-dropdown-logout').click();
    await expect(page).toHaveURL(/\/login/);
    await page.goto('/farms');
    await expect(page).toHaveURL(/\/login/);
  });

  test('stale access token is renewed silently', async ({ page }) => {
    await loginAs(page, 'sup_a', '/login');
    await page.evaluate(() => localStorage.setItem('access_token', 'stale.expired.token'));
    await page.goto('/farms');
    await expect(page.getByText('Lakshmi Farm')).toBeVisible();
    expect(await page.evaluate(() => localStorage.getItem('access_token'))).not.toBe('stale.expired.token');
  });

  test('revoked session lands on login with a notice', async ({ page, request }) => {
    const data = await loginAs(page, 'sup_a', '/login');
    await request.post(`${API}/auth/logout/`, { data: { refresh: data.refresh } });
    await page.evaluate(() => localStorage.setItem('access_token', 'stale.expired.token'));
    await page.goto('/farms');
    await expect(page).toHaveURL(/\/login\?expired=1/);
    await expect(page.getByText('Your session expired. Please sign in again.')).toBeVisible();
  });
});

test.describe('first login with an admin-set password', () => {
  test('newbie must set their own password before anything else', async ({ page, request }) => {
    await uiLogin(page, 'newbie', NEWBIE_PASSWORD);
    await expect(page).toHaveURL(/\/change-password/);
    await expect(page.getByRole('heading', { name: 'Set your password' })).toBeVisible();
    await expect(page.getByText(/Your password was set by an administrator/)).toBeVisible();

    await page.goto('/farms');                                   // can't escape
    await expect(page).toHaveURL(/\/change-password/);

    const pw = page.locator('input[type=password]');
    await pw.nth(0).fill(NEWBIE_PASSWORD);
    await pw.nth(1).fill(NEWBIE_PASSWORD);
    await pw.nth(2).fill(NEWBIE_PASSWORD);
    await page.getByRole('button', { name: 'Change Password' }).click();
    await expect(page.getByText(/different from the current one/)).toBeVisible();

    await pw.nth(1).fill('Naveen-own-2026');
    await pw.nth(2).fill('Naveen-own-2026');
    await page.getByRole('button', { name: 'Change Password' }).click();
    await expect(page.getByRole('heading', { name: "Today's Dashboard" })).toBeVisible();

    const old = await request.post(`${API}/auth/login/`, { data: { username: 'newbie', password: NEWBIE_PASSWORD } });
    expect(old.status()).toBe(401);
    const fresh = await apiLogin(request, 'newbie', 'Naveen-own-2026');
    expect(fresh.user.must_change_password).toBe(false);
  });

  test('mismatched confirmation is caught', async ({ page }) => {
    await loginAs(page, 'sup_b', '/change-password');
    const pw = page.locator('input[type=password]');
    await pw.nth(0).fill('E2e-pass-2026!');
    await pw.nth(1).fill('Kiran-new-2026');
    await pw.nth(2).fill('Kiran-new-2027');
    await page.getByRole('button', { name: 'Change Password' }).click();
    await expect(page.getByText('New passwords do not match')).toBeVisible();
  });
});
