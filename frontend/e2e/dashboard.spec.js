// Control-room dashboard: figures, regions, alerts and the flock table with next actions.
import { test, expect } from '@playwright/test';
import { reseed, loginAs } from './helpers';

test.beforeAll(() => reseed());

test('admin sees the control room with a next action for every flock', async ({ page }) => {
  await loginAs(page, 'admin', '/feeds');
  await expect(page.getByRole('heading', { name: "Today's Dashboard" })).toBeVisible();
  for (const t of ['Live birds', 'Mortality today', 'Daily entries', 'Feed used today', 'Feed on farms'])
    await expect(page.locator('.stat-label', { hasText: t })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Regions' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Alerts' })).toBeVisible();
  const table = page.getByRole('region', { name: 'Flocks on the ground' }).locator('table');
  const rows = table.locator('tbody tr');
  expect(await rows.count()).toBeGreaterThan(0);
  for (let i = 0; i < await rows.count(); i++) await expect(rows.nth(i).locator('.chip')).toHaveCount(1);
  // the farm name opens its flock
  const first = rows.first().locator('a.cell-title');
  const name = await first.textContent();
  await first.click();
  await expect(page).toHaveURL(/\/flocks\/\d+/);
  await expect(page.getByText(name).first()).toBeVisible();
});

test('supervisor sees only their regions in the Regions panel', async ({ page }) => {
  await loginAs(page, 'sup_b', '/feeds');
  const regions = page.getByRole('region', { name: 'Regions' });
  await expect(regions.locator('.region-name')).toHaveText(['Zone-B']);
  await expect(page.getByText(/Rates ₹\/kg/)).toHaveCount(0);
});
