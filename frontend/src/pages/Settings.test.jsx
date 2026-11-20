import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi, test, expect, beforeEach } from 'vitest';

const { rows, setCalls, states } = vi.hoisted(() => ({ rows: { current: [] }, setCalls: [], states: { current: {} } }));
vi.mock('../api/client', () => ({
  getErrorMessage: () => 'failed',
  rulesAPI: {
    list: () => Promise.resolve({ data: [{ key: 'edit_window_days', name: 'Edit window (days)', description: 'd', type: 'int', min: 0, max: 365, value: 3 }] }),
    save: (v) => Promise.resolve({ data: [{ key: 'edit_window_days', name: 'Edit window (days)', description: 'd', type: 'int', min: 0, max: 365, value: Number(v.edit_window_days) }] }),
  },
  featureAPI: {
    list: () => Promise.resolve({ data: rows.current }),
    states: () => Promise.resolve({ data: states.current }),
    set: (key, enabled) => {
      setCalls.push([key, enabled]);
      const row = rows.current.find(r => r.key === key);
      return Promise.resolve({ data: { ...row, enabled, updated_by: 'Sai', updated_at: '2026-11-19T08:00:00Z' } });
    },
  },
}));
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ isAdmin: true }) }));

import Settings from './Settings';
import BagCountSection from '../components/BagCountSection';
import { refreshFeatures } from '../utils/features';

beforeEach(() => {
  setCalls.length = 0;
  rows.current = [
    { key: 'feed_audit', name: 'Feed Audit (bag counts)', description: 'd1', when_off: 'Bag counts hidden.', enabled: true },
    { key: 'lift_planner', name: 'Best Day to Lift', description: 'd2', when_off: 'Page hidden.', enabled: true },
  ];
});

test('lists every feature with what turning it off does', async () => {
  render(<MemoryRouter><Settings /></MemoryRouter>);
  expect(await screen.findByRole('switch', { name: 'Feed Audit (bag counts)' })).toBeChecked();
  expect(screen.getByRole('switch', { name: 'Best Day to Lift' })).toBeChecked();
  expect(screen.getByText('Bag counts hidden.')).toBeInTheDocument();
});

test('turning a feature off saves it and shows who changed it', async () => {
  render(<MemoryRouter><Settings /></MemoryRouter>);
  const sw = await screen.findByRole('switch', { name: 'Best Day to Lift' });
  await userEvent.click(sw);
  await waitFor(() => expect(sw).not.toBeChecked());
  expect(setCalls).toEqual([['lift_planner', false]]);
  expect(screen.getByText(/Last changed by Sai/)).toBeInTheDocument();
});

test('bag counts disappear from the flock page when Feed Audit is off', async () => {
  states.current = { feed_audit: false, lift_planner: true };
  await refreshFeatures();
  const { container } = render(<MemoryRouter><BagCountSection flock={{ id: 1, status: 'active' }} canEdit isAdmin /></MemoryRouter>);
  expect(container).toBeEmptyDOMElement();
});
