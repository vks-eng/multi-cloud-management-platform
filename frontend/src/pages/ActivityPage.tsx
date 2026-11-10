import { useQuery } from '@tanstack/react-query';
import clsx from 'clsx';
import { useState } from 'react';
import { api } from '../api/endpoints';
import type { AuditLog, LoginEvent, ResourceChange } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { StatusBadge } from '../components/ui/Badge';
import { Card, ErrorState, PageHeader, Spinner } from '../components/ui/Card';
import { DataTable, Pagination, type Column } from '../components/ui/DataTable';
import { SelectField } from '../components/ui/Field';
import { formatDateTime, humanize } from '../lib/format';

const LIMIT = 25;
type Tab = 'audit' | 'access' | 'changes';

function AuditTab() {
  const [action, setAction] = useState('');
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const q = useQuery({
    queryKey: ['audit', action, status, offset],
    queryFn: () => api.auditLogs({ action: action || undefined, status: status || undefined, limit: LIMIT, offset }),
  });
  const columns: Column<AuditLog>[] = [
    { key: 'when', header: 'When', render: (a) => <span className="whitespace-nowrap text-xs">{formatDateTime(a.created_at)}</span> },
    { key: 'actor', header: 'Actor', render: (a) => a.actor_email ?? <span className="text-faint">system</span> },
    { key: 'action', header: 'Action', render: (a) => <span className="font-mono text-xs text-orbit-200">{a.action}</span> },
    { key: 'target', header: 'Target', render: (a) => (a.target_type ? `${a.target_type}` : '-'), hideOnMobile: true },
    { key: 'status', header: 'Result', render: (a) => <StatusBadge status={a.status} /> },
    {
      key: 'details',
      header: 'Details',
      render: (a) => <span className="line-clamp-2 break-all font-mono text-[11px] text-faint">{JSON.stringify(a.details)}</span>,
      hideOnMobile: true,
    },
    { key: 'ip', header: 'IP', render: (a) => a.ip_address ?? '-', hideOnMobile: true },
  ];
  return (
    <>
      <div className="mb-4 grid max-w-xl gap-3 sm:grid-cols-2">
        <SelectField
          label="Action"
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setOffset(0);
          }}
          options={[
            { value: '', label: 'All actions' },
            ...['auth', 'user', 'cloud_account', 'resource', 'provisioning', 'budget', 'alert'].map((a) => ({ value: a, label: humanize(a) })),
          ]}
        />
        <SelectField
          label="Result"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
          options={[
            { value: '', label: 'Any result' },
            { value: 'success', label: 'Success' },
            { value: 'failure', label: 'Failure' },
          ]}
        />
      </div>
      {q.isPending && <Spinner />}
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.data && (
        <>
          <DataTable caption="Audit log" columns={columns} rows={q.data.items} rowKey={(r) => r.id} emptyTitle="No audit entries" />
          <Pagination total={q.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}
    </>
  );
}

function AccessTab() {
  const [offset, setOffset] = useState(0);
  const q = useQuery({ queryKey: ['access', offset], queryFn: () => api.accessHistory({ limit: LIMIT, offset }) });
  const columns: Column<LoginEvent>[] = [
    { key: 'when', header: 'When', render: (e) => formatDateTime(e.created_at) },
    { key: 'email', header: 'E-mail', render: (e) => e.email },
    { key: 'result', header: 'Result', render: (e) => <StatusBadge status={e.success ? 'success' : 'failure'} /> },
    { key: 'reason', header: 'Reason', render: (e) => (e.failure_reason ? humanize(e.failure_reason) : '-') },
    { key: 'ip', header: 'IP', render: (e) => e.ip_address ?? '-', hideOnMobile: true },
    { key: 'ua', header: 'User agent', render: (e) => <span className="line-clamp-1 text-xs text-faint">{e.user_agent ?? '-'}</span>, hideOnMobile: true },
  ];
  if (q.isPending) return <Spinner />;
  if (q.isError) return <ErrorState error={q.error} />;
  return (
    <>
      <DataTable caption="Access history" columns={columns} rows={q.data.items} rowKey={(r) => r.id} emptyTitle="No sign-in events" />
      <Pagination total={q.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
    </>
  );
}

function ChangesTab() {
  const [offset, setOffset] = useState(0);
  const q = useQuery({ queryKey: ['all-changes', offset], queryFn: () => api.allChanges({ limit: LIMIT, offset }) });
  const columns: Column<ResourceChange>[] = [
    { key: 'when', header: 'When', render: (c) => formatDateTime(c.created_at) },
    { key: 'resource', header: 'Resource', render: (c) => <span className="font-medium text-ink">{c.resource_name}</span> },
    { key: 'type', header: 'Change', render: (c) => <StatusBadge status={c.change_type === 'deleted' ? 'deleted' : c.change_type === 'created' ? 'success' : 'acknowledged'} /> },
    { key: 'kind', header: 'Type', render: (c) => humanize(c.change_type) },
    { key: 'source', header: 'Source', render: (c) => c.source },
    { key: 'diff', header: 'Diff', render: (c) => <span className="line-clamp-2 break-all font-mono text-[11px] text-faint">{JSON.stringify(c.changes)}</span>, hideOnMobile: true },
  ];
  if (q.isPending) return <Spinner />;
  if (q.isError) return <ErrorState error={q.error} />;
  return (
    <>
      <DataTable caption="Resource change history" columns={columns} rows={q.data.items} rowKey={(r) => r.id} emptyTitle="No resource changes" />
      <Pagination total={q.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
    </>
  );
}

export function ActivityPage() {
  const { can } = useAuth();
  const tabs: { id: Tab; label: string; visible: boolean }[] = [
    { id: 'audit', label: 'Audit log', visible: can('audit:read') },
    { id: 'access', label: 'Access history', visible: true },
    { id: 'changes', label: 'Resource changes', visible: can('resources:read') },
  ];
  const visible = tabs.filter((t) => t.visible);
  const [tab, setTab] = useState<Tab>(visible[0].id);

  return (
    <>
      <PageHeader title="Activity logs" description="Audit trail, sign-in history and resource lifecycle changes" />
      <div role="tablist" aria-label="Activity views" className="mb-4 inline-flex rounded-xl border border-line bg-surface p-1">
        {visible.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={clsx(
              'rounded-lg px-3 py-1.5 text-sm font-medium',
              tab === t.id ? 'bg-orbit-400/15 text-orbit-200' : 'text-muted hover:text-ink',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <Card>
        {tab === 'audit' && <AuditTab />}
        {tab === 'access' && <AccessTab />}
        {tab === 'changes' && <ChangesTab />}
      </Card>
    </>
  );
}
