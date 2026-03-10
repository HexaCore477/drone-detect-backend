/** Base API configuration. Uses Vite proxy in dev, direct URL in production. */
const API_BASE = import.meta.env.DEV ? '' : 'http://localhost:8000';

export function apiUrl(path: string): string {
  const base = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE}/api${base}`;
}
