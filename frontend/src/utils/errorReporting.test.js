import { vi, beforeEach } from 'vitest';
import { buildReport, reportClientError, _resetReporting } from './errorReporting';

let fetchMock;
beforeEach(() => {
  _resetReporting();
  fetchMock = vi.fn(() => Promise.resolve({ ok: true }));
  vi.stubGlobal('fetch', fetchMock);
});

test('report carries message, stack and path only — no query string', () => {
  window.history.pushState({}, '', '/flocks/7/bill?farm=F001&pan=ABCDE1234F');
  const r = buildReport(new Error('boom'), { componentStack: 'at Bill', source: 'boundary' });
  expect(r.message).toBe('boom');
  expect(r.stack).toContain('boom');
  expect(r.component_stack).toBe('at Bill');
  expect(r.path).toBe('/flocks/7/bill');
  expect(JSON.stringify(r)).not.toContain('ABCDE1234F');
});

test('long stacks are truncated and non-Error values are handled', () => {
  const e = new Error('x');
  e.stack = 'y'.repeat(10000);
  expect(buildReport(e).stack).toHaveLength(4000);
  expect(buildReport('a string').message).toBe('a string');
  expect(buildReport(undefined).message).toBe('Unknown error');
});

test('posts to /client-errors/ with the auth token when logged in', () => {
  localStorage.setItem('access_token', 'tok123');
  expect(reportClientError(new Error('boom'))).toBe(true);
  const [url, opts] = fetchMock.mock.calls[0];
  expect(url).toMatch(/\/client-errors\/$/);
  expect(opts.method).toBe('POST');
  expect(opts.headers.Authorization).toBe('Bearer tok123');
  expect(JSON.parse(opts.body).message).toBe('boom');
});

test('the same error is sent once per minute (dedupe)', () => {
  reportClientError(new Error('same'));
  reportClientError(new Error('same'));
  reportClientError(new Error('different'));
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test('at most 10 reports per page load (no flood from a render loop)', () => {
  for (let i = 0; i < 25; i++) reportClientError(new Error(`e${i}`));
  expect(fetchMock).toHaveBeenCalledTimes(10);
});

test('reporting never throws, even if fetch does', () => {
  vi.stubGlobal('fetch', () => { throw new Error('offline'); });
  expect(() => reportClientError(new Error('boom'))).not.toThrow();
});
