// Supervisors mostly use phones in the field.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, field, daysAgo } from './helpers';

test.beforeAll(() => reseed());

test('menu opens from the hamburger and navigates', async ({ page }) => {
  await loginAs(page, 'sup_a', '/feeds');
  await page.locator('.nav-hamburger, .hamburger, button[aria-label*="menu" i]').first().click();
  await page.locator('nav').getByRole('link', { name: 'Farms', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Farms (3)' })).toBeVisible();
});

test('daily entry can be added on a phone', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/flocks/${flock}`);
  await page.getByRole('button', { name: '+ Daily Entry' }).click();
  const f = page.locator('form.form-card');
  await field(f, 'Date *').fill(daysAgo(0));
  await field(f, 'Mortality').fill('1');
  await f.getByRole('button', { name: 'Save' }).click();
  await expect(f).toHaveCount(0);
});

test('no sideways scrolling on key screens', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  for (const path of ['/feeds', '/farms', `/flocks/${flock}`, '/feed']) {
    await loginAs(page, 'sup_a', path);
    await page.waitForLoadState('networkidle');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${path} scrolls sideways by ${overflow}px`).toBeLessThanOrEqual(1);
  }
});
