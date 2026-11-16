// Feed orders through their life: supervisor orders → mill sends → supervisor
// receives; cancel; transfers; rates.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, field, api, daysAgo } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

const ordersTable = (page) => page.locator('table').last();

async function selectByText(select, text) {
  const label = (await select.locator('option').allTextContents()).find(t => t.includes(text));
  await select.selectOption({ label });
}

test('supervisor places an order for their farm', async ({ page, request }) => {
  await loginAs(page, 'sup_a', '/feed');
  await page.getByRole('button', { name: '+ Order Feed' }).click();
  const f = page.locator('form.form-card');
  await selectByText(field(f, 'Farm *'), 'Lakshmi');
  const flock = field(f, 'Flock *');
  await expect(flock.locator('option')).not.toHaveCount(1);
  await flock.selectOption({ index: 1 });
  await field(f, 'Feed Type *').selectOption('BSC');
  await field(f, 'Quantity (bags) *').fill('33');
  await f.getByRole('button', { name: 'Place Order' }).click();
  await expect(ordersTable(page)).toContainText('33');
  const orders = (await api(request, 'admin', 'GET', '/feed-orders/')).body;
  expect(orders.some(o => o.quantity_bags === 33 && o.status === 'pending')).toBe(true);
});

test('the mill sees it and marks it sent — no other order controls', async ({ page, request }) => {
  await loginAs(page, 'mill', '/feed');
  for (const b of ['+ Order Feed', 'Transfer Feed', 'Update Rate', 'Cancel'])
    await expect(page.getByRole('button', { name: b, exact: true })).toHaveCount(0);
  const row = ordersTable(page).locator('tr', { hasText: '33' });
  await row.getByRole('button', { name: 'Mark Sent' }).click();
  await expect(row).toContainText(/sent/i);
  const o = (await api(request, 'admin', 'GET', '/feed-orders/')).body.find(x => x.quantity_bags === 33);
  expect(o.status).toBe('sent');
});

test('a dispatched order can no longer be changed by the supervisor', async ({ request }) => {
  const o = (await api(request, 'admin', 'GET', '/feed-orders/')).body.find(x => x.quantity_bags === 33);
  const r = await api(request, 'sup_a', 'PATCH', `/feed-orders/${o.id}/`, { quantity_bags: 99 });
  expect(r.status).toBe(403);
});

test('supervisor receives it and farm stock goes up', async ({ page, request }) => {
  const before = (await api(request, 'admin', 'GET', '/feed-stock/')).body.find(s => s.farm_name?.includes('Lakshmi') || s.farm_code === 'A1');
  await loginAs(page, 'sup_a', '/feed');
  const row = ordersTable(page).locator('tr', { hasText: '33' });
  await row.getByRole('button', { name: 'Confirm Delivery' }).click();
  const confirm = page.getByRole('button', { name: /Confirm|Yes/ });
  if (await confirm.count()) await confirm.first().click();
  await expect(row).toContainText(/delivered/i);
  const after = (await api(request, 'admin', 'GET', '/feed-stock/')).body.find(s => s.farm_name?.includes('Lakshmi') || s.farm_code === 'A1');
  expect(JSON.stringify(after)).not.toBe(JSON.stringify(before));
});

test('supervisor cancels a pending order', async ({ page, request }) => {
  await loginAs(page, 'sup_a', '/feed');
  const row = ordersTable(page).locator('tr', { hasText: '40' });       // seed's pending A1 order
  await row.getByRole('button', { name: 'Cancel' }).click();
  const confirm = page.getByRole('button', { name: /Yes, proceed|Confirm/ });
  if (await confirm.count()) await confirm.first().click();
  await expect(row).toContainText(/cancel/i);
  const o = (await api(request, 'admin', 'GET', '/feed-orders/')).body.find(x => x.quantity_bags === 40);
  expect(o.status).toBe('cancelled');
});

test('supervisor transfers feed between their own farms', async ({ page, request }) => {
  await loginAs(page, 'sup_a', '/feed');
  await page.getByRole('button', { name: 'Transfer Feed' }).click();
  const f = page.locator('form.form-card');
  await selectByText(field(f, 'From Farm *'), 'Lakshmi');
  await selectByText(field(f, 'To Farm *'), 'Krishna');
  await field(f, 'Feed Type *').selectOption('BFP');
  await field(f, 'Bags *').fill('4');
  await field(f, 'Date *').fill(daysAgo(0));
  await f.getByRole('button', { name: 'Transfer' }).click();
  await expect(page.locator('form.form-card')).toHaveCount(0);
  const t = (await api(request, 'admin', 'GET', '/feed-transfers/')).body;
  expect(t.some(x => x.quantity_bags === 4)).toBe(true);
});

test('admin updates a feed rate', async ({ page, request }) => {
  await loginAs(page, 'admin', '/feed');
  await page.getByRole('button', { name: 'Update Rate' }).click();
  const f = page.locator('form.form-card');
  await field(f, 'Week Start Date *').fill(daysAgo(0));
  await field(f, 'Feed Type *').selectOption('BSC');
  await field(f, 'Rate per kg (₹) *').fill('47.50');
  await f.getByRole('button', { name: 'Save Rate' }).click();
  await expect(page.getByText(/47\.5/).first()).toBeVisible();
  const rates = (await api(request, 'admin', 'GET', '/feed-rates/')).body;
  expect(rates.some(r => Number(r.rate_per_kg) === 47.5)).toBe(true);
});

test('supervisors cannot change rates', async ({ page }) => {
  await loginAs(page, 'sup_a', '/feed');
  await expect(page.getByRole('button', { name: 'Update Rate' })).toHaveCount(0);
});
