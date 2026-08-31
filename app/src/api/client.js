import axios from 'axios';

/**
 * Same-origin API client.
 *
 * Every request goes to a relative `/api/...` path: in production Vercel
 * rewrites those onto the FastAPI serverless function, and in development the
 * Vite proxy forwards them to Uvicorn.  No component ever needs to know an API
 * hostname, so nothing has to change between local and deployed environments.
 */
const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { Accept: 'application/json' },
});

const TOKEN_KEY = 'routesathi.token';

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable (private browsing) - the session stays in memory */
  }
}

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let onUnauthorized = null;

/** Registered by AuthProvider so an expired token signs the user out once. */
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && onUnauthorized) onUnauthorized();
    return Promise.reject(error);
  },
);

/** Pull a displayable message out of an axios error. */
export function errorMessage(error, fallback = 'Something went wrong. Please try again.') {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail[0]?.msg || fallback;
  }
  if (error?.code === 'ECONNABORTED') return 'The request timed out. Please try again.';
  if (error?.message === 'Network Error') {
    return 'Cannot reach the RouteSathi server. Check your connection.';
  }
  return fallback;
}

export default client;
