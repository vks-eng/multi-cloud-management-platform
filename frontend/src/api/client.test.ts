import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiRequest, buildQuery, onUnauthorized, tokenStore } from './client';

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
  onUnauthorized(null);
});

describe('api client', () => {
  it('builds query strings, skipping empty values', () => {
    expect(buildQuery({ a: 1, b: '', c: undefined, d: null, e: true })).toBe('?a=1&e=true');
    expect(buildQuery()).toBe('');
  });

  it('sends the bearer token and JSON body', async () => {
    tokenStore.set('abc');
    const fetchMock = mockFetch(200, { ok: true });
    await apiRequest('/things', { method: 'POST', body: { x: 1 }, query: { limit: 5 } });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/things?limit=5');
    expect(init.headers.Authorization).toBe('Bearer abc');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(init.body).toBe('{"x":1}');
  });

  it('parses the error envelope into ApiError with field errors', async () => {
    mockFetch(422, { error: { code: 'business_rule_violation', message: 'Invalid', details: { fields: { name: 'bad' } } } });
    const err = await apiRequest('/x').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(422);
    expect((err as ApiError).code).toBe('business_rule_violation');
    expect((err as ApiError).fieldErrors).toEqual({ name: 'bad' });
  });

  it('clears the session and notifies on 401', async () => {
    tokenStore.set('expired');
    const handler = vi.fn();
    onUnauthorized(handler);
    mockFetch(401, { error: { code: 'not_authenticated', message: 'Invalid or expired token' } });
    await expect(apiRequest('/auth/me')).rejects.toThrow('Invalid or expired token');
    expect(tokenStore.get()).toBeNull();
    expect(handler).toHaveBeenCalledOnce();
  });

  it('maps network failures to a readable error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(apiRequest('/x')).rejects.toMatchObject({ status: 0, code: 'network_error' });
  });

  it('returns undefined for 204 responses', async () => {
    mockFetch(204, null);
    await expect(apiRequest('/x', { method: 'DELETE' })).resolves.toBeUndefined();
  });
});
