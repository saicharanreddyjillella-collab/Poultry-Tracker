// What each role sees in the menu, and what happens if they open a URL they
// shouldn't (typing it, or an old bookmark).
import { test, expect } from '@playwright/test';
import { reseed, loginAs, navLinks, flockIdOf, farmIdOf } from './helpers';

test.beforeAll(() => reseed());

const ADMIN_ONLY = ['Feed Forecast', 'Owner View', 'Break-even', 'Users', 'Recycle Bin'];

test('admin menu has everything', async ({ page }) => {
  await loginAs(page, 'admin', '/farms');
  const links = await navLinks(page);
  for (const l of ['Today', 'Farms', 'Feed', 'Reports', ...ADMIN_ONLY]) expect(links).toContain(l);
});

test('supervisor menu: day-to-day screens only', async ({ page }) => {
  await loginAs(page, 'sup_a', '/farms');
  const links = await navLinks(page);
  for (const l of ['Today', 'Farms', 'Feed', 'Reports']) expect(links).toContain(l);
  for (const l of [...ADMIN_ONLY, 'Switch Business']) expect(links).not.toContain(l);
});

test('feed-mill menu: Feed only', async ({ page }) => {
  await loginAs(page, 'mill', '/feed');
  const links = await navLinks(page);
  expect(links).toContain('Feed');
  for (const l of ['Today', 'Farms', 'Reports', ...ADMIN_ONLY]) expect(links).not.toContain(l);
});

for (const path of ['/owner-dashboard', '/break-even', '/feed-forecast', '/trash']) {
  test(`supervisor opening ${path} is sent back to their dashboard`, async ({ page }) => {
    await loginAs(page, 'sup_a', path);
    await expect(page.getByRole('heading', { name: "Today's Dashboard" })).toBeVisible();
    expect(new URL(page.url()).pathname).not.toBe(path);
  });
}

test('supervisor opening User Management sees "Admin access required"', async ({ page }) => {
  await loginAs(page, 'sup_a', '/users');
  await expect(page.getByText('Admin access required.')).toBeVisible();
  await expect(page.getByRole('button', { name: '+ Add User' })).toHaveCount(0);
});

test('feed-mill user is kept on the Feed screens', async ({ page, request }) => {
  const flock = await flockIdOf(request, 'A1');
  const farm = await farmIdOf(request, 'A1');
  for (const path of ['/feeds', '/farms', `/farms/${farm}`, `/flocks/${flock}`, '/reports', '/users', '/']) {
    await loginAs(page, 'mill', path);
    await expect(page).toHaveURL(/\/feed$/);
    await expect(page.getByRole('heading', { name: 'Feed Stock & Orders' })).toBeVisible();
  }
});

test('admin-only pages open for admin', async ({ page }) => {
  for (const [path, heading] of [['/users', 'User Management'], ['/trash', 'Recycle Bin']]) {
    await loginAs(page, 'admin', path);
    await expect(page.getByRole('heading', { name: heading })).toBeVisible();
  }
  for (const path of ['/owner-dashboard', '/break-even', '/feed-forecast']) {
    await loginAs(page, 'admin', path);
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.locator('main h1').first()).toBeVisible();
  }
});
