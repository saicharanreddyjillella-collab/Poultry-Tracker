// Admin analysis (Insights: Feed Audit, Owner View, Break-even, Feed Forecast …): admin only (nav + direct URL).
import { render, screen } from '@testing-library/react';
import { vi, beforeEach } from 'vitest';
import App from './App';

const { me, EMPTY_AUDIT } = vi.hoisted(() => ({
  me: { current: null },
  EMPTY_AUDIT: { as_of: '2026-11-19', feed_cost_per_kg: '44.00', rows: [],
    summary: { flocks_checked: 0, flagged: 0, high: 0, counts_due: 0, value_at_risk: 0 } },
}));
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
    insightsAPI: Object.fromEntries(Object.keys(real.insightsAPI).map(k => [k, () => ok(EMPTY_AUDIT)])),
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

test.each(['/owner-dashboard', '/break-even', '/feed-forecast', '/insights', '/feed-audit', '/hatcheries', '/lift-planner'])('supervisor opening %s is sent to the dashboard', async (path) => {
  as('supervisor', path);
  await screen.findAllByRole('link', { name: 'Farms' });
  // their dashboard: /feeds on main, / on the Feeds-only release
  expect(['/feeds', '/']).toContain(window.location.pathname);
});

test('supervisor nav has no Insights or report links', async () => {
  as('supervisor', '/feeds');
  await screen.findAllByRole('link', { name: 'Reports' });
  for (const name of ['Insights', 'Owner View', 'Break-even', 'Feed Forecast', 'Feed Audit']) {
    expect(screen.queryByRole('link', { name })).not.toBeInTheDocument();
  }
});

test('admin reaches every analysis page from Insights', async () => {
  as('admin', '/feeds');
  expect(await screen.findByRole('link', { name: 'Insights' })).toBeInTheDocument();
  window.history.pushState({}, '', '/insights');
  window.dispatchEvent(new PopStateEvent('popstate'));
  for (const name of [/Feed Audit/, /Best Day to Lift/, /Heat Stress/, /Chick Quality/, /Owner View/, /Break-even/, /Feed Forecast/]) {
    expect(await screen.findByRole('link', { name })).toBeInTheDocument();
  }
});

test('admin opens the Feed Audit', async () => {
  as('admin', '/feed-audit');
  expect(await screen.findByRole('heading', { name: 'Feed Audit' })).toBeInTheDocument();
  expect(await screen.findByText('No feed problems found.')).toBeInTheDocument();
});
