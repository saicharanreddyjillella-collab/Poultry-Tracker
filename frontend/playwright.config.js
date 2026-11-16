// Browser (end-to-end) tests: the real React build against the real Django API
// on a throwaway SQLite database seeded by `manage.py seed_e2e`.
//
//   npm run e2e                 (needs the backend's Python deps installed)
//   E2E_PYTHON=../backend/venv/bin/python npm run e2e
import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
import os from 'node:os';

const PY = process.env.E2E_PYTHON || 'python';
export const API = 'http://127.0.0.1:8000';
export const BACKEND_ENV = {
  DEBUG: 'True',
  SECRET_KEY: 'e2e-only-not-a-secret',
  SQLITE_PATH: process.env.E2E_SQLITE_PATH || path.join(os.tmpdir(), 'poultrytrack-e2e.sqlite3'),
  E2E_SEED: '1',
  // Tests log in a lot; production keeps its defaults.
  THROTTLE_LOGIN_RATE: '5000/min',
  THROTTLE_ANON_RATE: '10000/min',
  THROTTLE_USER_RATE: '10000/min',
  LOG_LEVEL: 'WARNING',            // keep request logs out of the test output
};
process.env.E2E_SQLITE_PATH = BACKEND_ENV.SQLITE_PATH;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,                 // one shared database
  retries: 0,                 // tests change data — a blind retry would hide real failures
  timeout: 45_000,
  expect: { timeout: 8_000 },
  reporter: process.env.CI ? [['list'], ['github'], ['html', { open: 'never' }]] : [['list']],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] }, testIgnore: /mobile\.spec/ },
    { name: 'phone', use: { ...devices['Pixel 7'] }, testMatch: /mobile\.spec/ },
  ],
  webServer: [
    {
      command: `${PY} manage.py migrate --noinput -v0 && ${PY} manage.py seed_e2e && ${PY} manage.py runserver 127.0.0.1:8000 --noreload`,
      cwd: '../backend',
      url: `${API}/api/health/`,
      env: { ...process.env, ...BACKEND_ENV },
      timeout: 180_000,
      reuseExistingServer: false,
    },
    {
      command: 'npx vite build --logLevel error --outDir dist-e2e && npx vite preview --outDir dist-e2e --port 4173 --strictPort --host 127.0.0.1',
      url: 'http://127.0.0.1:4173',
      env: { ...process.env, VITE_API_URL: `${API}/api` },
      timeout: 180_000,
      reuseExistingServer: false,
    },
  ],
});
