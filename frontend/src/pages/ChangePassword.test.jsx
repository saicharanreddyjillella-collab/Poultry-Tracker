import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, beforeEach } from 'vitest';

const { auth, authAPI } = vi.hoisted(() => ({
  auth: { user: null, updateUser: vi.fn() },
  authAPI: { changePassword: vi.fn() },
}));
vi.mock('../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../api/client', async (orig) => ({ ...(await orig()), authAPI }));
import ChangePassword from './ChangePassword';

const renderAt = () => render(
  <MemoryRouter initialEntries={['/change-password']}>
    <Routes>
      <Route path="/change-password" element={<ChangePassword />} />
      <Route path="/" element={<p>dashboard</p>} />
    </Routes>
  </MemoryRouter>,
);

beforeEach(() => {
  auth.updateUser.mockReset();
  authAPI.changePassword.mockReset();
});

const fillAndSubmit = async (current, next) => {
  const [cur, nw, conf] = document.querySelectorAll('input[type=password]');
  await userEvent.type(cur, current);
  await userEvent.type(nw, next);
  await userEvent.type(conf, next);
  await userEvent.click(screen.getByRole('button', { name: /Change Password/ }));
};

test('first login: welcome message, then straight to the app after setting a password', async () => {
  auth.user = { username: 'suresh', first_name: 'Suresh', role: 'supervisor', must_change_password: true };
  const fresh = { ...auth.user, must_change_password: false };
  authAPI.changePassword.mockResolvedValue({ data: { access: 'a', refresh: 'r', user: fresh } });
  renderAt();
  expect(screen.getByRole('heading')).toHaveTextContent('Set your password');
  expect(screen.getByRole('status')).toHaveTextContent('Welcome, Suresh');
  await fillAndSubmit('Kp7m-Qx4t-Rw9a', 'Suresh-own-2026');
  expect(auth.updateUser).toHaveBeenCalledWith(fresh);
  expect(await screen.findByText('dashboard')).toBeInTheDocument();
});

test('re-using the temporary password is refused before calling the server', async () => {
  auth.user = { username: 'suresh', must_change_password: true };
  renderAt();
  await fillAndSubmit('Kp7m-Qx4t-Rw9a', 'Kp7m-Qx4t-Rw9a');
  expect(screen.getByText(/different from the current/)).toBeInTheDocument();
  expect(authAPI.changePassword).not.toHaveBeenCalled();
});

test('normal password change stays on the page with a confirmation', async () => {
  auth.user = { username: 'admin', role: 'admin', must_change_password: false };
  authAPI.changePassword.mockResolvedValue({ data: { access: 'a', refresh: 'r', user: auth.user } });
  renderAt();
  expect(screen.getByRole('heading')).toHaveTextContent('Change Password');
  await fillAndSubmit('Old-pass-2026', 'New-pass-2026');
  expect(await screen.findByText(/signed out on other devices/)).toBeInTheDocument();
});
