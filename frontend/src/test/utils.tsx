import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { tokenStore } from '../api/client';
import type { Role, User } from '../api/types';
import { AuthProvider } from '../auth/AuthContext';

export function makeUser(role: Role = 'admin', overrides: Partial<User> = {}): User {
  return {
    id: `user-${role}`,
    email: `${role}@cloudorbit.dev`,
    full_name: `${role[0].toUpperCase()}${role.slice(1)} User`,
    role,
    is_active: true,
    job_title: null,
    timezone: 'UTC',
    last_login_at: null,
    created_at: '2026-11-01T00:00:00Z',
    ...overrides,
  };
}

/**
 * Render a page inside React Query + Router + Auth. When `signedIn` is set, a token is placed
 * in storage so AuthProvider loads the user through the (mocked) `api.me`.
 */
export function renderPage(ui: ReactElement, { path = '/', signedIn = true }: { path?: string; signedIn?: boolean } = {}) {
  if (signedIn) tokenStore.set('test-token');
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <Routes>
            <Route path="*" element={ui} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
