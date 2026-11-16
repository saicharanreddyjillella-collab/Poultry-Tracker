// Every report screen renders for the people allowed to see it.
import { test, expect } from '@playwright/test';
import { reseed, loginAs } from './helpers';

test.beforeAll(() => reseed());

for (const user of ['admin', 'sup_a']) {
  test(`${user}: monthly, till-date and region reports render`, async ({ page }) => {
    await loginAs(page, user, '/reports');
    await expect(page.getByRole('heading', { name: 'Reports' })).toBeVisible();
    for (const tab of ['Monthly', 'Till Date', 'Region']) {
      await page.getByRole('button', { name: tab, exact: true }).click();
      await expect(page.locator('.error-msg')).toHaveCount(0);
    }
  });

  test(`${user}: monthly Excel export downloads`, async ({ page }) => {
    await loginAs(page, user, '/reports');
    const [d] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export Excel' }).click()]);
    expect(d.suggestedFilename()).toMatch(/\.xlsx$/);
  });
}

for (const [path, text] of [['/owner-dashboard', /Owner|Overview/i], ['/break-even', /Break-even/i], ['/feed-forecast', /Forecast/i]]) {
  test(`admin: ${path} renders with data`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await loginAs(page, 'admin', path);
    await expect(page.locator('main h1').first()).toHaveText(text);
    await expect(page.locator('.error-msg')).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test('dashboard shows farms and feed for today without errors', async ({ page }) => {
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await loginAs(page, 'sup_a', '/feeds');
  await expect(page.getByRole('heading', { name: "Today's Dashboard" })).toBeVisible();
  await expect(page.getByText('Lakshmi Farm').first()).toBeVisible();
  expect(errors).toEqual([]);
});
