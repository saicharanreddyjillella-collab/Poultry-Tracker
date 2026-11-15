import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, beforeEach } from 'vitest';
import ErrorBoundary from './ErrorBoundary';
import * as reporting from '../utils/errorReporting';

let shouldThrow = true;
function Bomb() {
  if (shouldThrow) throw new Error('kaboom in FlockDetail');
  return <p>page content</p>;
}

beforeEach(() => {
  shouldThrow = true;
  vi.spyOn(console, 'error').mockImplementation(() => {}); // React logs caught errors
});

test('renders children when nothing throws', () => {
  render(<ErrorBoundary><p>hello</p></ErrorBoundary>);
  expect(screen.getByText('hello')).toBeInTheDocument();
});

test('shows a recovery panel instead of a blank screen and reports the error', () => {
  const spy = vi.spyOn(reporting, 'reportClientError').mockReturnValue(true);
  render(<ErrorBoundary><Bomb /></ErrorBoundary>);
  expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong on this page');
  expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Go to dashboard' })).toHaveAttribute('href', '/');
  expect(spy).toHaveBeenCalledTimes(1);
  const [err, extra] = spy.mock.calls[0];
  expect(err.message).toBe('kaboom in FlockDetail');
  expect(extra.componentStack).toContain('Bomb');
});

test('"Try again" re-renders the page once the problem is gone', async () => {
  vi.spyOn(reporting, 'reportClientError').mockReturnValue(true);
  render(<ErrorBoundary><Bomb /></ErrorBoundary>);
  shouldThrow = false;
  await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(screen.getByText('page content')).toBeInTheDocument();
});

test('navigating to another route (resetKey change) clears the error', () => {
  vi.spyOn(reporting, 'reportClientError').mockReturnValue(true);
  const { rerender } = render(<ErrorBoundary resetKey="/flocks/1"><Bomb /></ErrorBoundary>);
  expect(screen.getByRole('alert')).toBeInTheDocument();
  shouldThrow = false;
  rerender(<ErrorBoundary resetKey="/farms"><Bomb /></ErrorBoundary>);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByText('page content')).toBeInTheDocument();
});

test('full-page variant offers reload only', () => {
  vi.spyOn(reporting, 'reportClientError').mockReturnValue(true);
  render(<ErrorBoundary fullPage><Bomb /></ErrorBoundary>);
  expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument();
});
