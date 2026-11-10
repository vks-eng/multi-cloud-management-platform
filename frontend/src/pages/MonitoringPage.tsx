import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api/endpoints';
import type { Alert } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { AXIS_PROPS, GRID_PROPS, TOOLTIP_PROPS } from '../components/charts';
import { Badge, StatusBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card, ErrorState, PageHeader, Spinner, StatCard } from '../components/ui/Card';
import { DataTable, Pagination, type Column } from '../components/ui/DataTable';
import { SelectField } from '../components/ui/Field';
import { formatNumber, timeAgo } from '../lib/format';

const LIMIT = 15;

export function MonitoringPage() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState('open');
  const [severity, setSeverity] = useState('');
  const [offset, setOffset] = useState(0);
  const overview = useQuery({ queryKey: ['overview'], queryFn: () => api.overview(24) });
  const alerts = useQuery({
    queryKey: ['alerts', status, severity, offset],
    queryFn: () => api.alerts({ status: status || undefined, severity: severity || undefined, limit: LIMIT, offset }),
  });
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['alerts'] });
    void queryClient.invalidateQueries({ queryKey: ['overview'] });
  };
  const ack = useMutation({ mutationFn: (id: string) => api.acknowledgeAlert(id), onSuccess: invalidate });
  const resolve = useMutation({ mutationFn: (id: string) => api.resolveAlert(id), onSuccess: invalidate });

  const columns: Column<Alert>[] = [
    { key: 'severity', header: 'Severity', render: (a) => <StatusBadge status={a.severity} /> },
    {
      key: 'title',
      header: 'Alert',
      render: (a) => (
        <div>
          <p className="font-medium text-ink">{a.title}</p>
          <p className="text-xs text-muted">{a.message}</p>
        </div>
      ),
    },
    { key: 'category', header: 'Category', render: (a) => <Badge>{a.category}</Badge>, hideOnMobile: true },
    { key: 'status', header: 'Status', render: (a) => <StatusBadge status={a.status} /> },
    { key: 'age', header: 'Raised', render: (a) => timeAgo(a.created_at), hideOnMobile: true },
    {
      key: 'actions',
      header: '',
      render: (a) =>
        can('alerts:manage') && a.status !== 'resolved' ? (
          <div className="flex justify-end gap-1.5">
            {a.status === 'open' && (
              <Button size="sm" variant="secondary" onClick={() => ack.mutate(a.id)}>
                Acknowledge
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => resolve.mutate(a.id)}>
              Resolve
            </Button>
          </div>
        ) : null,
      className: 'text-right',
    },
  ];

  const o = overview.data;
  const series = (o?.usage.series ?? []).map((p) => ({
    time: new Date(p.timestamp).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
    in: p.network_in_mb,
    out: p.network_out_mb,
  }));

  return (
    <>
      <PageHeader title="Monitoring" description="Operational health, usage metrics and alerts across all clouds" />
      {o && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label="Accounts connected" value={`${o.accounts.connected}/${o.accounts.connected + o.accounts.error + o.accounts.pending}`} tone={o.accounts.error ? 'danger' : 'success'} hint={`${o.accounts.error} with errors`} />
          <StatCard label="Avg CPU" value={o.usage.avg_cpu_percent !== null ? `${o.usage.avg_cpu_percent}%` : '-'} hint={`${o.usage.high_cpu_resources} above 85%`} />
          <StatCard label="Avg memory" value={o.usage.avg_memory_percent !== null ? `${o.usage.avg_memory_percent}%` : '-'} tone="violet" />
          <StatCard label="Critical alerts" value={formatNumber(o.critical_alerts)} tone={o.critical_alerts ? 'danger' : 'success'} hint={`${o.open_alerts} open in total`} />
        </div>
      )}
      <Card title="Network throughput (24h)" description="Total MB in/out per hour across running compute" className="mt-6">
        {overview.isPending ? (
          <Spinner />
        ) : (
          <div className="h-56">
            <ResponsiveContainer>
              <LineChart data={series} margin={{ left: -10, right: 8 }}>
                <CartesianGrid {...GRID_PROPS} />
                <XAxis dataKey="time" {...AXIS_PROPS} minTickGap={24} />
                <YAxis {...AXIS_PROPS} />
                <Tooltip {...TOOLTIP_PROPS} />
                <Line dataKey="in" name="Network in (MB)" stroke="#22d3ee" dot={false} strokeWidth={2} />
                <Line dataKey="out" name="Network out (MB)" stroke="#a78bfa" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
      <Card
        title="Alerts"
        className="mt-6"
        actions={
          <div className="flex gap-2">
            <SelectField
              label="Status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setOffset(0);
              }}
              options={[
                { value: 'open', label: 'Open' },
                { value: 'acknowledged', label: 'Acknowledged' },
                { value: 'resolved', label: 'Resolved' },
                { value: '', label: 'All' },
              ]}
            />
            <SelectField
              label="Severity"
              value={severity}
              onChange={(e) => {
                setSeverity(e.target.value);
                setOffset(0);
              }}
              options={[
                { value: '', label: 'Any' },
                { value: 'critical', label: 'Critical' },
                { value: 'warning', label: 'Warning' },
                { value: 'info', label: 'Info' },
              ]}
            />
          </div>
        }
      >
        {alerts.isPending && <Spinner label="Loading alerts" />}
        {alerts.isError && <ErrorState error={alerts.error} onRetry={() => alerts.refetch()} />}
        {alerts.data && (
          <>
            <DataTable caption="Operational alerts" columns={columns} rows={alerts.data.items} rowKey={(a) => a.id} emptyTitle="No alerts" emptyDescription="Nothing matches these filters." />
            <Pagination total={alerts.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
    </>
  );
}
