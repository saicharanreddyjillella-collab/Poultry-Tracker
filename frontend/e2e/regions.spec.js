// Every supervisor can open and work on every farm (to cover for a colleague on leave);
// regions only set what their dashboard and reports show first. Entries record who made them.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, farmIdOf, field, daysAgo, api } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

test('every supervisor sees every farm on the Farms page', async ({ page }) => {
  for (const who of ['sup_a', 'sup_b']) {
    await loginAs(page, who, '/farms');
    await expect(page.getByRole('heading', { name: 'Farms (4)' })).toBeVisible();
    for (const f of ['Lakshmi Farm', 'Venkat Farm']) await expect(page.getByText(f).first()).toBeVisible();
  }
});

test('the dashboard opens on my regions; All farms shows the rest', async ({ page }) => {
  await loginAs(page, 'sup_a', '/feeds');
  const show = page.getByRole('group', { name: 'Show farms' });
  await expect(show.getByRole('button', { name: 'My regions' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('Lakshmi Farm').first()).toBeVisible();
  await expect(page.getByText('Venkat Farm')).toHaveCount(0);
  await show.getByRole('button', { name: 'All farms' }).click();
  await expect(page).toHaveURL(/scope=all/);
  await expect(page.getByText('Venkat Farm').first()).toBeVisible();
  // admins have no switch: they always see everything
  await loginAs(page, 'admin', '/feeds');
  await expect(page.getByRole('group', { name: 'Show farms' })).toHaveCount(0);
  await expect(page.getByText('Venkat Farm').first()).toBeVisible();
});

test('reports open on my regions, with All farms one click away', async ({ page }) => {
  await loginAs(page, 'sup_a', '/reports');
  await page.getByRole('button', { name: 'Region' }).click();
  await expect(page.locator('main')).toContainText('Zone-A');
  await expect(page.locator('main')).not.toContainText('Zone-B');
  await page.getByRole('group', { name: 'Show farms' }).getByRole('button', { name: 'All farms' }).click();
  await expect(page.locator('main')).toContainText('Zone-B');
});

test('a covering supervisor enters data on another region\'s farm, and it shows who', async ({ page, request }) => {
  const flockB = await flockIdOf(request, 'B1');
  await loginAs(page, 'sup_a', `/flocks/${flockB}`);            // Ravi covers Venkat Farm (Zone-B)
  await page.getByRole('button', { name: '+ Daily Entry' }).click();
  const f = page.locator('form.form-card');
  await field(f, 'Date *').fill(daysAgo(0));
  await field(f, 'Mortality').fill('2');
  await f.getByRole('button', { name: 'Save' }).click();
  const row = page.locator('tr', { hasText: daysAgo(0) });
  await expect(row.locator('td.cell-by')).toHaveText('Ravi');
  // Kiran, back from leave, corrects it
  await loginAs(page, 'sup_b', `/flocks/${flockB}?tab=entries`);
  await page.locator('tr', { hasText: daysAgo(0) }).getByRole('button', { name: 'Edit' }).click();
  await field(page.locator('form.form-card'), 'Mortality').fill('3');
  await page.locator('form.form-card').getByRole('button', { name: /Save|Update/ }).click();
  await expect(page.locator('tr', { hasText: daysAgo(0) }).locator('td.cell-by')).toHaveText('Raviedited by Kiran');
  // the dashboard's last-entry column says who
  await loginAs(page, 'admin', '/feeds');
  await expect(page.locator('tr', { hasText: 'Venkat Farm' })).toContainText('by Ravi');
});

test('farm details stay with the farm\'s own region', async ({ page, request }) => {
  await loginAs(page, 'sup_a', `/farms/${await farmIdOf(request, 'B1')}`);
  await expect(page.getByRole('button', { name: '+ New Flock' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Edit', exact: true })).toHaveCount(0);
  expect((await api(request, 'sup_a', 'PATCH', `/farms/${await farmIdOf(request, 'B1')}/`, { owner_name: 'x' })).status).toBe(403);
  await page.goto(`/farms/${await farmIdOf(request, 'A1')}`);
  await expect(page.getByRole('link', { name: 'Edit', exact: true })).toBeVisible();
});

test('feed: every supervisor sees and can order for every farm', async ({ page }) => {
  await loginAs(page, 'sup_a', '/feed');
  await expect(page.locator('table').last()).toContainText('Venkat Farm');
  await page.getByRole('button', { name: '+ Order Feed' }).click();
  const options = await page.locator('form select').first().locator('option').allTextContents();
  expect(options.join(' ')).toContain('Lakshmi');
  expect(options.join(' ')).toContain('Venkat');
});

test('a supervisor can open their own billed flock and its bill', async ({ page, request }) => {
  const flockA2 = await flockIdOf(request, 'A2', 'closed');
  await loginAs(page, 'sup_a', `/flocks/${flockA2}`);
  await page.getByRole('link', { name: 'View Bill' }).click();
  await expect(page.getByText('Ganga Farm', { exact: false }).first()).toBeVisible();
  await expect(page.getByText(/Net Payable to Farmer/)).toBeVisible();
});
