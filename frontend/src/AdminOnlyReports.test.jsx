// Owner View, Break-even and Feed Forecast: admin only (nav + direct URL).
import { render, screen } from '@testing-library/react';
import { vi, beforeEach } from 'vitest';
import App from './App';

const { me } = vi.hoisted(() => ({ me: { current: null } }));
vi.mock('./utils/errorReporting', () => ({ reportClientError: vi.fn() }));
vi.mock('./api/client', async (orig) => {
  const real = await orig();
  const ok = (data) => Promise.resolve({ data });
  const stubAll = (obj) => Object.fromEntries(Object.keys(obj || {}).map(k => [k, () => ok([])]));
  return {
    ...real,
    authAPI: { ...real.authAPI, me: () => ok(me.current) },
    alertAPI: stubAll(real.alertAPI),
    dashboardAPI: stubAll(real.dashboardAPI),
    farmAPI: stubAll(real.farmAPI),
    reportAPI: Object.fromEntries(Object.keys(real.reportAPI).map(k => [k, () => ok({ flocks: [], overall: {}, weeks: [], sections: {} })])),
  };
});

const as = (role, path) => {
  me.current = { id: 1, username: role, role, first_name: role, assigned_farm_ids: [], must_change_password: false };
  localStorage.setItem('access_token', 't');
  localStorage.setItem('user', JSON.stringify(me.current));
  window.history.pushState({}, '', path);
  return render(<App />);
};

beforeEach(() => vi.spyOn(console, 'error').mockImplementation(() => {}));

test.each(['/owner-dashboard', '/break-even', '/feed-forecast'])('supervisor opening %s is sent to the dashboard', async (path) => {
  as('supervisor', path);
  await screen.findAllByRole('link', { name: 'Farms' });
  // their dashboard: /feeds on main, / on the Feeds-only release
  expect(['/feeds', '/']).toContain(window.location.pathname);
});

test('supervisor nav has no Owner View / Break-even / Feed Forecast', async () => {
  as('supervisor', '/feeds');
  await screen.findAllByRole('link', { name: 'Reports' });
  for (const name of ['Owner View', 'Break-even', 'Feed Forecast']) {
    expect(screen.queryByRole('link', { name })).not.toBeInTheDocument();
  }
});

test('admin sees all three', async () => {
  as('admin', '/feeds');
  for (const name of ['Owner View', 'Break-even', 'Feed Forecast']) {
    expect(await screen.findByRole('link', { name })).toBeInTheDocument();
  }
});
