import axios from 'axios';

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
};

export const billAPI = {
  config: () => API.get('/bill-config/'),
  updateConfig: (data) => API.put('/bill-config/', data),
  closeAndBill: (flockId) => API.post(`/flocks/${flockId}/close-and-bill/`),
  get: (flockId) => API.get(`/flocks/${flockId}/bill/`),
  list: () => API.get('/bills/'),
};

export default API;
