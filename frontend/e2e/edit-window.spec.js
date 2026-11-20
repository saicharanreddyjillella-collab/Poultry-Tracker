// Edit window: recent records save at once; older ones go to an admin with a reason.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, field, daysAgo, api } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

test('an old entry asks for a reason and waits for the admin', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/flocks/${flock}`);
  await page.getByRole('button', { name: '+ Daily Entry' }).click();
  const f = page.locator('form.form-card');
  await field(f, 'Date *').fill(daysAgo(6));
  await field(f, 'Mortality').fill('4');
  await f.getByRole('button', { name: 'Save' }).click();
  const dialog = page.getByRole('dialog', { name: 'Needs admin approval' });
  await expect(dialog).toContainText('outside the 3-day edit window');
  await dialog.getByLabel('Reason *').fill('Forgot to enter on the day');
  await dialog.getByRole('button', { name: 'Send for approval' }).click();
  await expect(page.getByRole('status')).toContainText('Sent to an admin for approval');
  const waiting = page.getByRole('region', { name: 'Waiting for admin approval' });
  await expect(waiting).toContainText('Add daily entry');
  await expect(waiting).toContainText('Mortality 4');
  await expect(waiting).toContainText('Forgot to enter on the day');
  await expect(waiting.getByRole('button', { name: 'Approve' })).toHaveCount(0);      // supervisors can't
  await page.getByRole('tab', { name: /Daily entries/ }).click();
  await expect(page.locator('tbody tr', { hasText: daysAgo(6) })).toHaveCount(0);       // not saved yet
});

test('the admin sees it on the dashboard and approves it', async ({ page, request }) => {
  await loginAs(page, 'admin', '/feeds');
  await page.getByRole('link', { name: 'Approvals' }).first().click();
  await expect(page).toHaveURL(/\/approvals$/);
  const waiting = page.getByRole('region', { name: 'Changes waiting for approval' });
  await expect(waiting).toContainText('Lakshmi Farm');
  await waiting.getByRole('button', { name: 'Approve' }).click();
  await expect(page.getByText('Nothing is waiting for approval.')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Recently decided' })).toContainText('Approved');
  const flock = await flockIdOf(request, 'A1');
  const rows = (await api(request, 'admin', 'GET', `/flocks/${flock}/cumulative/`)).body.entries;
  const row = rows.find(r => r.date === daysAgo(6));
  expect(row.daily_mortality).toBe(4);
  expect(row.entered_by_name).toBe('Ravi');
});

test('cancelling the reason saves nothing', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/flocks/${flock}`);
  await page.getByRole('button', { name: '+ Medicine' }).click();
  const f = page.locator('form.form-card');
  await field(f, 'Date *').fill(daysAgo(9));
  await field(f, 'Medicine Name *').fill('Vitamin');
  await f.getByRole('button', { name: 'Save' }).click();
  await page.getByRole('dialog', { name: 'Needs admin approval' }).getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('region', { name: 'Waiting for admin approval' })).toHaveCount(0);
  await expect(f).toBeVisible();                                                         // form kept
});

test('the admin widens the window in Settings → Rules', async ({ page, request }) => {
  await loginAs(page, 'admin', '/settings');
  const rules = page.getByRole('form', { name: 'Rules' });
  await rules.getByLabel('Edit window (days)').fill('10');
  await rules.getByRole('button', { name: 'Save rules' }).click();
  await expect(rules.getByRole('status')).toHaveText('Saved.');
  const flock = await flockIdOf(request, 'A1');
  const r = await api(request, 'sup_a', 'POST', '/daily-entries/', { flock, date: daysAgo(8), mortality_count: 1 });
  expect(r.status).toBe(201);
});
