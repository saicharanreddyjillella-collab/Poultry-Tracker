// E12 integration: a crash inside one page must not take down the app shell.
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import App from './App';

vi.mock('./pages/FarmsList', () => ({
  default: () => { throw new Error('FarmsList exploded'); },
}));
vi.mock('./utils/errorReporting', () => ({ reportClientError: vi.fn() }));
vi.mock('./api/client', async (importOriginal) => {
  const real = await importOriginal();
  const user = { id: 1, username: 'admin', role: 'admin', first_name: 'Admin', assigned_farm_ids: [] };
  const ok = (data) => Promise.resolve({ data });
  return {
    ...real,
    authAPI: { ...real.authAPI, me: () => ok(user) },
    alertAPI: real.alertAPI ? Object.fromEntries(Object.keys(real.alertAPI).map(k => [k, () => ok([])])) : undefined,
  };
});

test('a crashing page shows the recovery panel while the navbar stays usable', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
  localStorage.setItem('access_token', 't');
  localStorage.setItem('user', JSON.stringify({ id: 1, username: 'admin', role: 'admin' }));
  window.history.pushState({}, '', '/farms');

  render(<App />);

  expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong on this page');
  // shell still there: nav links work for getting away from the broken page
  expect(screen.getAllByRole('link', { name: /Farms/ }).length).toBeGreaterThan(0);
  const { reportClientError } = await import('./utils/errorReporting');
  expect(reportClientError).toHaveBeenCalled();
});
