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

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
});

// Add auth token to every request
API.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401, redirect to login
API.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export const authAPI = {
  checkSetup: () => API.get('/auth/check-setup/'),
  setup: (data) => API.post('/auth/setup/', data),
  login: (username, password) => API.post('/auth/login/', { username, password }),
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
};

export const billAPI = {
  config: () => API.get('/bill-config/'),
  updateConfig: (data) => API.put('/bill-config/', data),
  closeAndBill: (flockId, flags) => API.post(`/flocks/${flockId}/close-and-bill/`, flags || {}),
  get: (flockId) => API.get(`/flocks/${flockId}/bill/`),
  list: () => API.get('/bills/'),
};

// ─── Accounting core ───
export const accountingAPI = {
  accounts: (params) => API.get('/accounting/accounts/', { params }),
  parties: (params) => API.get('/accounting/parties/', { params }),
  createParty: (data) => API.post('/accounting/parties/', data),
  updateParty: (id, data) => API.put(`/accounting/parties/${id}/`, data),
  partyStatement: (id, params) => API.get(`/accounting/reports/party/${id}/`, { params }),
  trialBalance: (params) => API.get('/accounting/reports/trial-balance/', { params }),
  pnl: (params) => API.get('/accounting/reports/pnl/', { params }),
  cashBook: (params) => API.get('/accounting/reports/cash-book/', { params }),
  outstanding: (params) => API.get('/accounting/reports/outstanding/', { params }),
  bookLock: (params) => API.get('/accounting/book-lock/', { params }),
  setBookLock: (data) => API.post('/accounting/book-lock/', data),
};

// ─── Inventory ───
export const inventoryAPI = {
  units: () => API.get('/inventory/units/'),
  createUnit: (data) => API.post('/inventory/units/', data),
  items: (params) => API.get('/inventory/items/', { params }),
  createItem: (data) => API.post('/inventory/items/', data),
  updateItem: (id, data) => API.put(`/inventory/items/${id}/`, data),
  stockOnHand: (params) => API.get('/inventory/stock-on-hand/', { params }),
};

// ─── Chicken Center ───
export const chickenAPI = {
  sales: (params) => API.get('/chicken/sales/', { params }),
  createSale: (data) => API.post('/chicken/sales/', data),
  purchases: () => API.get('/chicken/purchases/'),
  createPurchase: (data) => API.post('/chicken/purchases/', data),
  collections: () => API.get('/chicken/collections/'),
  createCollection: (data) => API.post('/chicken/collections/', data),
  payments: () => API.get('/chicken/payments/'),
  createPayment: (data) => API.post('/chicken/payments/', data),
  expenses: () => API.get('/chicken/expenses/'),
  createExpense: (data) => API.post('/chicken/expenses/', data),
  shrinkage: () => API.get('/chicken/shrinkage/'),
  createShrinkage: (data) => API.post('/chicken/shrinkage/', data),
  reverse: (kind, id) => API.post(`/chicken/reverse/${kind}/${id}/`),
  pendingBills: (params) => API.get('/chicken/pending-bills/', { params }),
  ageing: () => API.get('/chicken/ageing/'),
  sale: (id) => API.get(`/chicken/sales/${id}/`),
  openingParty: (data) => API.post('/chicken/opening/party/', data),
  openingCash: (data) => API.post('/chicken/opening/cash/', data),
  exportUrl: (kind, params) => {
    const q = params ? '?' + new URLSearchParams(params).toString() : '';
    return `${import.meta.env.VITE_API_URL || '/api'}/chicken/export/${kind}/${q}`;
  },
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
