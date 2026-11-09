import type { Role } from '../api/types';

// Mirrors backend app/core/permissions.py. The backend remains the enforcement point;
// the UI only uses this to hide actions a user cannot perform.
export type Permission =
  | 'users:manage'
  | 'accounts:read'
  | 'accounts:write'
  | 'resources:read'
  | 'resources:sync'
  | 'infra:read'
  | 'infra:plan'
  | 'infra:apply'
  | 'costs:read'
  | 'budgets:write'
  | 'alerts:manage'
  | 'audit:read';

const READ_ONLY: Permission[] = ['accounts:read', 'resources:read', 'infra:read', 'costs:read'];

export const ROLE_PERMISSIONS: Record<Role, ReadonlySet<Permission>> = {
  viewer: new Set(READ_ONLY),
  operator: new Set<Permission>([...READ_ONLY, 'resources:sync', 'infra:plan', 'infra:apply', 'alerts:manage']),
  admin: new Set<Permission>([
    ...READ_ONLY,
    'users:manage',
    'accounts:write',
    'resources:sync',
    'infra:plan',
    'infra:apply',
    'budgets:write',
    'alerts:manage',
    'audit:read',
  ]),
};

export function roleHasPermission(role: Role | undefined, permission: Permission): boolean {
  return role ? ROLE_PERMISSIONS[role]?.has(permission) ?? false : false;
}
