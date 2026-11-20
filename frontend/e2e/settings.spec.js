// Settings → Features: the admin switches Feed Audit and Best Day to Lift off and on.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, api, istToday } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

const sw = (page, name) => page.getByRole('switch', { name });
const KEYS = { 'Feed Audit (bag counts)': 'feed_audit', 'Best Day to Lift': 'lift_planner' };
const flip = (page, name) => page.locator(`.feature-row[data-feature="${KEYS[name]}"] .switch-slider`).click();

test('admin finds Settings in the user menu; both features start on', async ({ page }) => {
  await loginAs(page, 'admin', '/feeds');
  await page.locator('.nav-user-trigger').first().hover();
  await page.locator('.nav-dropdown').getByRole('link', { name: 'Settings' }).first().click();
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  await expect(sw(page, 'Feed Audit (bag counts)')).toBeChecked();
  await expect(sw(page, 'Best Day to Lift')).toBeChecked();
});

test('Feed Audit off: card, page and bag counts disappear for everyone; data comes back when on', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  await api(request, 'sup_a', 'POST', '/feed-counts/', { flock, date: istToday(), bags: { BFP: 180 } });

  await loginAs(page, 'admin', '/settings');
  await flip(page, 'Feed Audit (bag counts)');
  await expect(sw(page, 'Feed Audit (bag counts)')).not.toBeChecked();
  await expect(page.getByText(/Last changed by Sai/)).toBeVisible();

  await page.goto('/insights');
  await expect(page.getByRole('link', { name: /Best Day to Lift/ })).toBeVisible();
  await expect(page.getByRole('link', { name: /Feed Audit/ })).toHaveCount(0);
  await page.goto('/feed-audit');
  await expect(page.getByRole('status')).toContainText('Feed Audit is turned off');

  await loginAs(page, 'sup_a', `/flocks/${flock}?tab=feed`);
  await expect(page.getByRole('heading', { name: 'Lakshmi Farm — Flock' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Feed Bag Counts' })).toHaveCount(0);
  expect((await api(request, 'sup_a', 'GET', `/feed-counts/?flock=${flock}`)).status).toBe(403);

  await loginAs(page, 'admin', '/settings');
  await flip(page, 'Feed Audit (bag counts)');
  await expect(sw(page, 'Feed Audit (bag counts)')).toBeChecked();
  await page.goto(`/flocks/${flock}?tab=feed`);
  await expect(page.locator('.bag-counts table')).toContainText('180');           // saved count kept
});

test('Best Day to Lift off and on', async ({ page }) => {
  await loginAs(page, 'admin', '/settings');
  await flip(page, 'Best Day to Lift');
  await expect(sw(page, 'Best Day to Lift')).not.toBeChecked();
  await page.goto('/lift-planner');
  await expect(page.getByRole('status')).toContainText('Best Day to Lift is turned off');
  await page.getByRole('link', { name: 'Settings → Features' }).click();
  await flip(page, 'Best Day to Lift');
  await expect(sw(page, 'Best Day to Lift')).toBeChecked();
  await page.goto('/lift-planner');
  await expect(page.getByRole('heading', { name: 'Best Day to Lift' })).toBeVisible();
  await expect(page.getByText('is turned off')).toHaveCount(0);
});

test('supervisors have no Settings', async ({ page, request }) => {
  await loginAs(page, 'sup_a', '/settings');
  await expect(page.getByRole('heading', { name: "Today's Dashboard" })).toBeVisible();
  expect((await api(request, 'sup_a', 'PATCH', '/settings/features/feed_audit/', { enabled: false })).status).toBe(403);
});
