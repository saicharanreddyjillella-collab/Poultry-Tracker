// Closing a flock, the generated bill, the lock, and an admin reopen.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, api } from './helpers';

test.describe.configure({ mode: 'serial' });     // one story, in order
test.beforeAll(() => reseed());

let flockA3;

test('supervisor closes a sold-out flock and gets the bill', async ({ page, request }) => {
  flockA3 = await flockIdOf(request, 'A3');
  await loginAs(page, 'sup_a', `/flocks/${flockA3}`);
  await page.getByRole('button', { name: 'Close & Generate Bill' }).click();
  await expect(page.getByRole('heading', { name: 'Close Flock & Generate Bill' })).toBeVisible();
  await page.getByRole('button', { name: 'Generate Bill', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/flocks/${flockA3}/bill$`));
  await expect(page.getByText(/Net Payable to Farmer/)).toBeVisible();
  await expect(page.getByText(/Locked/)).toBeVisible();
  // supervisors can't reopen
  await expect(page.getByRole('button', { name: 'Reopen Bill' })).toHaveCount(0);
});

test('the billed flock is read-only on screen', async ({ page }) => {
  await loginAs(page, 'sup_a', `/flocks/${flockA3}`);
  await expect(page.getByRole('link', { name: 'View Bill' })).toBeVisible();
  for (const b of ['+ Daily Entry', '+ Sale', '+ Medicine', 'Close & Generate Bill', 'Delete'])
    await expect(page.getByRole('button', { name: b, exact: true })).toHaveCount(0);
});

test('and locked on the server (no edits through the API either)', async ({ request }) => {
  const sales = (await api(request, 'sup_a', 'GET', `/sales/?flock=${flockA3}`)).body;
  const r = await api(request, 'sup_a', 'PATCH', `/sales/${sales[0].id}/`, { rate_per_kg: '1' });
  expect(r.status).toBe(409);
});

test('admin reopen needs a real reason', async ({ page }) => {
  await loginAs(page, 'admin', `/flocks/${flockA3}/bill`);
  await page.getByRole('button', { name: 'Reopen Bill' }).click();
  const confirm = page.getByRole('button', { name: 'Confirm Reopen' });
  await expect(confirm).toBeDisabled();
  await page.locator('textarea').fill('too short');
  await expect(confirm).toBeDisabled();
  await page.locator('textarea').fill('Weighbridge slip corrected — 40 kg was missed');
  await expect(confirm).toBeEnabled();
  await confirm.click();
  await expect(page).toHaveURL(new RegExp(`/flocks/${flockA3}$`));
  await expect(page.getByRole('button', { name: 'Close & Generate Bill' })).toBeVisible();   // active again
});

test('after correcting, closing again makes revision 2 with history', async ({ page }) => {
  await loginAs(page, 'sup_a', `/flocks/${flockA3}`);
  await page.getByRole('button', { name: 'Close & Generate Bill' }).click();
  await page.getByRole('button', { name: 'Generate Bill', exact: true }).click();
  await expect(page.getByText(/Revision 2/).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Bill history' })).toBeVisible();
  await expect(page.getByText('Weighbridge slip corrected — 40 kg was missed')).toBeVisible();
});

test('print view is available', async ({ page }) => {
  await loginAs(page, 'admin', `/flocks/${flockA3}/bill`);
  await expect(page.getByRole('button', { name: 'Print Bill' })).toBeVisible();
});
