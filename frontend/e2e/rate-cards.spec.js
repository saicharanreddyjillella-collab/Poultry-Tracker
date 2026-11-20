// Billing rate cards: admin adds the new card in Settings, then picks it when billing a flock.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, daysAgo, api } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

test('admin adds the Nov 2026 card with the standard growing-charge rule', async ({ page }) => {
  await loginAs(page, 'admin', '/settings');
  await page.getByRole('link', { name: 'Open billing rates →' }).click();
  await expect(page.getByRole('heading', { name: 'Billing Rates' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Rate cards' }).locator('tbody tr')).toHaveCount(1);
  await page.getByRole('button', { name: '+ New rate card' }).click();
  const f = page.getByRole('form', { name: 'Rate card' });
  await f.getByLabel('Card name *').fill('Jangaon Nov 2026');
  await f.getByLabel('Effective from').fill(daysAgo(400));
  await f.getByLabel('Growing charge method').selectOption('standard');
  const fields = {
    'Feed cost (₹ per kg)': '45.30', 'Chick cost (₹ per chick)': '34', 'Administration cost (₹ per chick)': '6',
    'Standard FCR': '1.60', 'Standard average body weight (kg)': '2', 'Standard mortality (%)': '5',
    'Standard production cost (₹/kg)': '95', 'Standard growing charge (₹/kg)': '8.50',
    'Minimum growing charge (₹/kg)': '5.50', 'Increase per ₹1 below standard (%)': '50',
    'Decrease per ₹1 above standard (%)': '50', 'Maximum rate incentive (₹/kg)': '2.50',
  };
  for (const [label, v] of Object.entries(fields)) await f.getByLabel(label, { exact: true }).fill(v);
  await f.getByLabel('Medicine at actual use for every farm').check();
  const check = f.getByLabel('Growing charge check');
  await expect(check).toContainText('cost ₹93 → ₹9.50');
  await expect(check).toContainText('cost ₹98 → ₹7.00');
  await expect(check).toContainText('cost ₹102 → ₹5.50');
  await f.getByRole('button', { name: 'Save card' }).click();
  await expect(page.getByRole('status')).toContainText('Saved Jangaon Nov 2026');
  const rows = page.getByRole('region', { name: 'Rate cards' }).locator('tbody tr');
  await expect(rows).toHaveCount(2);
  await expect(rows.filter({ hasText: 'Jangaon Nov 2026' })).toContainText('Standard ± %');
});

test('supervisors cannot open billing rates', async ({ page, request }) => {
  await loginAs(page, 'sup_a', '/settings/rate-cards');
  await expect(page.getByRole('heading', { name: 'Billing Rates' })).toHaveCount(0);
  expect((await api(request, 'sup_a', 'GET', '/rate-cards/')).status).toBe(403);
});

test('admin previews both cards when closing, then bills with the new one', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A3');
  await loginAs(page, 'admin', `/flocks/${flock}`);
  await page.getByRole('button', { name: 'Close & Generate Bill' }).click();
  const card = page.getByLabel('Rate card');
  await expect(card.locator('option:checked')).toHaveText(/Jangaon Nov 2026.*for this placement date/);
  const preview = page.getByLabel('Bill preview');
  await expect(preview).toContainText('Net payable');
  const newNet = await preview.locator('dd.strong').textContent();
  await card.selectOption({ label: (await card.locator('option').filter({ hasNotText: 'Jangaon' }).textContent()).trim() });
  await expect(preview.locator('dd.strong')).not.toHaveText(newNet);
  await card.selectOption({ index: 0 });
  await expect(preview.locator('dd.strong')).toHaveText(newNet);
  await page.getByRole('button', { name: 'Generate Bill', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/flocks/${flock}/bill$`));
  await expect(page.locator('tr', { hasText: 'Rate card' })).toContainText('Jangaon Nov 2026');
  await expect(page.locator('tr', { hasText: 'Rule' })).toContainText('₹8.50 ± 50% of');
  const bill = (await api(request, 'admin', 'GET', `/flocks/${flock}/bill/`)).body;
  expect(`₹${Number(bill.net_payable).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`).toBe(newNet.trim());
});
