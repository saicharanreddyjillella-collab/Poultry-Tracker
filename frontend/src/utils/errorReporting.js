// E12 — report frontend crashes to the backend (/api/client-errors/), which
// logs them at ERROR level → app.log and, when configured, Sentry (E7).
// Uses fetch (not the axios instance) so a broken interceptor can't loop.
// Sends no business data: message, stack, component stack, page path only.

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const MAX_REPORTS_PER_PAGE = 10;
const DEDUPE_MS = 60_000;
const MAX_LEN = { message: 500, stack: 4000, componentStack: 4000 };

let sent = 0;
const recent = new Map(); // message → last sent timestamp

const clip = (s, n) => (s == null ? '' : String(s).slice(0, n));

export function buildReport(error, extra = {}) {
  const err = error instanceof Error ? error : new Error(String(error ?? 'Unknown error'));
  return {
    message: clip(err.message || err.name || 'Error', MAX_LEN.message),
    stack: clip(err.stack, MAX_LEN.stack),
    component_stack: clip(extra.componentStack, MAX_LEN.componentStack),
    source: extra.source || 'boundary',
    // path only — query strings can carry ids/filters we don't need
    path: typeof window !== 'undefined' ? window.location.pathname : '',
    release: import.meta.env.VITE_APP_RELEASE || '',
  };
}

export function reportClientError(error, extra = {}) {
  try {
    const report = buildReport(error, extra);
    const now = Date.now();
    const last = recent.get(report.message);
    if (last && now - last < DEDUPE_MS) return false;
    if (sent >= MAX_REPORTS_PER_PAGE) return false;
    recent.set(report.message, now);
    sent += 1;

    const headers = { 'Content-Type': 'application/json' };
    const token = localStorage.getItem('access_token');
    if (token) headers.Authorization = `Bearer ${token}`;
    fetch(`${API_BASE}/client-errors/`, {
      method: 'POST', headers, body: JSON.stringify(report), keepalive: true,
    }).catch(() => {});
    return true;
  } catch {
    return false; // reporting must never throw
  }
}

let installed = false;
export function installGlobalErrorHandlers() {
  if (installed || typeof window === 'undefined') return;
  installed = true;
  window.addEventListener('error', (e) => {
    // Ignore resource load errors (img/script 404s) — they have no error object.
    if (e.error) reportClientError(e.error, { source: 'window.onerror' });
  });
  window.addEventListener('unhandledrejection', (e) => {
    const reason = e.reason;
    // Axios HTTP errors are handled by the screens that made the call.
    if (reason && reason.isAxiosError) return;
    reportClientError(reason, { source: 'unhandledrejection' });
  });
}

// test helper
export function _resetReporting() {
  sent = 0;
  recent.clear();
}
