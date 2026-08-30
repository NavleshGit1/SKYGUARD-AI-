import axios from 'axios';

// 1. Resolve API Base URL
// In development: Vite proxies /api to http://localhost:8000
// In production (Vercel): VITE_API_URL should point to Render (e.g., https://skyguard-api.onrender.com)
const RAW_API_URL = import.meta.env.VITE_API_URL || '';
export const API_BASE_URL = RAW_API_URL.replace(/\/+$/, '');

// 2. Resolve WebSocket URL
export const getWebSocketUrl = () => {
  const customWs = import.meta.env.VITE_WS_URL;
  if (customWs) {
    return customWs;
  }

  // If VITE_API_URL is provided (e.g., https://skyguard-backend.onrender.com)
  if (API_BASE_URL) {
    const wsProto = API_BASE_URL.startsWith('https') ? 'wss://' : 'ws://';
    const host = API_BASE_URL.replace(/^https?:\/\//, '');
    return `${wsProto}${host}/api/v1/ws/live-feed`;
  }

  // Fallback to current browser location (standard for local development / reverse proxies)
  const isHttps = window.location.protocol === 'https:';
  const wsProto = isHttps ? 'wss://' : 'ws://';
  const hostname = window.location.hostname || 'localhost';
  const port = window.location.port === '5173' ? '8000' : window.location.port;
  return `${wsProto}${hostname}${port ? `:${port}` : ''}/api/v1/ws/live-feed`;
};

// 3. Create pre-configured Axios client with 60s timeout for Render free tier cold starts
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60 seconds tolerance for Render spin-up from sleep
  headers: {
    'Content-Type': 'application/json',
  },
});

// 4. Request interceptor to automatically attach JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('skyguard_token');
    if (token && token !== 'null' && token !== 'undefined') {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 5. Response interceptor for automatic 401 handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('skyguard_token');
      localStorage.removeItem('skyguard_refresh_token');
      localStorage.removeItem('skyguard_user');
    }
    return Promise.reject(error);
  }
);

export default api;
