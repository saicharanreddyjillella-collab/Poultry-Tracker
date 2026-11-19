// Who gets the next chicks (admin only). Seed: Ganga Farm (A2) has the only settled flock
// (settled today, capacity 10,000); Lakshmi, Krishna and Venkat have running flocks.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, field, api } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

const plan = async (page, { chicks, rest }) => {
  const f = page.locator('form.loc-row');
  await field(f, 'Chicks available').fill(chicks);
  if (rest !== undefined) await field(f, 'Rest days after a flock').fill(rest);
  await f.getByRole('button', { name: 'Plan' }).click();
};

test('admin sees growers ranked from settled flocks, and new growers apart', async ({ page }) => {
  await loginAs(page, 'admin', '/insights');
  await page.getByRole('link', { name: /Who Gets the Next Chicks/ }).click();
  const ganga = page.locator('tr.grower-row', { hasText: 'Ganga Farm' });
  await expect(ganga).toContainText('90');                       // FCR 100 · mortality 100 · consistency 50
  await expect(ganga).toContainText(/Resting: settled 0 days ago, needs 14/);
  await ganga.click();
  await expect(page.getByText(/Score parts \(vs your other growers\): feed efficiency 100/)).toBeVisible();
  const lakshmi = page.locator('tr', { hasText: 'Lakshmi Farm' });
  await expect(lakshmi).toContainText('Flock running (20 days old)');
});

test('a resting farm gets nothing; with no rest it is filled and the rest is left over', async ({ page }) => {
  await loginAs(page, 'admin', '/grower-ranking');
  await plan(page, { chicks: '10000' });
  await expect(page.getByText(/No free farm can take these chicks/)).toBeVisible();

  await plan(page, { chicks: '25000', rest: '0' });
  const rows = page.locator('.placement-plan tbody tr');
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText('Ganga Farm');
  await expect(rows.first()).toContainText('10,000');
  await expect(page.locator('.plan-total')).toContainText('Placed 10,000 chicks · 15,000 left over');
});

test('a wrong number is explained', async ({ page }) => {
  await loginAs(page, 'admin', '/grower-ranking');
  await plan(page, { chicks: '5000', rest: '500' });
  await expect(page.getByText(/Must be between 0 and 120/)).toBeVisible();
});

test('admin only, and it can be switched off in Settings', async ({ page, request }) => {
  await loginAs(page, 'sup_a', '/grower-ranking');
  await expect(page.getByRole('heading', { name: "Today's Dashboard" })).toBeVisible();
  expect((await api(request, 'sup_a', 'GET', '/reports/grower-ranking/')).status).toBe(403);

  expect((await api(request, 'admin', 'PATCH', '/settings/features/placement_planner/', { enabled: false })).status).toBe(200);
  await loginAs(page, 'admin', '/grower-ranking');
  await expect(page.getByRole('status')).toContainText('Who Gets the Next Chicks is turned off');
  await page.goto('/insights');
  await expect(page.getByRole('link', { name: /Who Gets the Next Chicks/ })).toHaveCount(0);
  await api(request, 'admin', 'PATCH', '/settings/features/placement_planner/', { enabled: true });
});
