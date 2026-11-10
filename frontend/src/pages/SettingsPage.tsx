import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, X } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { api } from '../api/endpoints';
import type { Role, User } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { Badge, StatusBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card, ErrorState, PageHeader, Spinner, errorMessage } from '../components/ui/Card';
import { DataTable, type Column } from '../components/ui/DataTable';
import { TextField } from '../components/ui/Field';
import { formatDateTime } from '../lib/format';

function ProfileCard() {
  const { user, refreshUser } = useAuth();
  const [form, setForm] = useState({ full_name: user?.full_name ?? '', job_title: user?.job_title ?? '', timezone: user?.timezone ?? 'UTC' });
  const [saved, setSaved] = useState(false);
  const update = useMutation({
    mutationFn: () => api.updateProfile({ full_name: form.full_name, job_title: form.job_title || null, timezone: form.timezone }),
    onSuccess: async () => {
      await refreshUser();
      setSaved(true);
    },
  });
  return (
    <Card title="Profile" description={user?.email}>
      <form
        className="grid gap-3 sm:grid-cols-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          setSaved(false);
          update.mutate();
        }}
      >
        <TextField label="Full name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        <TextField label="Job title" value={form.job_title} onChange={(e) => setForm({ ...form, job_title: e.target.value })} />
        <TextField label="Time zone" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
        <div className="flex items-center gap-3 sm:col-span-3">
          <Button type="submit" loading={update.isPending}>
            Save profile
          </Button>
          {saved && <span role="status" className="text-sm text-emerald-300">Profile updated</span>}
          {update.isError && <span role="alert" className="text-sm text-rose-300">{errorMessage(update.error)}</span>}
        </div>
      </form>
    </Card>
  );
}

function PasswordCard() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const change = useMutation({
    mutationFn: () => api.changePassword(current, next),
    onSuccess: () => {
      setCurrent('');
      setNext('');
    },
  });
  return (
    <Card title="Change password">
      <form
        className="grid gap-3 sm:grid-cols-2"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          change.mutate();
        }}
      >
        <TextField label="Current password" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        <TextField label="New password" type="password" autoComplete="new-password" hint="At least 10 characters, letters and digits." value={next} onChange={(e) => setNext(e.target.value)} />
        <div className="flex items-center gap-3 sm:col-span-2">
          <Button type="submit" variant="secondary" loading={change.isPending} disabled={!current || !next}>
            Update password
          </Button>
          {change.isSuccess && <span role="status" className="text-sm text-emerald-300">Password changed</span>}
          {change.isError && <span role="alert" className="text-sm text-rose-300">{errorMessage(change.error)}</span>}
        </div>
      </form>
    </Card>
  );
}

function UsersCard() {
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const users = useQuery({ queryKey: ['users'], queryFn: () => api.users({ limit: 100 }) });
  const update = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { role?: Role; is_active?: boolean } }) => api.updateUser(id, data),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
  const columns: Column<User>[] = [
    {
      key: 'user',
      header: 'User',
      render: (u) => (
        <div>
          <p className="font-medium text-ink">{u.full_name}</p>
          <p className="text-xs text-muted">{u.email}</p>
        </div>
      ),
    },
    {
      key: 'role',
      header: 'Role',
      render: (u) => (
        <select
          aria-label={`Role for ${u.email}`}
          className="rounded-md bg-canvas px-2 py-1 text-xs text-ink ring-1 ring-line disabled:opacity-60"
          value={u.role}
          disabled={u.id === me?.id}
          onChange={(e) => update.mutate({ id: u.id, data: { role: e.target.value as Role } })}
        >
          <option value="admin">admin</option>
          <option value="operator">operator</option>
          <option value="viewer">viewer</option>
        </select>
      ),
    },
    { key: 'status', header: 'Status', render: (u) => <StatusBadge status={u.is_active ? 'success' : 'cancelled'} /> },
    { key: 'last', header: 'Last sign-in', render: (u) => formatDateTime(u.last_login_at), hideOnMobile: true },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (u) =>
        u.id !== me?.id && (
          <Button size="sm" variant="ghost" onClick={() => update.mutate({ id: u.id, data: { is_active: !u.is_active } })}>
            {u.is_active ? 'Deactivate' : 'Activate'}
          </Button>
        ),
    },
  ];
  return (
    <Card title="Users" description="Manage roles and access (admin only)">
      {users.isPending && <Spinner />}
      {users.isError && <ErrorState error={users.error} />}
      {update.isError && <p className="mb-2 text-sm text-rose-300">{errorMessage(update.error)}</p>}
      {users.data && <DataTable caption="Users" columns={columns} rows={users.data.items} rowKey={(u) => u.id} />}
    </Card>
  );
}

function RolesCard() {
  const roles = useQuery({ queryKey: ['roles'], queryFn: api.roles });
  if (!roles.data) return null;
  const all = Array.from(new Set(roles.data.flatMap((r) => r.permissions))).sort();
  return (
    <Card title="Role permissions" description="Enforced by the API on every request">
      <div className="-mx-5 overflow-x-auto">
        <table className="min-w-full text-sm">
          <caption className="sr-only">Role permission matrix</caption>
          <thead>
            <tr>
              <th scope="col" className="px-5 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-faint">
                Permission
              </th>
              {roles.data.map((r) => (
                <th key={r.role} scope="col" className="px-3 py-2 text-center text-[11px] font-semibold uppercase tracking-wider text-faint">
                  {r.role}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line/60">
            {all.map((p) => (
              <tr key={p}>
                <td className="px-5 py-1.5 font-mono text-xs text-ink/90">{p}</td>
                {roles.data.map((r) => (
                  <td key={r.role} className="px-3 py-1.5 text-center">
                    {r.permissions.includes(p) ? (
                      <Check className="mx-auto h-4 w-4 text-emerald-300" aria-label="granted" />
                    ) : (
                      <X className="mx-auto h-4 w-4 text-faint" aria-label="not granted" />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function SettingsPage() {
  const { user, can } = useAuth();
  return (
    <>
      <PageHeader title="Settings" description="Your profile, security and (for admins) user management" />
      <div className="mb-4 flex items-center gap-2 text-sm text-muted">
        Signed in as <Badge tone="violet">{user?.role}</Badge>
      </div>
      <div className="space-y-6">
        <ProfileCard />
        <PasswordCard />
        {can('users:manage') && <UsersCard />}
        <RolesCard />
      </div>
    </>
  );
}
