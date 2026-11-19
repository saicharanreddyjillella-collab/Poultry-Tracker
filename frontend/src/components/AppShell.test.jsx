import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi, test, expect } from 'vitest';

const { who } = vi.hoisted(() => ({ who: { current: null } }));
vi.mock('../context/AuthContext', () => ({ useAuth: () => who.current }));
vi.mock('./AlertBell', () => ({ default: () => <span>alerts</span> }));
import AppShell from './AppShell';

const groups = [
  { label: 'Operations', links: [{ to: '/feeds', label: 'Today', icon: 'today', end: true }, { to: '/farms', label: 'Farms', icon: 'farms' }] },
  { label: 'Admin', links: [] },
];
const show = (user, props = {}) => {
  who.current = { user, isAdmin: user.role === 'admin', logout: vi.fn() };
  return render(<MemoryRouter initialEntries={['/farms']}><AppShell brandName="Sai Ram Feeds" home="/feeds" groups={groups} showSearch {...props}><p>page</p></AppShell></MemoryRouter>);
};

test('groups with links show, empty groups are left out, the current page is marked', () => {
  show({ username: 'ravi', first_name: 'Ravi', role: 'supervisor' });
  const nav = screen.getByRole('navigation', { name: 'Main' });
  expect(nav).toHaveTextContent('Operations');
  expect(nav).not.toHaveTextContent('Admin');
  expect(screen.getByRole('link', { name: 'Farms' })).toHaveClass('active');
  expect(screen.getByRole('link', { name: 'Today' })).not.toHaveClass('active');
  expect(screen.getByText('SR')).toBeInTheDocument();            // initials logo
  expect(screen.getByText('page')).toBeInTheDocument();
});

test('user menu: settings only for the admin; logout always', async () => {
  show({ username: 'ravi', first_name: 'Ravi', role: 'supervisor' });
  await userEvent.click(screen.getByRole('button', { name: /Ravi/ }));
  expect(screen.queryByRole('link', { name: 'Settings' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument();
});

test('admin sees Settings in the user menu', async () => {
  show({ username: 'sai', first_name: 'Sai', role: 'admin' });
  await userEvent.click(screen.getByRole('button', { name: /Sai/ }));
  expect(screen.getByRole('link', { name: 'Settings' })).toBeInTheDocument();
});

test('search box only when asked for', () => {
  show({ username: 'mill', role: 'plant' }, { showSearch: false });
  expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Search farms')).not.toBeInTheDocument();
});
