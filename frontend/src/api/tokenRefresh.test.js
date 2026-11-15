// E15 — silent token refresh in the axios client (real interceptors, fake network).
import axios from 'axios';
import { vi, beforeEach, afterEach } from 'vitest';
import { API, farmAPI, authAPI } from './client';

let calls, server, origAdapter, origPost, hrefSet;

// Fake backend: access tokens "A1", "A2"... are valid once issued; "EXPIRED" is not.
function makeServer({ refreshFails = false } = {}) {
  let n = 1;
  const valid = new Set(['A1']);
  const refreshCalls = [];
  return {
    valid, refreshCalls,
    handle(config) {
      const auth = config.headers?.Authorization || config.headers?.get?.('Authorization') || '';
      const tok = String(auth).replace('Bearer ', '');
      calls.push({ url: config.url, tok });
      if (config.url.includes('/auth/login/')) return reply(config, 401, { detail: 'bad creds' });
      if (!valid.has(tok)) return reply(config, 401, { detail: 'Token is invalid or expired' });
      return reply(config, 200, { ok: true, url: config.url });
    },
    refresh(body) {
      refreshCalls.push(body.refresh);
      if (refreshFails) return Promise.reject(Object.assign(new Error('401'), { response: { status: 401 } }));
      n += 1;
      const access = `A${n}`;
      valid.add(access);
      return Promise.resolve({ data: { access, refresh: `R${n}` } });
    },
  };
}

function reply(config, status, data) {
  const res = { data, status, statusText: String(status), headers: {}, config };
  if (status >= 400) {
    const err = new Error(`Request failed with status code ${status}`);
    err.config = config; err.response = res; err.isAxiosError = true;
    return Promise.reject(err);
  }
  return Promise.resolve(res);
}

beforeEach(() => {
  calls = [];
  server = makeServer();
  origAdapter = API.defaults.adapter;
  API.defaults.adapter = (config) => server.handle(config);
  origPost = axios.post;
  axios.post = vi.fn((url, body) => server.refresh(body));
  localStorage.setItem('access_token', 'EXPIRED');
  localStorage.setItem('refresh_token', 'R1');
  localStorage.setItem('user', '{"id":1}');
  hrefSet = vi.fn();
  vi.stubGlobal('location', { pathname: '/farms', set href(v) { hrefSet(v); } });
});

afterEach(() => {
  API.defaults.adapter = origAdapter;
  axios.post = origPost;
  vi.unstubAllGlobals();
});

test('an expired access token is refreshed silently and the request replayed', async () => {
  const res = await farmAPI.list();
  expect(res.data.ok).toBe(true);
  expect(axios.post).toHaveBeenCalledTimes(1);
  expect(axios.post.mock.calls[0][0]).toMatch(/\/auth\/token\/refresh\/$/);
  expect(server.refreshCalls).toEqual(['R1']);
  expect(localStorage.getItem('access_token')).toBe('A2');
  expect(localStorage.getItem('refresh_token')).toBe('R2');      // rotated token stored
  expect(calls.map(c => c.tok)).toEqual(['EXPIRED', 'A2']);       // original, then replay
  expect(hrefSet).not.toHaveBeenCalled();                         // user never noticed
});

test('concurrent 401s share ONE refresh (rotation would revoke a second one)', async () => {
  const results = await Promise.all([farmAPI.list(), farmAPI.get(1), farmAPI.cumulative(1)]);
  expect(results.every(r => r.data.ok)).toBe(true);
  expect(axios.post).toHaveBeenCalledTimes(1);
  expect(server.refreshCalls).toEqual(['R1']);
});

test('if another tab already refreshed, reuse its token instead of refreshing again', async () => {
  // Request goes out with EXPIRED; meanwhile another tab stored a fresh pair.
  server.valid.add('A9');
  const p = farmAPI.list();
  localStorage.setItem('access_token', 'A9');
  localStorage.setItem('refresh_token', 'R9');
  const res = await p;
  expect(res.data.ok).toBe(true);
  expect(axios.post).not.toHaveBeenCalled();
  expect(calls.at(-1).tok).toBe('A9');
});

test('dead refresh token → session cleared and sent to login with a notice', async () => {
  server = makeServer({ refreshFails: true });
  await expect(farmAPI.list()).rejects.toBeTruthy();
  expect(localStorage.getItem('access_token')).toBeNull();
  expect(localStorage.getItem('refresh_token')).toBeNull();
  expect(localStorage.getItem('user')).toBeNull();
  expect(hrefSet).toHaveBeenCalledWith('/login?expired=1');
});

test('no refresh token at all → straight to login', async () => {
  localStorage.removeItem('refresh_token');
  await expect(farmAPI.list()).rejects.toBeTruthy();
  expect(axios.post).not.toHaveBeenCalled();
  expect(hrefSet).toHaveBeenCalledWith('/login?expired=1');
});

test('a wrong password on the login form never triggers refresh or redirect', async () => {
  await expect(authAPI.login('admin', 'nope')).rejects.toMatchObject({ response: { status: 401 } });
  expect(axios.post).not.toHaveBeenCalled();
  expect(hrefSet).not.toHaveBeenCalled();
});

test('a request still 401 after refresh is not retried forever', async () => {
  // Refresh "works" but the server rejects the new token too.
  server.refresh = (body) => { server.refreshCalls.push(body.refresh); return Promise.resolve({ data: { access: 'STILL_BAD' } }); };
  await expect(farmAPI.list()).rejects.toBeTruthy();
  expect(server.refreshCalls).toHaveLength(1);
  expect(calls).toHaveLength(2);
  expect(hrefSet).toHaveBeenCalledWith('/login?expired=1');
});

test('non-401 errors pass straight through', async () => {
  API.defaults.adapter = (config) => reply(config, 500, { error: 'boom' });
  await expect(farmAPI.list()).rejects.toMatchObject({ response: { status: 500 } });
  expect(axios.post).not.toHaveBeenCalled();
  expect(hrefSet).not.toHaveBeenCalled();
});
