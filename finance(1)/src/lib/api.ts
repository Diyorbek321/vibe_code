/**
 * <<< INTEGRATION: typed fetch wrapper for FastAPI backend >>>
 *
 * - Reads JWT from localStorage (key: "finance_token")
 * - Injects Authorization: Bearer header on every request
 * - On 401: clears stored token and dispatches a custom event so the
 *   auth store can react without a circular import
 * - Base URL: VITE_API_URL env var (defaults to "" so Vite proxy handles it)
 */

const BASE_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
const TOKEN_KEY = 'finance_token';

export const tokenStorage = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string): void => localStorage.setItem(TOKEN_KEY, token),
  clear: (): void => localStorage.removeItem(TOKEN_KEY),
};

function authHeaders(): Record<string, string> {
  const token = tokenStorage.get();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    tokenStorage.clear();
    // Let the auth store / router react without a circular import
    window.dispatchEvent(new CustomEvent('finance:unauthorized'));
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? body.error ?? detail;
    } catch {
      // non-JSON error body — keep the default
    }
    throw new ApiError(res.status, detail);
  }

  // 204 No Content — return undefined cast to T
  if (res.status === 204) return undefined as unknown as T;

  return res.json() as Promise<T>;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(options.headers as Record<string, string> | undefined ?? {}),
    },
  });
  return handleResponse<T>(res);
}

export const http = {
  get: <T>(path: string) => apiFetch<T>(path),

  post: <T>(path: string, body: unknown) =>
    apiFetch<T>(path, { method: 'POST', body: JSON.stringify(body) }),

  patch: <T>(path: string, body: unknown) =>
    apiFetch<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),

  delete: (path: string) =>
    apiFetch<void>(path, { method: 'DELETE' }),
};
