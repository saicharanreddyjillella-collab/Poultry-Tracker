// Deleted records go to the Recycle Bin and an admin can bring them back.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, api, daysAgo } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

test('delete a daily entry → it appears in the bin → restore brings it back', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/flocks/${flock}?tab=entries`);
  await page.locator('tr', { hasText: daysAgo(18) }).getByRole('button', { name: 'Delete' }).click();
  await page.getByRole('button', { name: 'Yes, proceed' }).click();
  await expect(page.locator('tr', { hasText: daysAgo(18) })).toHaveCount(0);

  await loginAs(page, 'admin', '/trash');
  const row = page.locator('tbody tr').first();
  await expect(row).toContainText('Entry for');
  await expect(row).toContainText('sup_a');
  await row.getByRole('button', { name: 'Restore' }).click();
  await page.getByRole('button', { name: 'Restore' }).last().click();
  await expect(page.getByText(/^Restored /)).toBeVisible();

  const rows = (await api(request, 'admin', 'GET', `/daily-entries/?flock=${flock}`)).body;
  expect(rows.some(r => r.date === daysAgo(18))).toBe(true);
});

test('deleting a farm (API) shows as one bin row with everything under it', async ({ page, request }) => {
  const farms = (await api(request, 'admin', 'GET', '/farms/')).body;
  const b1 = farms.find(f => f.farm_code === 'B1');
  expect((await api(request, 'admin', 'DELETE', `/farms/${b1.id}/`)).status).toBe(204);
  await loginAs(page, 'admin', '/trash');
  const row = page.locator('tbody tr', { hasText: 'Venkat Farm' });
  await expect(row).toContainText(/flock/);
  await row.getByRole('button', { name: 'Restore' }).click();
  await page.getByRole('button', { name: 'Restore' }).last().click();
  await expect(page.getByText(/^Restored Farm B1/)).toBeVisible();
  expect((await api(request, 'sup_b', 'GET', '/farms/')).body.map(f => f.farm_code)).toContain('B1');
});

test('a billed farm cannot be deleted', async ({ request }) => {
  const farms = (await api(request, 'admin', 'GET', '/farms/')).body;
  const a2 = farms.find(f => f.farm_code === 'A2');
  const r = await api(request, 'admin', 'DELETE', `/farms/${a2.id}/`);
  expect(r.status).toBe(409);
});
