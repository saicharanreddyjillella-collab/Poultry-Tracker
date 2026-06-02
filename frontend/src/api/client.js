import axios from 'axios';

const API = axios.create({
  baseURL: 'http://localhost:8000/api',
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
  listUsers: () => API.get('/auth/users/'),
  createUser: (data) => API.post('/auth/users/', data),
  updateUser: (id, data) => API.put(`/auth/users/${id}/`, data),
  deleteUser: (id) => API.delete(`/auth/users/${id}/`),
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

export default API;
