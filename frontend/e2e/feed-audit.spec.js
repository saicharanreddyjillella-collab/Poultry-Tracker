// Feed leakage detector: the supervisor counts bags, the admin sees the gap in the Feed Audit.
// Seed: A1's flock received 200 BFP + 100 BSC and has 3 entries of 5 BFP → paper 185 BFP + 100 BSC.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, field, api, daysAgo } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

const countForm = (page) => page.locator('form.form-card', { has: page.getByRole('heading', { name: 'Record Bag Count' }) });

test('supervisor records a bag count and is told it is short', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/flocks/${flock}?tab=feed`);
  await page.getByRole('button', { name: '+ Bag Count' }).click();
  const f = countForm(page);
  await expect(field(f, 'Date *')).toHaveValue(daysAgo(0));
  await field(f, 'BSC bags').fill('100');
  await field(f, 'BFP bags').fill('170');                         // paper 185 → 15 short
  await f.getByRole('button', { name: 'Save Count' }).click();
  await expect(page.getByText(/Count saved\. Paper stock 285 bags, counted 270/)).toBeVisible();
  await expect(page.locator('.bag-counts table')).toContainText('15 bags short');
});

test('a second count for the same day is explained', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/flocks/${flock}?tab=feed`);
  await page.getByRole('button', { name: '+ Bag Count' }).click();
  await field(countForm(page), 'BFP bags').fill('185');
  await countForm(page).getByRole('button', { name: 'Save Count' }).click();
  await expect(countForm(page).locator('.error-msg')).toContainText(/already exists/);
});

test('supervisor cannot remove a count; the API refuses too', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/flocks/${flock}?tab=feed`);
  await expect(page.locator('.bag-counts table')).toBeVisible();
  await expect(page.locator('.bag-counts').getByRole('button', { name: 'Remove' })).toHaveCount(0);
  const [c] = (await api(request, 'admin', 'GET', `/feed-counts/?flock=${flock}`)).body;
  expect((await api(request, 'sup_a', 'DELETE', `/feed-counts/${c.id}/`)).status).toBe(403);
});

test('admin finds it in Insights → Feed Audit, worst first, with its rupee value', async ({ page }) => {
  await loginAs(page, 'admin', '/feeds');
  await page.getByRole('link', { name: 'Insights' }).click();
  await page.getByRole('link', { name: /Feed Audit/ }).click();
  await expect(page.getByRole('heading', { name: 'Feed Audit' })).toBeVisible();
  const first = page.locator('tbody tr').first();
  await expect(first).toContainText('Lakshmi Farm');
  await expect(first).toContainText(/15 bags short at the count/);
  await expect(first).toContainText(/₹[\d,]+/);
  await first.getByRole('link', { name: 'Lakshmi Farm' }).click();
  await expect(page.getByRole('heading', { name: 'Lakshmi Farm — Flock' })).toBeVisible();
});

test('region filter and "Problems only"', async ({ page }) => {
  await loginAs(page, 'admin', '/feed-audit');
  await expect(page.locator('tbody tr').first()).toBeVisible();
  await field(page, 'Region').selectOption('Zone-B');
  await expect(page.getByText('No feed problems found.')).toBeVisible();     // Zone-B has none
  await page.getByLabel('Problems only').uncheck();
  await expect(page.locator('tbody')).toContainText('Venkat Farm');
});

test('admin removes a count', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'admin', `/flocks/${flock}?tab=feed`);
  page.once('dialog', d => d.accept());
  await page.locator('.bag-counts').getByRole('button', { name: 'Remove' }).click();
  await expect(page.locator('.bag-counts table')).toHaveCount(0);
});
