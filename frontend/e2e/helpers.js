import { expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const API = 'http://127.0.0.1:8000/api';
export const PASSWORD = 'E2e-pass-2026!';
export const NEWBIE_PASSWORD = 'Temp-pass-2026';
const BACKEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../backend');

/** Put the database back to the seed state (call in beforeAll of each file). */
export function reseed() {
  execFileSync(process.env.E2E_PYTHON || 'python', ['manage.py', 'seed_e2e'], {
    cwd: BACKEND,
    env: { ...process.env, DEBUG: 'True', SECRET_KEY: 'e2e-only-not-a-secret', E2E_SEED: '1',
           SQLITE_PATH: process.env.E2E_SQLITE_PATH },
    stdio: 'pipe',
  });
}

export async function apiLogin(request, username, password = PASSWORD) {
  const r = await request.post(`${API}/auth/login/`, { data: { username, password } });
  expect(r.ok(), `login ${username}`).toBeTruthy();
  return r.json();
}

/** Sign in without the form (fast) and open `to`. */
export async function loginAs(page, username, to = '/feeds', password = PASSWORD) {
  const data = await apiLogin(page.request, username, password);
  await page.goto('/login');
  await page.evaluate((d) => {
    localStorage.setItem('access_token', d.access);
    localStorage.setItem('refresh_token', d.refresh);
    localStorage.setItem('user', JSON.stringify(d.user));
  }, data);
  await page.goto(to);
  return data;
}

/** Sign in through the real login form. */
export async function uiLogin(page, username, password = PASSWORD) {
  await page.goto('/login');
  await page.getByPlaceholder('Enter username').fill(username);
  await page.getByPlaceholder('Enter password').fill(password);
  await page.getByRole('button', { name: 'Sign In' }).click();
}

/** Authenticated API call (for looking up ids / checking results). */
export async function api(request, username, method, url, data) {
  const { access } = await apiLogin(request, username);
  const r = await request.fetch(`${API}${url}`, { method, data, headers: { Authorization: `Bearer ${access}` } });
  return { status: r.status(), body: r.status() !== 204 ? await r.json().catch(() => null) : null };
}

export async function flockIdOf(request, farmCode, status = 'active') {
  const farms = (await api(request, 'admin', 'GET', '/farms/')).body;
  const farm = farms.find(f => f.farm_code === farmCode);
  const flocks = (await api(request, 'admin', 'GET', `/flocks/?farm=${farm.id}&status=${status}`)).body;
  return flocks[0].id;
}

export async function farmIdOf(request, farmCode) {
  const farms = (await api(request, 'admin', 'GET', '/farms/')).body;
  return farms.find(f => f.farm_code === farmCode).id;
}

/** Input/select/textarea inside the .form-group whose label is exactly `label`. */
export function field(scope, label) {
  const esc = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const page = typeof scope.page === 'function' ? scope.page() : scope;   // `has` must be page-relative
  return scope.locator('.form-group')
    .filter({ has: page.locator('label', { hasText: new RegExp(`^\\s*${esc}\\s*$`) }) })
    .locator('input, select, textarea').first();
}

export const navLinks = async (page) =>
  (await page.locator('nav .nav-links > a').allInnerTexts()).map(t => t.trim()).filter(Boolean);

// Dates are India dates (the server runs on Asia/Kolkata), whatever zone the test machine is in.
const IST = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' });
export const istToday = () => IST.format(new Date());
export const daysAgo = (n) => {
  const [y, m, d] = istToday().split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d - n)).toISOString().slice(0, 10);
};
