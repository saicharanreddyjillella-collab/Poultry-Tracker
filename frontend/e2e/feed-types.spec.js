// Feed types are the admin's list: rename BFP → BFP1, add BFP2, retire one; every screen follows.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, field, daysAgo, api } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

test('admin renames BFP to BFP1 and adds BFP2', async ({ page }) => {
  await loginAs(page, 'admin', '/settings');
  await page.getByRole('link', { name: 'Open feed types →' }).click();
  await expect(page.getByRole('heading', { name: 'Feed Types' })).toBeVisible();
  const rows = page.getByRole('region', { name: 'Feed type list' }).locator('tbody tr');
  await expect(rows).toHaveCount(3);

  await rows.filter({ hasText: 'BFP' }).getByRole('button', { name: 'Edit' }).click();
  const form = page.getByRole('form', { name: 'Feed type' });
  await form.getByLabel('Code *').fill('BFP1');
  await form.getByLabel('Name').fill('Finisher Pellet 1');
  await form.getByLabel('Kg per bird').fill('1.5');
  await form.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('status')).toHaveText('Saved BFP1.');
  await expect(rows.filter({ hasText: 'BFP1' })).toContainText('was BFP');

  await page.getByRole('button', { name: '+ Add feed type' }).click();
  await form.getByLabel('Code *').fill('BFP2');
  await form.getByLabel('Name').fill('Finisher Pellet 2');
  await form.getByRole('button', { name: 'Save' }).click();
  await expect(rows).toHaveCount(4);
  await expect(rows.nth(3)).toContainText('BFP2');
  await expect(rows.nth(3)).toContainText('the rest');
  await expect(rows.nth(3).getByRole('button', { name: 'Delete' })).toBeVisible();     // unused yet
  await expect(rows.nth(0).getByRole('button', { name: 'Delete' })).toHaveCount(0);    // BPSC has records
});

test('the supervisor sees the new names everywhere and can give two feeds in a day', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/flocks/${flock}?tab=entries`);
  await expect(page.locator('tbody tr').first()).toContainText('BFP1');                // old BFP entries
  await page.getByRole('button', { name: '+ Daily Entry' }).click();
  const f = page.locator('form.form-card');
  const types = await field(f, 'Feed Type').locator('option').allTextContents();
  expect(types.join('|')).toMatch(/BPSC.*\|BSC.*\|BFP1.*\|BFP2/);
  await field(f, 'Date *').fill(daysAgo(0));
  await field(f, 'Feed Type').selectOption('BFP');                                     // shown as BFP1
  await field(f, 'Bags').fill('4');
  await f.getByRole('button', { name: /Another feed/ }).click();
  await f.getByLabel('Feed Type 2').selectOption('BSC');
  await f.getByLabel('Bags 2').fill('3');
  await f.getByRole('button', { name: 'Save' }).click();
  const row = page.locator('tbody tr', { hasText: daysAgo(0) });
  await expect(row).toContainText('BFP1 4');
  await expect(row).toContainText('BSC 3');
  await page.getByRole('tab', { name: 'Feed' }).click();
  await expect(page.locator('.farm-stock-bar')).toContainText('BFP1:');
  await expect(page.locator('.farm-stock-bar')).toContainText('BFP2: 0');
});

test('the stock check uses the new name; retiring a type hides it from new records', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  const r = await api(request, 'sup_a', 'POST', '/daily-entries/', { flock, date: daysAgo(1), feed_bags: { BFP2: 1 } });
  expect(r.status).toBe(400);
  expect(JSON.stringify(r.body)).toContain('Only 0 BFP2 bags in stock');
  const types = (await api(request, 'admin', 'GET', '/feed-types/')).body;
  const bsc = types.find(t => t.key === 'BSC');
  await api(request, 'admin', 'PATCH', `/feed-types/${bsc.id}/`, { active: false });
  await loginAs(page, 'sup_a', '/feed');
  await page.getByRole('button', { name: '+ Order Feed' }).click();
  const options = await field(page.locator('form'), 'Feed Type *').locator('option').allTextContents();
  expect(options.join('|')).not.toContain('BSC');
  expect(options.join('|')).toContain('BFP2');
  await expect(page.locator('table').filter({ hasText: 'Pending Orders' }).locator('thead')).toContainText('BSC'); // still held at A1
});
