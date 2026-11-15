import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, beforeEach } from 'vitest';

const { auth, trashAPI } = vi.hoisted(() => ({
  auth: { isAdmin: true },
  trashAPI: { list: vi.fn(), restore: vi.fn() },
}));
vi.mock('../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../api/client', async (orig) => ({ ...(await orig()), trashAPI }));

import RecycleBin from './RecycleBin';

const ROWS = [
  { batch: 'b-flock', kind: 'Flock', summary: 'Flock: Lakshmi Farm - 2026-10-04',
    also_removed: { 'Daily entry': 4, Sale: 1 }, items_total: 6, deleted_at: '2026-11-15T09:00:00Z', deleted_by: 'admin' },
  { batch: 'b-entry', kind: 'DailyEntry', summary: 'Daily entry: 2026-10-05',
    also_removed: {}, items_total: 1, deleted_at: '2026-11-14T09:00:00Z', deleted_by: 'sup' },
];

const renderPage = () => render(
  <MemoryRouter initialEntries={['/trash']}>
    <Routes>
      <Route path="/trash" element={<RecycleBin />} />
      <Route path="/" element={<p>home</p>} />
    </Routes>
  </MemoryRouter>,
);

beforeEach(() => {
  auth.isAdmin = true;
  trashAPI.list.mockReset().mockResolvedValue({ data: ROWS });
  trashAPI.restore.mockReset();
});

test('lists one row per delete action with what went with it', async () => {
  renderPage();
  const row = (await screen.findByText('Flock: Lakshmi Farm - 2026-10-04')).closest('tr');
  expect(within(row).getByText('4 daily entries, 1 sale')).toBeInTheDocument();
  expect(within(row).getByText('admin')).toBeInTheDocument();
  expect(screen.getByText('Daily entry: 2026-10-05').closest('tr')).toHaveTextContent('—');
});

test('restore asks for confirmation, calls the API and refreshes the list', async () => {
  trashAPI.restore.mockResolvedValue({ data: { restored: 6 } });
  renderPage();
  const row = (await screen.findByText('Flock: Lakshmi Farm - 2026-10-04')).closest('tr');
  await userEvent.click(within(row).getByRole('button', { name: 'Restore' }));
  expect(screen.getByText(/and 5 related record/)).toBeInTheDocument();
  trashAPI.list.mockResolvedValue({ data: [ROWS[1]] });
  await userEvent.click(screen.getAllByRole('button', { name: 'Restore' }).at(-1));
  expect(trashAPI.restore).toHaveBeenCalledWith('b-flock');
  expect(await screen.findByText(/Restored Flock: Lakshmi Farm/)).toBeInTheDocument();
  expect(screen.queryByText('Flock: Lakshmi Farm - 2026-10-04')).not.toBeInTheDocument();
});

test('a refused restore shows the server reason', async () => {
  trashAPI.restore.mockRejectedValue({ response: { data: { error: 'Restore that first.' } } });
  renderPage();
  const row = (await screen.findByText('Daily entry: 2026-10-05')).closest('tr');
  await userEvent.click(within(row).getByRole('button', { name: 'Restore' }));
  await userEvent.click(screen.getAllByRole('button', { name: 'Restore' }).at(-1));
  expect(await screen.findByRole('alert')).toHaveTextContent('Restore that first.');
});

test('empty bin', async () => {
  trashAPI.list.mockResolvedValue({ data: [] });
  renderPage();
  expect(await screen.findByText('Nothing has been deleted.')).toBeInTheDocument();
});

test('non-admins are sent away', () => {
  auth.isAdmin = false;
  renderPage();
  expect(screen.getByText('home')).toBeInTheDocument();
  expect(trashAPI.list).not.toHaveBeenCalled();
});
