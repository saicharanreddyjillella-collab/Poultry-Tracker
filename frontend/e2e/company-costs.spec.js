// Company costs and grower PAN are admin-only; supervisors keep the grower's payment and their own entries.
// Seed: A2 (Ganga) is billed; A1 (Lakshmi) has PAN ABCPR1234A; BFP rate ₹44/kg this week.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, farmIdOf, field } from './helpers';

test.beforeAll(() => reseed());

test('supervisor bill shows what the grower gets, not the company cost', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A2', 'closed');
  await loginAs(page, 'sup_a', `/flocks/${flock}/bill`);
  await expect(page.getByText('Net Payable to Farmer')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Production Cost' })).toHaveCount(0);
  await expect(page.getByText('Avg Selling Price')).toHaveCount(0);
  await expect(page.getByText(/Chick Cost/)).toHaveCount(0);
  await expect(page.getByText(/undefined|NaN/)).toHaveCount(0);

  await loginAs(page, 'admin', `/flocks/${flock}/bill`);
  await expect(page.getByRole('heading', { name: 'Production Cost' })).toBeVisible();
  await expect(page.getByText('Avg Selling Price')).toBeVisible();
});

test('supervisor till-date report has no sale amount, feed cost or feed prices', async ({ page }) => {
  await loginAs(page, 'sup_a', '/reports');
  await page.getByRole('button', { name: 'Till Date', exact: true }).click();
  await expect(page.getByText('Birds Placed').first()).toBeVisible();
  for (const t of ['Sale Amount', 'Feed Cost', 'Cost per kg', 'Current Feed Rates']) {
    await expect(page.locator('.stat-label', { hasText: new RegExp(`^${t}$`) })).toHaveCount(0);
  }
  await expect(page.locator('.stat-label', { hasText: /^FCR$/ })).toBeVisible();
  await loginAs(page, 'admin', '/reports');
  await page.getByRole('button', { name: 'Till Date', exact: true }).click();
  for (const t of ['Sale Amount', 'Feed Cost', 'Cost per kg']) {
    await expect(page.locator('.stat-label', { hasText: new RegExp(`^${t}$`) })).toBeVisible();
  }
});

test('feed stock works for supervisors without showing feed prices', async ({ page }) => {
  await loginAs(page, 'sup_a', '/feed');
  await expect(page.getByRole('heading', { name: 'Feed Stock & Orders' })).toBeVisible();
  await expect(page.getByText('Lakshmi Farm').first()).toBeVisible();          // stock still loads
  await expect(page.getByText('Current Feed Rates')).toHaveCount(0);
  await loginAs(page, 'mill', '/feed');
  await expect(page.getByText('Current Feed Rates')).toBeVisible();
  await expect(page.getByText(/₹44(\.00)?\/kg/).first()).toBeVisible();
});

test('PAN is admin only, and a supervisor saving the farm keeps it', async ({ page, request }) => {
  const farm = await farmIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/farms/${farm}/edit`);
  await expect(field(page, 'Farm Name *')).toHaveValue('Lakshmi Farm');
  await expect(page.getByText('PAN', { exact: true })).toHaveCount(0);
  await field(page, 'Location').fill('Near the water tank');
  await page.getByRole('button', { name: 'Update Farm' }).click();
  await expect(page).toHaveURL(/\/farms$/);

  await loginAs(page, 'admin', `/farms/${farm}/edit`);
  await expect(field(page, 'PAN')).toHaveValue('ABCPR1234A');
  await expect(field(page, 'Location')).toHaveValue('Near the water tank');
});
