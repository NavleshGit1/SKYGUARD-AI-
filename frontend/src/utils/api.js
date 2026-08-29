/**
 * SkyGuard AI — Unified API & WebSocket Endpoint Resolver
 * Supports local development, Docker, and Cloud Deployments (Render + Vercel).
 */
import axios from 'axios';

// 1. Resolve Base API URL from Environment with fallback to live Render backend
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' && window.location.hostname.includes('vercel.app')
    ? 'https://skyguard-backend-y9nh.onrender.com'
    : '')
).replace(/\/$/, '');

// 2. Configure Global Axios Instance
if (API_BASE_URL) {
  axios.defaults.baseURL = API_BASE_URL;
}

/**
 * Resolves a full API URL given a relative endpoint path.
 * @param {string} endpoint - e.g. '/api/v1/stations'
 * @returns {string} - Full URL or relative path
 */
export function apiUrl(endpoint) {
  const cleanPath = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return API_BASE_URL ? `${API_BASE_URL}${cleanPath}` : cleanPath;
}

/**
 * Resilient wrapper around native fetch that prepends API_BASE_URL
 */
export async function apiFetch(endpoint, options = {}) {
  const url = apiUrl(endpoint);
  return fetch(url, options);
}

/**
 * Derives the optimal WebSocket live feed URL based on active deployment configuration.
 */
export function getWebSocketUrl() {
  if (import.meta.env.VITE_WS_BASE_URL) {
    const wsBase = import.meta.env.VITE_WS_BASE_URL.replace(/\/$/, '');
    return wsBase.includes('/api/v1/ws') ? wsBase : `${wsBase}/api/v1/ws/live-feed`;
  }

  const targetUrl = API_BASE_URL || (typeof window !== 'undefined' && window.location.hostname.includes('vercel.app')
    ? 'https://skyguard-backend-y9nh.onrender.com'
    : '');

  if (targetUrl) {
    const isSecure = targetUrl.startsWith('https://');
    const wsProto = isSecure ? 'wss:' : 'ws:';
    const host = targetUrl.replace(/^https?:\/\//, '').replace(/\/$/, '');
    return `${wsProto}//${host}/api/v1/ws/live-feed`;
  }

  // Local development fallback
  const hostname = (typeof window !== 'undefined' && window.location.hostname) ? window.location.hostname : 'localhost';
  return `ws://${hostname}:8000/api/v1/ws/live-feed`;
}
