// Minimal typed fetch wrapper: bearer auth, JSON, and the backend's error envelope.

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
const TOKEN_KEY = 'cloudorbit.token';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = 'ApiError';
  }

  /** Field-level validation messages, if the backend provided any. */
  get fieldErrors(): Record<string, string> {
    const fields = this.details?.fields;
    return fields && typeof fields === 'object' ? (fields as Record<string, string>) : {};
  }
}

export const tokenStore = {
  get(): string | null {
    try {
      return sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string | null): void {
    try {
      if (token) sessionStorage.setItem(TOKEN_KEY, token);
      else sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* storage unavailable (private mode) */
    }
  },
};

let unauthorizedHandler: (() => void) | null = null;
export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

type Query = Record<string, string | number | boolean | null | undefined>;

export function buildQuery(params?: Query): string {
  if (!params) return '';
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  });
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

export async function apiRequest<T>(
  path: string,
  options: { method?: string; body?: unknown; query?: Query; form?: URLSearchParams } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (options.form) {
    body = options.form;
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
  } else if (options.body !== undefined) {
    body = JSON.stringify(options.body);
    headers['Content-Type'] = 'application/json';
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}${buildQuery(options.query)}`, {
      method: options.method ?? 'GET',
      headers,
      body,
    });
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the API server');
  }

  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const err = payload?.error;
    if (response.status === 401 && token) {
      tokenStore.set(null);
      unauthorizedHandler?.();
    }
    throw new ApiError(
      response.status,
      err?.code ?? 'http_error',
      err?.message ?? `Request failed (${response.status})`,
      err?.details ?? {},
    );
  }
  return payload as T;
}
