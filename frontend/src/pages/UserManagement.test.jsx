import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, beforeEach } from 'vitest';

const { authAPI, farmAPI } = vi.hoisted(() => ({
  authAPI: { listUsers: vi.fn(), listRegions: vi.fn(), createUser: vi.fn(), updateUser: vi.fn(), deleteUser: vi.fn() },
  farmAPI: { list: vi.fn() },
}));
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ isAdmin: true }) }));
vi.mock('../api/client', async (orig) => ({ ...(await orig()), authAPI, farmAPI }));

import UserManagement from './UserManagement';

const USERS = [
  { id: 1, username: 'admin', role: 'admin', first_name: 'Sai', last_name: '', assigned_regions: [], must_change_password: false },
  { id: 2, username: 'suresh', role: 'supervisor', first_name: 'Suresh', last_name: '', assigned_regions: ['Zone-A'], must_change_password: true },
];

beforeEach(() => {
  Object.values(authAPI).forEach(f => f.mockReset());
  authAPI.listUsers.mockResolvedValue({ data: USERS });
  authAPI.listRegions.mockResolvedValue({ data: ['Zone-A'] });
  farmAPI.list.mockResolvedValue({ data: [] });
});

const openForm = async () => {
  render(<UserManagement />);
  await userEvent.click(await screen.findByRole('button', { name: '+ Add User' }));
  const form = document.querySelector('form.form-card');
  const [username, password] = form.querySelectorAll('input');
  return { form, username, password };
};

test('the browser is told not to autofill the admin\'s own login into the new-user form', async () => {
  const { form, username, password } = await openForm();
  expect(form).toHaveAttribute('autocomplete', 'off');
  expect(username).toHaveAttribute('autocomplete', 'off');
  expect(password).toHaveAttribute('autocomplete', 'new-password');
});

test('Generate fills a strong password and shows it; Show/Hide toggles', async () => {
  const { password } = await openForm();
  expect(password).toHaveAttribute('type', 'password');
  await userEvent.click(screen.getByRole('button', { name: 'Generate' }));
  expect(password.value).toMatch(/^[A-Za-z2-9]{4}-[A-Za-z2-9]{4}-[A-Za-z2-9]{4}$/);
  expect(password).toHaveAttribute('type', 'text');
  await userEvent.click(screen.getByRole('button', { name: 'Hide password' }));
  expect(password).toHaveAttribute('type', 'password');
});

test('creating a user shows the login details to hand over', async () => {
  authAPI.createUser.mockResolvedValue({ data: { id: 3 } });
  const { username, password } = await openForm();
  await userEvent.type(username, 'ravi');
  await userEvent.type(password, 'Ravi-temp-2026');
  await userEvent.click(screen.getByRole('button', { name: 'Create User' }));
  expect(authAPI.createUser).toHaveBeenCalledWith(expect.objectContaining({ username: 'ravi', password: 'Ravi-temp-2026' }));
  const card = await screen.findByRole('status');
  expect(card).toHaveTextContent('User ravi created');
  expect(within(card).getByTestId('shared-password')).toHaveTextContent('Ravi-temp-2026');
  expect(card).toHaveTextContent(/choose\s+their own/);
});

test('missing password gives a clear message, nothing is sent', async () => {
  const { username } = await openForm();
  await userEvent.type(username, 'ravi');
  await userEvent.click(screen.getByRole('button', { name: 'Create User' }));
  expect(screen.getByText(/needs it to log in/)).toBeInTheDocument();
  expect(authAPI.createUser).not.toHaveBeenCalled();
});

test('server password-policy errors are shown', async () => {
  authAPI.createUser.mockRejectedValue({ response: { data: { error: 'This password is too short.' } } });
  const { username, password } = await openForm();
  await userEvent.type(username, 'ravi');
  await userEvent.type(password, 'abc');
  await userEvent.click(screen.getByRole('button', { name: 'Create User' }));
  expect(await screen.findByText('This password is too short.')).toBeInTheDocument();
});

test('Reset password gives a supervisor a new temporary password and shows it', async () => {
  authAPI.updateUser.mockResolvedValue({ data: {} });
  render(<UserManagement />);
  const row = (await screen.findByText('suresh')).closest('tr');
  expect(row).toHaveTextContent('temporary password');
  await userEvent.click(within(row).getByRole('button', { name: 'Reset password' }));
  await userEvent.click(screen.getAllByRole('button', { name: 'Reset password' }).at(-1)); // confirm
  const [id, body] = authAPI.updateUser.mock.calls[0];
  expect(id).toBe(2);
  expect(body.password).toMatch(/^.{4}-.{4}-.{4}$/);
  const card = await screen.findByRole('status');
  expect(card).toHaveTextContent('New password for suresh');
  expect(within(card).getByTestId('shared-password')).toHaveTextContent(body.password);
});

test('no Reset password button for admins', async () => {
  render(<UserManagement />);
  await screen.findByText('suresh');
  const row = screen.getAllByRole('row').find(r => within(r).queryByText('admin', { selector: 'strong' }));
  expect(within(row).queryByRole('button', { name: 'Reset password' })).not.toBeInTheDocument();
});
