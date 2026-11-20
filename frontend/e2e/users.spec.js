// Admin manages users: create with a generated password → the new user's
// first login → reset password → delete.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, uiLogin, api, API } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

let tempPassword;

test('admin creates a supervisor with a generated password', async ({ page }) => {
  await loginAs(page, 'admin', '/users');
  await page.getByRole('button', { name: '+ Add User' }).click();
  const form = page.locator('form.form-card');
  await expect(form).toHaveAttribute('autocomplete', 'off');               // no browser autofill of admin's login
  await form.locator('input').nth(0).fill('ravi_e2e');
  await page.getByRole('button', { name: 'Generate' }).click();
  await form.locator('label:has(input[type=checkbox])').filter({ hasText: 'Zone-A' }).first().click();
  await page.getByRole('button', { name: 'Create User' }).click();
  const card = page.getByRole('status');
  await expect(card).toContainText('User ravi_e2e created');
  tempPassword = (await page.getByTestId('shared-password').innerText()).trim();
  expect(tempPassword).toMatch(/^.{4}-.{4}-.{4}$/);
  await expect(page.locator('tr', { hasText: 'ravi_e2e' })).toContainText('temporary password');
});

test('weak password and missing password are explained', async ({ page }) => {
  await loginAs(page, 'admin', '/users');
  await page.getByRole('button', { name: '+ Add User' }).click();
  const form = page.locator('form.form-card');
  await form.locator('input').nth(0).fill('weak_user');
  await page.getByRole('button', { name: 'Create User' }).click();
  await expect(page.getByText(/needs it to log in/)).toBeVisible();
  await form.locator('input').nth(1).fill('1234');
  await page.getByRole('button', { name: 'Create User' }).click();
  await expect(page.locator('.error-msg')).toContainText(/too short|too common|numeric/);
});

test('the new supervisor signs in, sets their own password, works in Zone-A', async ({ page }) => {
  await uiLogin(page, 'ravi_e2e', tempPassword);
  await expect(page.getByRole('heading', { name: 'Set your password' })).toBeVisible();
  const pw = page.locator('input[type=password]');
  await pw.nth(0).fill(tempPassword);
  await pw.nth(1).fill('Ravi-own-2026');
  await pw.nth(2).fill('Ravi-own-2026');
  await page.getByRole('button', { name: 'Change Password' }).click();
  await expect(page.getByRole('heading', { name: "Today's Dashboard" })).toBeVisible();
  await page.goto('/farms');
  await expect(page.getByRole('heading', { name: 'Farms (4)' })).toBeVisible();       // every farm (covering)
});

test('admin resets their password: old one stops working, new one is temporary', async ({ page, request }) => {
  await loginAs(page, 'admin', '/users');
  await page.locator('tr', { hasText: 'ravi_e2e' }).getByRole('button', { name: 'Reset password' }).click();
  await page.getByRole('button', { name: 'Reset password' }).last().click();
  await expect(page.getByRole('status')).toContainText('New password for ravi_e2e');
  const fresh = (await page.getByTestId('shared-password').innerText()).trim();
  expect((await request.post(`${API}/auth/login/`, { data: { username: 'ravi_e2e', password: 'Ravi-own-2026' } })).status()).toBe(401);
  const r = await request.post(`${API}/auth/login/`, { data: { username: 'ravi_e2e', password: fresh } });
  expect((await r.json()).user.must_change_password).toBe(true);
});

test('admins have no reset button (they change their own password)', async ({ page }) => {
  await loginAs(page, 'admin', '/users');
  const row = page.locator('tr').filter({ has: page.locator('strong', { hasText: /^admin$/ }) });
  await expect(row.getByRole('button', { name: 'Reset password' })).toHaveCount(0);
});

test('admin deletes the user', async ({ page, request }) => {
  await loginAs(page, 'admin', '/users');
  await page.locator('tr', { hasText: 'ravi_e2e' }).getByRole('button', { name: 'Delete' }).click();
  await page.getByRole('button', { name: 'Delete' }).last().click();
  await expect(page.locator('tr', { hasText: 'ravi_e2e' })).toHaveCount(0);
  const users = (await api(request, 'admin', 'GET', '/auth/users/')).body;
  expect(users.some(u => u.username === 'ravi_e2e')).toBe(false);
});
