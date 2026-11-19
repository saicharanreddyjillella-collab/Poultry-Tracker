// Farms page as a table: status, region and search filters (kept in the address).
import { test, expect } from '@playwright/test';
import { reseed, loginAs } from './helpers';

test.beforeAll(() => reseed());

const rows = (page) => page.getByRole('region', { name: 'Farm list' }).locator('tbody tr');

test('admin filters farms by status, region and search', async ({ page }) => {
  await loginAs(page, 'admin', '/farms');
  await expect(page.getByRole('heading', { name: 'Farms (4)' })).toBeVisible();
  await expect(rows(page)).toHaveCount(4);
  await page.getByRole('button', { name: /^Empty/ }).click();
  await expect(rows(page)).toHaveCount(1);
  await expect(rows(page).first()).toContainText('Ganga Farm');
  await expect(rows(page).first()).toContainText('Empty');
  await page.getByRole('button', { name: /^Running/ }).click();
  await expect(rows(page)).toHaveCount(3);
  await page.getByLabel('Region').selectOption('Zone-B');
  await expect(rows(page)).toHaveCount(1);
  await expect(page).toHaveURL(/status=running/);
  await expect(page).toHaveURL(/region=Zone-B/);
  await page.getByRole('button', { name: /^All/ }).click();
  await page.getByLabel('Region').selectOption('');
  await page.getByLabel('Search farms', { exact: true }).last().fill('lakshmi');
  await expect(rows(page)).toHaveCount(1);
  // the running chip opens the flock, the name opens the farm
  await rows(page).first().getByText(/Running · day/).click();                // Lakshmi: birds on the farm
  await expect(page).toHaveURL(/\/flocks\/\d+/);
});

test('the top bar search opens the filtered table', async ({ page }) => {
  await loginAs(page, 'admin', '/feeds');
  const top = page.getByRole('search').getByLabel('Search farms');
  await top.fill('Venkat');
  await top.press('Enter');
  await expect(page).toHaveURL(/\/farms\?q=Venkat/);
  await expect(rows(page)).toHaveCount(1);
  await rows(page).first().getByRole('link', { name: 'Venkat Farm' }).click();
  await expect(page).toHaveURL(/\/farms\/\d+$/);
});
