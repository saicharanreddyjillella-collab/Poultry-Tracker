// Adding and editing farms; region rules for supervisors.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, field, api, farmIdOf } from './helpers';

test.beforeAll(() => reseed());

async function fillFarm(page, { code, name, owner = 'Owner', capacity = '5000', region }) {
  await field(page, 'Farm Code *').fill(code);
  await field(page, 'Farm Name *').fill(name);
  await field(page, 'Owner / Farmer Name *').fill(owner);
  await field(page, 'Capacity (birds) *').fill(capacity);
  if (region) {
    const r = field(page, 'Region *');
    if ((await r.evaluate(e => e.tagName)) === 'SELECT') await r.selectOption(region);
    else await r.fill(region);
  }
}

test('admin adds a farm', async ({ page, request }) => {
  await loginAs(page, 'admin', '/farms/new');
  await fillFarm(page, { code: 'C1', name: 'Saraswati Farm', region: 'Zone-A' });
  await page.getByRole('button', { name: 'Create Farm' }).click();
  await expect(page).not.toHaveURL(/\/farms\/new/);
  const farms = (await api(request, 'admin', 'GET', '/farms/')).body;
  expect(farms.some(f => f.farm_code === 'C1' && f.name === 'Saraswati Farm')).toBe(true);
});

test('duplicate farm code shows a message (not a crash)', async ({ page }) => {
  await loginAs(page, 'admin', '/farms/new');
  await fillFarm(page, { code: 'A1', name: 'Copy', region: 'Zone-A' });
  await page.getByRole('button', { name: 'Create Farm' }).click();
  await expect(page.locator('.error-msg')).toContainText(/already exists|already in use/);
  await expect(page).toHaveURL(/\/farms\/new/);
});

test('supervisor can only pick their own regions', async ({ page }) => {
  await loginAs(page, 'sup_a', '/farms/new');
  const region = field(page, 'Region *');
  await expect(region.locator('option', { hasText: 'Zone-A' })).toHaveCount(1);   // regions load after the page
  const options = await region.locator('option').allTextContents();
  expect(options.join(' ')).toContain('Zone-A');
  expect(options.join(' ')).not.toContain('Zone-B');
});

test('supervisor adds a farm in their region', async ({ page, request }) => {
  await loginAs(page, 'sup_a', '/farms/new');
  await fillFarm(page, { code: 'A9', name: 'Durga Farm', region: 'Zone-A' });
  await page.getByRole('button', { name: 'Create Farm' }).click();
  await expect(page).not.toHaveURL(/\/farms\/new/);
  const farms = (await api(request, 'sup_a', 'GET', '/farms/')).body;
  expect(farms.some(f => f.farm_code === 'A9')).toBe(true);
});

test('edit a farm', async ({ page, request }) => {
  const id = await farmIdOf(request, 'A2');
  await loginAs(page, 'sup_a', `/farms/${id}/edit`);
  await expect(field(page, 'Owner / Farmer Name *')).toHaveValue('Suresh');   // saved details loaded
  await field(page, 'Owner / Farmer Name *').fill('Suresh Kumar');
  await page.getByRole('button', { name: /Save|Update/ }).click();
  await expect(page).not.toHaveURL(/\/edit$/);
  expect((await api(request, 'admin', 'GET', `/farms/${id}/`)).body.owner_name).toBe('Suresh Kumar');
});

test('start a new flock on a farm', async ({ page, request }) => {
  const id = await farmIdOf(request, 'A2');                  // A2's only flock is closed
  await loginAs(page, 'sup_a', `/farms/${id}`);
  await page.getByRole('button', { name: '+ New Flock' }).click();
  await field(page, 'Placement Date *').fill(new Date().toISOString().slice(0, 10));
  await field(page, 'Chicks Placed *').fill('9800');
  await page.locator('form').getByRole('button', { name: /Create|Start|Save|Place/ }).click();
  await expect(page.getByText(/Day 0|Day 1/).first()).toBeVisible();
  const flocks = (await api(request, 'admin', 'GET', `/flocks/?farm=${id}&status=active`)).body;
  expect(flocks).toHaveLength(1);
});
