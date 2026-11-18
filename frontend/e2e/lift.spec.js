// Best day to lift. A 35-day-old flock (8,000 birds, weighed at 93% of standard) is placed on
// Ganga Farm for this file. With no market rate yet, the planner uses our own recent sales
// (seed: A3 sold yesterday at ₹102/kg).
import { test, expect, request as pwRequest } from '@playwright/test';
import { reseed, loginAs, field, api, farmIdOf, daysAgo } from './helpers';

test.describe.configure({ mode: 'serial' });

test.beforeAll(async () => {
  reseed();
  const request = await pwRequest.newContext();
  const farm = await farmIdOf(request, 'A2');
  const f = await api(request, 'admin', 'POST', '/flocks/', { farm, placement_date: daysAgo(35), chick_count: 8000 });
  expect(f.status).toBe(201);
  const e = await api(request, 'admin', 'POST', '/daily-entries/',
    { flock: f.body.id, date: daysAgo(0), mortality_count: 8, avg_body_weight_grams: '1856' });
  expect(e.status).toBe(201);
  await request.dispose();
});

const ganga = (page) => page.locator('tr.lift-row', { hasText: 'Ganga Farm' });

test('without a market rate it uses our own recent sales', async ({ page }) => {
  await loginAs(page, 'admin', '/insights');
  await page.getByRole('link', { name: /Best Day to Lift/ }).click();
  await expect(page.getByRole('heading', { name: 'Best Day to Lift' })).toBeVisible();
  await expect(page.locator('.stat-value', { hasText: '₹102/kg' })).toBeVisible();
  await expect(page.getByText('Average of our sales in the last 7 days')).toBeVisible();
  await expect(ganga(page)).toContainText('35d');
  await expect(ganga(page)).toContainText('93% of standard');
  await expect(page.locator('tr.lift-row', { hasText: 'Lakshmi Farm' })).toHaveCount(0);   // 20 days: too young
});

test('a good market rate says hold, with the extra rupees', async ({ page }) => {
  await loginAs(page, 'admin', '/lift-planner');
  await field(page, 'Rate ₹/kg').fill('125');
  await page.getByRole('button', { name: 'Save Rate' }).click();
  await expect(page.getByText(`Saved ₹125/kg for ${daysAgo(0)}.`)).toBeVisible();
  await expect(page.getByText('Market rate (today)')).toBeVisible();
  await expect(ganga(page)).toContainText(/Best around .* more than lifting today|check again/);
  await expect(ganga(page)).toContainText(/\+₹[\d,]+/);
  await ganga(page).click();
  const days = page.locator('tr', { has: page.locator('table') }).locator('tbody tr');
  await expect(days).toHaveCount(11);                                    // today + 10 days
});

test('a poor rate for the same day corrects it and says lift now', async ({ page }) => {
  await loginAs(page, 'admin', '/lift-planner');
  await field(page, 'Rate ₹/kg').fill('70');
  await page.getByRole('button', { name: 'Save Rate' }).click();
  await expect(page.locator('.stat-value', { hasText: '₹70/kg' })).toBeVisible();
  await expect(ganga(page)).toContainText('Now');
  await expect(ganga(page)).toContainText('Lift now');
});

test('an impossible rate is explained', async ({ page }) => {
  await loginAs(page, 'admin', '/lift-planner');
  await field(page, 'Rate ₹/kg').fill('4');
  await page.getByRole('button', { name: 'Save Rate' }).click();
  await expect(page.getByText(/20–500/)).toBeVisible();
});

test('supervisors cannot open it', async ({ page, request }) => {
  await loginAs(page, 'sup_a', '/lift-planner');
  await expect(page.getByRole('heading', { name: "Today's Dashboard" })).toBeVisible();
  expect((await api(request, 'sup_a', 'GET', '/reports/lift-planner/')).status).toBe(403);
});
