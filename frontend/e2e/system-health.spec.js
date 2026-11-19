// System Health (admin): checks, recent errors, who is active.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, api, API } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

const card = (page, key) => page.locator(`.health-check[data-check="${key}"]`);

test('admin reaches it from Settings and sees every check', async ({ page, request }) => {
  await api(request, 'sup_a', 'GET', '/farms/');                         // Ravi signs in
  await request.post(`${API}/client-errors/`, { data: { message: 'TypeError: e2e screen error', path: '/flocks/9' } });

  await loginAs(page, 'admin', '/settings');
  await page.getByRole('link', { name: 'System Health →' }).click();
  await expect(page.getByRole('heading', { name: 'System Health' })).toBeVisible();
  await expect(page.locator('.health-overall')).toContainText(/Needs a look|Needs action|All good/);

  await expect(card(page, 'database')).toContainText('Answering');
  await expect(card(page, 'backup')).toContainText('Not set up on this computer');
  await expect(card(page, 'entries')).toContainText(/Missing for 3: Krishna Farm, Lakshmi Farm, Venkat Farm/);
  await expect(card(page, 'weather')).toContainText('Forecast service reachable');
  await expect(card(page, 'features')).toContainText('On: Feed Audit (bag counts), Best Day to Lift, Who Gets the Next Chicks');
  await expect(card(page, 'errors')).toContainText('1 on screens');

  const err = page.locator('tr', { hasText: 'e2e screen error' });
  await expect(err).toContainText('Screen');
  await expect(err).toContainText('/flocks/9');

  const ravi = page.locator('tr', { hasText: 'sup_a' });
  await expect(ravi).toContainText('supervisor');
  await expect(ravi.locator('td').nth(2)).not.toHaveText('—');          // has a last sign-in
});

test('switching a feature off shows up on the page', async ({ page, request }) => {
  await api(request, 'admin', 'PATCH', '/settings/features/lift_planner/', { enabled: false });
  await loginAs(page, 'admin', '/system-health');
  await expect(card(page, 'features')).toContainText('Off: Best Day to Lift');
  await api(request, 'admin', 'PATCH', '/settings/features/lift_planner/', { enabled: true });
});

test('supervisors cannot open it', async ({ page, request }) => {
  await loginAs(page, 'sup_a', '/system-health');
  await expect(page.getByRole('heading', { name: "Today's Dashboard" })).toBeVisible();
  expect((await api(request, 'sup_a', 'GET', '/settings/health/')).status).toBe(403);
});
