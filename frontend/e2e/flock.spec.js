// A supervisor's daily work on a flock: entries, sales, medicines — and the
// checks that stop bad data.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, field, daysAgo, api } from './helpers';

test.beforeAll(() => reseed());

let flock;
test.beforeEach(async ({ page, request }) => {
  flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/flocks/${flock}`);
  await expect(page.getByRole('heading', { name: 'Lakshmi Farm — Flock' })).toBeVisible();
});

const entryForm = (page) => page.locator('form.form-card');

async function addEntry(page, { date, mortality = '0', bags = '', feedType, water = '', weight = '' }) {
  await page.getByRole('button', { name: '+ Daily Entry' }).click();
  const f = entryForm(page);
  await field(f, 'Date *').fill(date);
  await field(f, 'Mortality').fill(mortality);
  if (feedType) await field(f, 'Feed Type').selectOption(feedType);
  if (bags) await field(f, 'Bags').fill(bags);
  if (water) await field(f, 'Water (L)').fill(water);
  if (weight) await field(f, 'Body Weight (g)').fill(weight);
  await f.getByRole('button', { name: 'Save' }).click();
}

test('add a daily entry for today', async ({ page, request }) => {
  await addEntry(page, { date: daysAgo(0), mortality: '2', feedType: 'BFP', bags: '5', water: '900', weight: '850' });
  await expect(entryForm(page)).toHaveCount(0);
  const rows = (await api(request, 'admin', 'GET', `/daily-entries/?flock=${flock}`)).body;
  expect(rows.some(r => r.date === daysAgo(0) && r.mortality_count === 2)).toBe(true);
});

test('the same day twice is refused', async ({ page }) => {
  await addEntry(page, { date: daysAgo(18), mortality: '1' });    // seed has this day
  await expect(page.locator('.error-msg')).toContainText(/already exists/);
});

test('future dates and dates before placement are blocked by the date picker', async ({ page, request }) => {
  for (const date of [daysAgo(-2), daysAgo(40)]) {
    await addEntry(page, { date, mortality: '1' });
    const valid = await field(entryForm(page), 'Date *').evaluate(e => e.checkValidity());
    expect(valid, `${date} should be out of range`).toBe(false);
    await expect(entryForm(page)).toBeVisible();                       // not submitted
    await entryForm(page).getByRole('button', { name: 'Cancel' }).click();
  }
  const rows = (await api(request, 'admin', 'GET', `/daily-entries/?flock=${flock}`)).body;
  expect(rows.some(r => r.date === daysAgo(-2) || r.date === daysAgo(40))).toBe(false);
});

test('the server also refuses an out-of-range date sent directly', async ({ request }) => {
  const r = await api(request, 'sup_a', 'POST', '/daily-entries/', { flock, date: daysAgo(-2), mortality_count: 0 });
  expect(r.status).toBe(400);
});

test('negative values are refused before saving', async ({ page }) => {
  await addEntry(page, { date: daysAgo(10), water: '-5' });
  await expect(page.locator('.error-msg')).toHaveText('Water consumed cannot be negative.');
});

test('high mortality asks for confirmation — Cancel does not save', async ({ page, request }) => {
  page.once('dialog', d => { expect(d.message()).toContain('High mortality'); d.dismiss(); });
  await addEntry(page, { date: daysAgo(9), mortality: '200' });
  await expect(entryForm(page)).toBeVisible();                          // still open, nothing saved
  const rows = (await api(request, 'admin', 'GET', `/daily-entries/?flock=${flock}`)).body;
  expect(rows.some(r => r.date === daysAgo(9))).toBe(false);
});

test('high mortality confirmed with OK is saved', async ({ page, request }) => {
  page.once('dialog', d => d.accept());
  await addEntry(page, { date: daysAgo(8), mortality: '200' });
  await expect(entryForm(page)).toHaveCount(0);
  const rows = (await api(request, 'admin', 'GET', `/daily-entries/?flock=${flock}`)).body;
  expect(rows.find(r => r.date === daysAgo(8)).mortality_count).toBe(200);
});

test('more deaths than live birds is refused by the server', async ({ page }) => {
  page.on('dialog', d => d.accept());
  await addEntry(page, { date: daysAgo(7), mortality: '99999' });
  await expect(page.locator('.error-msg')).toContainText(/exceed|live birds|more than/i);
});

test('more feed than is in stock is refused', async ({ page }) => {
  page.on('dialog', d => d.accept());
  await addEntry(page, { date: daysAgo(6), feedType: 'BPSC', bags: '50' });   // no BPSC stock at A1
  await expect(page.locator('.error-msg')).toContainText(/stock|available/i);
});

test('edit an entry', async ({ page, request }) => {
  const before = (await api(request, 'admin', 'GET', `/daily-entries/?flock=${flock}`)).body
    .find(r => r.date === daysAgo(17));
  await page.locator('tr', { hasText: daysAgo(17) }).getByRole('button', { name: 'Edit' }).click();
  const f = entryForm(page);
  await field(f, 'Mortality').fill('7');
  await f.getByRole('button', { name: /Save|Update/ }).click();
  await expect(entryForm(page)).toHaveCount(0);
  const after = (await api(request, 'admin', 'GET', `/daily-entries/${before.id}/`)).body;
  expect(after.mortality_count).toBe(7);
});

test('delete an entry (with a Recycle Bin note)', async ({ page, request }) => {
  const row = page.locator('tr', { hasText: daysAgo(19) });
  await row.getByRole('button', { name: 'Delete' }).click();
  await expect(page.getByText(/An admin can restore it from the Recycle Bin/)).toBeVisible();
  await page.getByRole('button', { name: 'Yes, proceed' }).click();
  await expect(page.locator('tr', { hasText: daysAgo(19) })).toHaveCount(0);
  const rows = (await api(request, 'admin', 'GET', `/daily-entries/?flock=${flock}`)).body;
  expect(rows.some(r => r.date === daysAgo(19))).toBe(false);
});

test('record a sale', async ({ page, request }) => {
  await page.getByRole('button', { name: '+ Sale' }).click();
  const f = entryForm(page);
  await field(f, 'Date *').fill(daysAgo(0));
  await field(f, 'Trader / Buyer *').fill('Balaji Traders');
  await field(f, 'Birds *').fill('100');
  await field(f, 'Total Weight (kg) *').fill('210');
  await field(f, 'Rate (₹/kg)').fill('104');
  await f.getByRole('button', { name: 'Save Sale' }).click();
  await expect(entryForm(page)).toHaveCount(0);
  const sales = (await api(request, 'admin', 'GET', `/sales/?flock=${flock}`)).body;
  expect(sales.some(s => s.trader_name === 'Balaji Traders' && s.bird_count === 100)).toBe(true);
});

test('selling more birds than are alive is refused', async ({ page }) => {
  await page.getByRole('button', { name: '+ Sale' }).click();
  const f = entryForm(page);
  await field(f, 'Date *').fill(daysAgo(0));
  await field(f, 'Trader / Buyer *').fill('Too Many');
  await field(f, 'Birds *').fill('99999');
  await field(f, 'Total Weight (kg) *').fill('100');
  await f.getByRole('button', { name: 'Save Sale' }).click();
  await expect(page.locator('.error-msg')).toBeVisible();
});

test('record a medicine', async ({ page, request }) => {
  await page.getByRole('button', { name: '+ Medicine' }).click();
  const f = entryForm(page);
  await field(f, 'Date *').fill(daysAgo(1));
  await field(f, 'Medicine Name *').fill('ND Lasota');
  await field(f, 'Cost (₹)').fill('1500');
  await f.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('ND Lasota')).toBeVisible();
  const meds = (await api(request, 'admin', 'GET', `/medications/?flock=${flock}`)).body;
  expect(meds.some(m => m.name === 'ND Lasota')).toBe(true);
});

test('the excel export downloads', async ({ page }) => {
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export' }).click()]);
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
});
