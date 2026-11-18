// Chick quality by hatchery. Seed: A1 + A2 from Sri Venkateswara, A3 from Balaji Chicks, B1 not recorded.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, farmIdOf, field, daysAgo } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

const card = (page) => page.locator('.chick-quality');

test('supervisor records hatchery, dead on arrival and chick weight when placing a flock', async ({ page, request }) => {
  const farm = await farmIdOf(request, 'A3');                 // 3,000 active of 10,000 capacity
  await loginAs(page, 'sup_a', `/farms/${farm}`);
  await page.getByRole('button', { name: '+ New Flock' }).click();
  const f = page.locator('form.form-card');
  await field(f, 'Placement Date *').fill(daysAgo(0));
  await field(f, 'Chicks Placed *').fill('4000');
  await field(f, 'Hatchery').selectOption({ label: 'Balaji Chicks' });
  await field(f, 'Dead on Arrival').fill('25');
  await field(f, 'Avg Chick Weight (g)').fill('39');
  await f.getByRole('button', { name: 'Place Flock' }).click();
  await expect(f).toHaveCount(0);
  await page.getByText('4,000 chicks').first().click();
  await expect(card(page)).toContainText('Hatchery: Balaji Chicks');
  await expect(card(page)).toContainText('Dead on arrival: 25 (0.63%)');
  await expect(card(page)).toContainText(/Avg chick weight: 39(\.0)? g/);
});

test('supervisor corrects the chick details of a running flock', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/flocks/${flock}`);
  await expect(card(page)).toContainText('Hatchery: Sri Venkateswara');
  await card(page).getByRole('button', { name: 'Edit' }).click();
  await field(card(page), 'Dead on Arrival').fill('50');
  await card(page).getByRole('button', { name: 'Save' }).click();
  await expect(card(page)).toContainText('Dead on arrival: 50 (1.00%)');
});

test('an impossible chick weight is explained', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/flocks/${flock}`);
  await card(page).getByRole('button', { name: 'Edit' }).click();
  await field(card(page), 'Avg Chick Weight (g)').fill('400');
  await card(page).getByRole('button', { name: 'Save' }).click();
  await expect(card(page).locator('.error-msg')).toContainText('20–80 g');
});

test('admin compares hatcheries in Insights → Chick Quality', async ({ page }) => {
  await loginAs(page, 'admin', '/insights');
  await page.getByRole('link', { name: /Chick Quality/ }).click();
  await expect(page.getByRole('heading', { name: 'Chick Quality by Hatchery' })).toBeVisible();
  const rows = page.locator('tr.hatchery-row');
  await expect(rows).toHaveCount(3);
  await expect(rows.last()).toContainText('Not recorded');
  const sv = rows.filter({ hasText: 'Sri Venkateswara' });
  await expect(sv).toContainText('OK');
  await sv.click();
  await expect(page.getByRole('link', { name: 'Lakshmi Farm' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Ganga Farm' })).toBeVisible();
});

test('admin manages the hatchery list; a retired one is not offered for new flocks', async ({ page, request }) => {
  await loginAs(page, 'admin', '/hatcheries');
  await field(page.locator('form.loc-row'), 'New hatchery').fill('Suguna');
  await page.getByRole('button', { name: 'Add' }).click();
  await expect(page.getByText('Added Suguna.')).toBeVisible();
  const balaji = page.locator('tr', { hasText: 'Balaji Chicks' }).last();
  await balaji.getByRole('button', { name: 'Remove' }).click();
  await expect(page.getByText(/has flocks, so it can't be removed/)).toBeVisible();
  await balaji.getByRole('button', { name: 'Mark not used' }).click();
  await expect(page.getByText('Balaji Chicks updated.')).toBeVisible();

  const farm = await farmIdOf(request, 'A3');
  await loginAs(page, 'sup_a', `/farms/${farm}`);
  await page.getByRole('button', { name: '+ New Flock' }).click();
  const opts = await field(page.locator('form.form-card'), 'Hatchery').locator('option').allTextContents();
  expect(opts).toEqual(['Select hatchery...', 'Sri Venkateswara', 'Suguna']);
});
