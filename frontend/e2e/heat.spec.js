// Heat-stress forecast. The test server uses a fixed hot week (WEATHER_FAKE):
// day 0 watch · day 1 danger · day 2 emergency · day 3 danger · day 4 watch.
// Seed: Zone-A has a weather point, Zone-B does not.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, field } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

test('supervisor gets a heat alert on the dashboard and sees what to do', async ({ page }) => {
  await loginAs(page, 'sup_a', '/feeds');
  const banner = page.getByRole('status').filter({ hasText: 'Heat alert' });
  await expect(banner).toContainText(/2 farms at danger level or worse in the next 3 days \(2 at emergency\)/);
  await banner.getByRole('link', { name: /See what to do/ }).click();
  await expect(page.getByRole('heading', { name: 'Heat Stress Forecast' })).toBeVisible();
  const lakshmi = page.locator('tr', { hasText: 'Lakshmi Farm' });
  await expect(lakshmi.locator('.heat')).toHaveText(['Watch', 'Danger', 'Emergency', 'Danger', 'Watch']);
  await expect(page.locator('tr', { hasText: 'Krishna Farm' }).locator('.heat').nth(1)).toHaveText('Emergency'); // 43-day birds
  await expect(page.getByText(/consider lifting heavy birds early/)).toBeVisible();
  await expect(page.getByText('Venkat Farm')).toHaveCount(0);                  // other region
  await expect(page.getByRole('heading', { name: 'Region locations' })).toHaveCount(0);
});

test('admin sets the missing Zone-B location and its farm appears', async ({ page }) => {
  await loginAs(page, 'admin', '/insights');
  await page.getByRole('link', { name: /Heat Stress/ }).click();
  await expect(page.getByText(/No location set for Zone-B/)).toBeVisible();
  await expect(page.getByText('Venkat Farm')).toHaveCount(0);
  const row = page.locator('.loc-row[data-region="Zone-B"]');
  await field(row, 'Latitude').fill('18.43860');
  await field(row, 'Longitude').fill('79.12880');
  await row.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('Saved Zone-B.')).toBeVisible();
  await expect(page.getByText(/No location set/)).toHaveCount(0);
  await expect(page.locator('tr', { hasText: 'Venkat Farm' })).toBeVisible();
});

test('a wrong number is explained', async ({ page }) => {
  await loginAs(page, 'admin', '/heat-stress');
  const row = page.locator('.loc-row[data-region="Zone-A"]');
  await field(row, 'Latitude').fill('117.4');
  await row.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText(/Must be between -90 and 90/)).toBeVisible();
});

test('feed-mill user is kept on Feed', async ({ page }) => {
  await loginAs(page, 'mill', '/heat-stress');
  await expect(page).toHaveURL(/\/feed$/);
});
