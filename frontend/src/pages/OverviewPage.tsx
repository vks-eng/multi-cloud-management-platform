import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Boxes, Cloud, Cpu, DollarSign, HardDrive, Power } from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../api/endpoints';
import { AXIS_PROPS, GRID_PROPS, LEGEND_PROPS, PROVIDER_COLORS, STATUS_COLORS, TOOLTIP_PROPS } from '../components/charts';
import { StatusBadge } from '../components/ui/Badge';
import { Card, EmptyState, ErrorState, PageHeader, Spinner, StatCard } from '../components/ui/Card';
import {
  formatCurrency,
  formatNumber,
  humanize,
  providerLabel,
  resourceTypeLabel,
  timeAgo,
} from '../lib/format';

export function OverviewPage() {
  const query = useQuery({ queryKey: ['overview'], queryFn: () => api.overview(24), refetchInterval: 60_000 });

  if (query.isPending) return <Spinner label="Loading dashboard" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  const data = query.data;

  if (data.total_resources === 0) {
    return (
      <>
        <PageHeader title="Overview" description="Your multi-cloud estate at a glance" />
        <EmptyState
          title="No resources yet"
          description="Connect an AWS account, Azure subscription or GCP project and run a sync to populate the dashboard."
          action={
            <Link to="/accounts" className="text-sm font-medium text-orbit-300 hover:text-orbit-200">
              Go to cloud accounts →
            </Link>
          }
        />
      </>
    );
  }

  const providerData = data.by_provider.map((p) => ({ name: providerLabel(p.key), key: p.key, value: p.count }));
  const usage = data.usage.series.map((p) => ({
    time: new Date(p.timestamp).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
    cpu: p.avg_cpu_percent,
    memory: p.avg_memory_percent,
  }));

  return (
    <>
      <PageHeader
        title="Overview"
        description={`Last sync ${timeAgo(data.accounts.last_sync_at)} · ${data.accounts.connected} connected account(s)`}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total resources" value={formatNumber(data.total_resources)} icon={<Boxes className="h-4 w-4" />} hint={`${data.storage_resources} storage · ${data.running_compute + data.stopped_compute} compute`} />
        <StatCard label="Running compute" value={formatNumber(data.running_compute)} icon={<Power className="h-4 w-4" />} tone="success" hint={`${data.stopped_compute} stopped`} />
        <StatCard label="Month-to-date cost" value={formatCurrency(data.month_to_date_cost)} icon={<DollarSign className="h-4 w-4" />} tone="violet" hint={`Run-rate ${formatCurrency(data.estimated_monthly_run_rate)}/mo`} />
        <StatCard
          label="Open alerts"
          value={formatNumber(data.open_alerts)}
          icon={<AlertTriangle className="h-4 w-4" />}
          tone={data.critical_alerts > 0 ? 'danger' : 'warning'}
          hint={`${data.critical_alerts} critical`}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Provider distribution" description="Active resources per cloud">
          <div className="h-56" data-testid="provider-chart">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={providerData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3} stroke="none">
                  {providerData.map((p) => (
                    <Cell key={p.key} fill={PROVIDER_COLORS[p.key] ?? '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_PROPS} />
                <Legend {...LEGEND_PROPS} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Utilisation (24h)" description="Average CPU and memory across running compute" className="lg:col-span-2">
          <div className="mb-3 flex flex-wrap gap-4 text-xs text-muted">
            <span className="inline-flex items-center gap-1.5"><Cpu className="h-3.5 w-3.5" /> Avg CPU {data.usage.avg_cpu_percent ?? '-'}%</span>
            <span>Avg memory {data.usage.avg_memory_percent ?? '-'}%</span>
            <span className="inline-flex items-center gap-1.5"><HardDrive className="h-3.5 w-3.5" /> {formatNumber(data.usage.total_storage_gb)} GB stored</span>
            <span>{data.usage.high_cpu_resources} high-CPU resource(s)</span>
          </div>
          <div className="h-48">
            <ResponsiveContainer>
              <AreaChart data={usage} margin={{ left: -20, right: 8 }}>
                <defs>
                  <linearGradient id="cpuFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="memFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#a78bfa" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid {...GRID_PROPS} />
                <XAxis dataKey="time" {...AXIS_PROPS} minTickGap={24} />
                <YAxis {...AXIS_PROPS} domain={[0, 100]} unit="%" />
                <Tooltip {...TOOLTIP_PROPS} />
                <Area type="monotone" dataKey="cpu" name="CPU %" stroke="#22d3ee" fill="url(#cpuFill)" strokeWidth={2} />
                <Area type="monotone" dataKey="memory" name="Memory %" stroke="#a78bfa" fill="url(#memFill)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Resource status">
          <div className="h-52">
            <ResponsiveContainer>
              <BarChart data={data.by_status} layout="vertical" margin={{ left: 10, right: 16 }}>
                <CartesianGrid {...GRID_PROPS} horizontal={false} vertical />
                <XAxis type="number" {...AXIS_PROPS} allowDecimals={false} />
                <YAxis type="category" dataKey="key" {...AXIS_PROPS} width={80} />
                <Tooltip {...TOOLTIP_PROPS} />
                <Bar dataKey="count" name="Resources" radius={[0, 4, 4, 0]}>
                  {data.by_status.map((s) => (
                    <Cell key={s.key} fill={STATUS_COLORS[s.key] ?? '#94a3b8'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="By resource type">
          <ul className="space-y-2.5">
            {data.by_type.map((t) => (
              <li key={t.key} className="flex items-center justify-between text-sm">
                <span className="text-ink/90">{resourceTypeLabel(t.key)}</span>
                <span className="tabular-nums text-muted">{t.count}</span>
              </li>
            ))}
          </ul>
          <h3 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wider text-faint">Top regions</h3>
          <div className="flex flex-wrap gap-1.5">
            {data.by_region.map((r) => (
              <span key={r.key} className="rounded-md bg-elevated px-2 py-0.5 text-xs text-muted">
                {r.key} · {r.count}
              </span>
            ))}
          </div>
        </Card>

        <Card
          title="Operational alerts"
          actions={
            <Link to="/monitoring" className="text-xs font-medium text-orbit-300 hover:text-orbit-200">
              View all
            </Link>
          }
        >
          {data.recent_alerts.length === 0 ? (
            <p className="text-sm text-muted">No open alerts. All systems nominal.</p>
          ) : (
            <ul className="space-y-3">
              {data.recent_alerts.map((a) => (
                <li key={a.id} className="flex items-start gap-2">
                  <StatusBadge status={a.severity} />
                  <div className="min-w-0">
                    <p className="truncate text-sm text-ink">{a.title}</p>
                    <p className="text-xs text-faint">{timeAgo(a.created_at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Recent activity" className="mt-6" description="Latest audited actions">
        <ul className="divide-y divide-line/60">
          {data.recent_activity.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span className="flex items-center gap-2">
                <Cloud className="h-3.5 w-3.5 text-faint" aria-hidden />
                <span className="font-medium text-ink">{humanize(a.action)}</span>
                <span className="text-muted">{a.actor_email ?? 'system'}</span>
              </span>
              <span className="flex items-center gap-2">
                <StatusBadge status={a.status} />
                <span className="text-xs text-faint">{timeAgo(a.created_at)}</span>
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
