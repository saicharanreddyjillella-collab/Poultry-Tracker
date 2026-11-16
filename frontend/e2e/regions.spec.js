// Supervisors see and work on their own region only.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, farmIdOf } from './helpers';

test.beforeAll(() => reseed());

test('Zone-A supervisor sees only Zone-A farms on Farms and the dashboard', async ({ page }) => {
  await loginAs(page, 'sup_a', '/farms');
  await expect(page.getByRole('heading', { name: 'Farms (3)' })).toBeVisible();
  for (const f of ['Lakshmi Farm', 'Ganga Farm', 'Krishna Farm']) await expect(page.getByText(f).first()).toBeVisible();
  await expect(page.getByText('Venkat Farm')).toHaveCount(0);
  await page.goto('/feeds');
  await expect(page.getByRole('heading', { name: "Today's Dashboard" })).toBeVisible();
  await expect(page.getByText('Lakshmi Farm').first()).toBeVisible();
  await expect(page.getByText('Venkat Farm')).toHaveCount(0);
});

test('Zone-B supervisor sees only their farm', async ({ page }) => {
  await loginAs(page, 'sup_b', '/farms');
  await expect(page.getByRole('heading', { name: 'Farms (1)' })).toBeVisible();
  await expect(page.getByText('Venkat Farm').first()).toBeVisible();
  await expect(page.getByText('Lakshmi Farm')).toHaveCount(0);
});

test('admin sees every region', async ({ page }) => {
  await loginAs(page, 'admin', '/farms');
  await expect(page.getByRole('heading', { name: 'Farms (4)' })).toBeVisible();
});

test('opening another region by link shows "not found", never the data', async ({ page, request }) => {
  const farmB = await farmIdOf(request, 'B1');
  const flockB = await flockIdOf(request, 'B1');
  await loginAs(page, 'sup_a', `/farms/${farmB}`);
  await expect(page.getByText(/Farm not found/)).toBeVisible();
  await expect(page.getByText('Venkat')).toHaveCount(0);

  await page.goto(`/flocks/${flockB}`);
  await expect(page.getByText(/Flock not found/)).toBeVisible();
  await expect(page.getByRole('button', { name: '+ Daily Entry' })).toHaveCount(0);

  await page.goto(`/flocks/${flockB}/bill`);
  await expect(page.getByText('Bill not found.')).toBeVisible();
});

test('a supervisor can open their own billed flock and its bill', async ({ page, request }) => {
  const flockA2 = await flockIdOf(request, 'A2', 'closed');
  await loginAs(page, 'sup_a', `/flocks/${flockA2}`);
  await page.getByRole('link', { name: 'View Bill' }).click();
  await expect(page.getByText('Ganga Farm', { exact: false }).first()).toBeVisible();
  await expect(page.getByText(/Net Payable to Farmer/)).toBeVisible();
});

test('feed page: supervisor sees own region orders; the mill sees all', async ({ page }) => {
  await loginAs(page, 'sup_a', '/feed');
  const orders = page.locator('table').last();
  await expect(orders).toContainText('Lakshmi Farm');
  await expect(orders).not.toContainText('Venkat Farm');
  await loginAs(page, 'mill', '/feed');
  await expect(page.locator('table').last()).toContainText('Venkat Farm');
  await expect(page.locator('table').last()).toContainText('Lakshmi Farm');
});

test('farm dropdowns only offer the supervisor\'s farms', async ({ page }) => {
  await loginAs(page, 'sup_a', '/feed');
  await page.getByRole('button', { name: '+ Order Feed' }).click();
  const options = await page.locator('form select').first().locator('option').allTextContents();
  expect(options.join(' ')).toContain('Lakshmi');
  expect(options.join(' ')).not.toContain('Venkat');
});

test('reports only cover the supervisor\'s region', async ({ page }) => {
  await loginAs(page, 'sup_a', '/reports');
  await page.getByRole('button', { name: 'Region' }).click();
  await expect(page.locator('main')).toContainText('Zone-A');
  await expect(page.locator('main')).not.toContainText('Zone-B');
});
