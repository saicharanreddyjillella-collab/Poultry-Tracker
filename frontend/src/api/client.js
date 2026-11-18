import axios from 'axios';

// Extract readable error message from API error
export function getErrorMessage(err) {
  const data = err.response?.data;
  if (!data) return 'Something went wrong. Please try again.';
  if (typeof data === 'string') return data;
  if (data.error) return data.error;
  if (data.detail) return data.detail;
  // DRF field errors: {field: ["message"]} or {field: "message"}
  const messages = [];
  for (const [key, val] of Object.entries(data)) {
    const msg = Array.isArray(val) ? val.join(', ') : String(val);
    messages.push(msg);
  }
  return messages.join(' ') || 'Something went wrong.';
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const API = axios.create({ baseURL: API_BASE });

// Add auth token to every request
API.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── E15: silent token refresh ───────────────────────────────────────────────
// Access tokens are short-lived (30 min). On a 401 we swap the refresh token
// for a new pair and replay the request, so users are only signed out when
// the refresh token itself is dead (7 days idle, logout, password change).
//  * single-flight: concurrent 401s share one refresh call
//  * cross-tab: a Web Lock serialises refreshes between tabs; refresh tokens
//    rotate (old one is revoked), so a second tab must reuse the new pair
//    instead of replaying the old token
//  * auth endpoints and already-retried requests never trigger a refresh

const NO_REFRESH = ['/auth/login/', '/auth/token/refresh/', '/auth/logout/', '/auth/setup/'];
let refreshInFlight = null;

function clearSession() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
}

export function sessionExpired() {
  clearSession();
  if (window.location.pathname !== '/login') {
    window.location.href = '/login?expired=1';
  }
}

async function doRefresh(failedAccess) {
  // Another tab may already have refreshed while we waited for the lock.
  const current = localStorage.getItem('access_token');
  if (current && current !== failedAccess) return current;

  const refresh = localStorage.getItem('refresh_token');
  if (!refresh) throw new Error('no refresh token');
  // Bare axios: must not go through this interceptor.
  const res = await axios.post(`${API_BASE}/auth/token/refresh/`, { refresh });
  localStorage.setItem('access_token', res.data.access);
  if (res.data.refresh) localStorage.setItem('refresh_token', res.data.refresh);
  return res.data.access;
}

export function refreshAccessToken(failedAccess) {
  if (!refreshInFlight) {
    const run = () => doRefresh(failedAccess);
    const locked = typeof navigator !== 'undefined' && navigator.locks?.request
      ? navigator.locks.request('poultrytrack-token-refresh', run)
      : run();
    refreshInFlight = Promise.resolve(locked).finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

API.interceptors.response.use(
  res => res,
  async err => {
    const original = err.config;
    const status = err.response?.status;
    const url = original?.url || '';
    if (status !== 401 || !original || original._retried || NO_REFRESH.some(p => url.includes(p))) {
      if (status === 401 && original?._retried) sessionExpired();
      return Promise.reject(err);
    }
    original._retried = true;
    const failedAccess = (original.headers?.Authorization || '').replace(/^Bearer /, '') || null;
    try {
      const access = await refreshAccessToken(failedAccess);
      original.headers = { ...(original.headers || {}), Authorization: `Bearer ${access}` };
      return API(original);
    } catch {
      sessionExpired();
      return Promise.reject(err);
    }
  }
);

export { API };

export const authAPI = {
  checkSetup: () => API.get('/auth/check-setup/'),
  setup: (data) => API.post('/auth/setup/', data),
  login: (username, password) => API.post('/auth/login/', { username, password }),
  logout: (refresh) => API.post('/auth/logout/', { refresh }),
  me: () => API.get('/auth/me/'),
  changePassword: (current_password, new_password) => API.post('/auth/change-password/', { current_password, new_password }),
  listUsers: () => API.get('/auth/users/'),
  createUser: (data) => API.post('/auth/users/', data),
  updateUser: (id, data) => API.put(`/auth/users/${id}/`, data),
  deleteUser: (id) => API.delete(`/auth/users/${id}/`),
  listRegions: () => API.get('/auth/regions/'),
};

export const farmAPI = {
  list: () => API.get('/farms/'),
  create: (data) => API.post('/farms/', data),
  get: (id) => API.get(`/farms/${id}/`),
  update: (id, data) => API.put(`/farms/${id}/`, data),
  delete: (id) => API.delete(`/farms/${id}/`),
  cumulative: (id) => API.get(`/farms/${id}/cumulative/`),
  performanceHistory: (id) => API.get(`/farms/${id}/performance-history/`),
};

// E14 — admin Recycle Bin
export const trashAPI = {
  list: () => API.get('/trash/'),
  restore: (batch) => API.post(`/trash/${batch}/restore/`),
};

export const documentAPI = {
  list: (params) => API.get('/documents/', { params }),
  upload: (formData) => API.post('/documents/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  delete: (id) => API.delete(`/documents/${id}/`),
};

export const flockAPI = {
  list: () => API.get('/flocks/'),
  create: (data) => API.post('/flocks/', data),
  get: (id) => API.get(`/flocks/${id}/`),
  update: (id, data) => API.put(`/flocks/${id}/`, data),
  cumulative: (id) => API.get(`/flocks/${id}/cumulative/`),
};

export const dailyEntryAPI = {
  list: (flockId) => API.get(`/daily-entries/?flock=${flockId}`),
  create: (data) => API.post('/daily-entries/', data),
  update: (id, data) => API.put(`/daily-entries/${id}/`, data),
  delete: (id) => API.delete(`/daily-entries/${id}/`),
};

export const saleAPI = {
  list: (flockId) => API.get(`/sales/?flock=${flockId}`),
  create: (data) => API.post('/sales/', data),
  update: (id, data) => API.put(`/sales/${id}/`, data),
  delete: (id) => API.delete(`/sales/${id}/`),
};

export const feedRateAPI = {
  list: () => API.get('/feed-rates/'),
  create: (data) => API.post('/feed-rates/', data),
  update: (id, data) => API.put(`/feed-rates/${id}/`, data),
  delete: (id) => API.delete(`/feed-rates/${id}/`),
};

export const feedOrderAPI = {
  list: (params) => API.get('/feed-orders/', { params }),
  create: (data) => API.post('/feed-orders/', data),
  markSent: (id) => API.post(`/feed-orders/${id}/mark-sent/`),
  markDelivered: (id) => API.post(`/feed-orders/${id}/mark-delivered/`),
  cancel: (id) => API.post(`/feed-orders/${id}/cancel/`),
};

export const feedTransferAPI = {
  list: (farmId) => API.get(`/feed-transfers/${farmId ? `?farm=${farmId}` : ''}`),
  create: (data) => API.post('/feed-transfers/', data),
};

export const feedStockAPI = {
  list: (farmId) => API.get(`/feed-stock/${farmId ? `?farm=${farmId}` : ''}`),
};

export const medicationAPI = {
  list: (flockId) => API.get(`/medications/?flock=${flockId}`),
  create: (data) => API.post('/medications/', data),
};

export const dashboardAPI = {
  get: () => API.get('/dashboard/'),
};

export const reportAPI = {
  monthly: (year, month) => API.get(`/reports/monthly/?year=${year}&month=${month}`),
  region: (region) => API.get(`/reports/region/${region ? `?region=${encodeURIComponent(region)}` : ''}`),
  tillDate: () => API.get('/reports/till-date/'),
  feedForecast: (weeks) => API.get(`/reports/feed-forecast/${weeks ? `?weeks=${weeks}` : ''}`),
  ownerDashboard: (periodDays) => API.get(`/reports/owner-dashboard/${periodDays ? `?period_days=${periodDays}` : ''}`),
  breakEven: (finishAge) => API.get(`/reports/break-even/${finishAge ? `?finish_age=${finishAge}` : ''}`),
};

export const billAPI = {
  config: () => API.get('/bill-config/'),
  updateConfig: (data) => API.put('/bill-config/', data),
  closeAndBill: (flockId, flags) => API.post(`/flocks/${flockId}/close-and-bill/`, flags || {}),
  get: (flockId) => API.get(`/flocks/${flockId}/bill/`),
  list: () => API.get('/bills/'),
  reopen: (flockId, reason) => API.post(`/flocks/${flockId}/reopen-bill/`, { reason }),
  history: (flockId) => API.get(`/flocks/${flockId}/bill-history/`),
};

// Authenticated file download (blob) — reused by report export buttons.
export async function downloadFile(url, filename) {
  const token = localStorage.getItem('access_token');
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error('Export failed');
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = window.URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  window.URL.revokeObjectURL(a.href);
}

export default API;

// ─── Insights: feed audit, heat stress, hatcheries, lift planner ───
export const feedCountAPI = {
  list: (flockId) => API.get(`/feed-counts/?flock=${flockId}`),
  create: (data) => API.post('/feed-counts/', data),
  remove: (id) => API.delete(`/feed-counts/${id}/`),
};

export const insightsAPI = {
  feedAudit: (region) => API.get(`/reports/feed-audit/${region ? `?region=${encodeURIComponent(region)}` : ''}`),
  heatStress: () => API.get('/reports/heat-stress/'),
};

export const regionLocationAPI = {
  list: () => API.get('/region-locations/'),
  save: (region, latitude, longitude) => API.post('/region-locations/', { region, latitude, longitude }),
};
