import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, TrendingDown, TrendingUp } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import {
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
import type { Budget, BudgetCreate, Provider } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { AXIS_PROPS, GRID_PROPS, LEGEND_PROPS, PROVIDER_COLORS, SERIES_COLORS, TOOLTIP_PROPS } from '../components/charts';
import { ProviderBadge, StatusBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card, ErrorState, PageHeader, Spinner, StatCard, errorMessage } from '../components/ui/Card';
import { DataTable, type Column } from '../components/ui/DataTable';
import { SelectField, TextField } from '../components/ui/Field';
import { Modal } from '../components/ui/Modal';
import { formatCurrency, formatMonth, formatPercent, providerLabel, toNumber } from '../lib/format';

function BudgetBar({ budget }: { budget: Budget }) {
  const pct = Math.min(100, budget.utilization_percent);
  const color = budget.utilization_percent >= 100 ? 'bg-rose-400' : budget.utilization_percent >= budget.alert_threshold_percent ? 'bg-amber-400' : 'bg-orbit-400';
  return (
    <div>
      <div className="flex justify-between text-xs text-muted">
        <span>
          {formatCurrency(budget.current_spend)} of {formatCurrency(budget.monthly_limit)}
        </span>
        <span className="tabular-nums">{budget.utilization_percent.toFixed(1)}%</span>
      </div>
      <div
        className="mt-1 h-2 rounded-full bg-elevated"
        role="progressbar"
        aria-label={`${budget.name} utilisation`}
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function BudgetModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: '', provider: '', monthly_limit: '', alert_threshold_percent: '80' });
  const create = useMutation({
    mutationFn: (data: BudgetCreate) => api.createBudget(data),
    onSuccess: () => {
      ['budgets', 'cost-alerts', 'overview'].forEach((k) => void queryClient.invalidateQueries({ queryKey: [k] }));
      onClose();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate({
      name: form.name,
      provider: (form.provider || null) as Provider | null,
      monthly_limit: form.monthly_limit,
      alert_threshold_percent: Number(form.alert_threshold_percent),
    });
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New monthly budget"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="budget-form" loading={create.isPending}>
            Create budget
          </Button>
        </>
      }
    >
      <form id="budget-form" onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        <TextField label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="sm:col-span-2" />
        <SelectField
          label="Scope"
          value={form.provider}
          onChange={(e) => setForm({ ...form, provider: e.target.value })}
          options={[
            { value: '', label: 'All providers' },
            { value: 'aws', label: 'AWS only' },
            { value: 'azure', label: 'Azure only' },
            { value: 'gcp', label: 'GCP only' },
          ]}
        />
        <TextField label="Monthly limit (USD)" type="number" min="1" step="0.01" value={form.monthly_limit} onChange={(e) => setForm({ ...form, monthly_limit: e.target.value })} />
        <TextField
          label="Alert threshold (%)"
          type="number"
          min="1"
          max="100"
          value={form.alert_threshold_percent}
          onChange={(e) => setForm({ ...form, alert_threshold_percent: e.target.value })}
          hint="An alert is also raised at 100%."
        />
        {create.isError && (
          <p role="alert" className="text-sm text-rose-300 sm:col-span-2">
            {errorMessage(create.error)}
          </p>
        )}
      </form>
    </Modal>
  );
}

export function CostsPage() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const summary = useQuery({ queryKey: ['cost-summary'], queryFn: api.costSummary });
  const trends = useQuery({ queryKey: ['cost-trends'], queryFn: () => api.costTrends(6) });
  const services = useQuery({ queryKey: ['cost-services'], queryFn: api.costByService });
  const budgets = useQuery({ queryKey: ['budgets'], queryFn: api.budgets });
  const alerts = useQuery({ queryKey: ['cost-alerts'], queryFn: api.costAlerts });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteBudget(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['budgets'] }),
  });

  if (summary.isPending) return <Spinner label="Loading cost data" />;
  if (summary.isError) return <ErrorState error={summary.error} onRetry={() => summary.refetch()} />;
  const s = summary.data;
  const trendData = (trends.data ?? []).map((p) => ({
    month: formatMonth(p.month),
    aws: toNumber(p.aws),
    azure: toNumber(p.azure),
    gcp: toNumber(p.gcp),
  }));
  const providerShare = s.by_provider.filter((p) => toNumber(p.current_month) > 0).map((p) => ({ key: p.provider, name: providerLabel(p.provider), value: toNumber(p.current_month) }));
  const topServices = (services.data ?? []).slice(0, 8).map((x) => ({ ...x, label: `${x.service} (${providerLabel(x.provider)})`, value: toNumber(x.amount) }));

  const alertColumns: Column<NonNullable<typeof alerts.data>['items'][number]>[] = [
    { key: 'budget', header: 'Budget', render: (a) => a.budget_name },
    { key: 'threshold', header: 'Threshold', render: (a) => `${a.threshold_percent}%` },
    { key: 'actual', header: 'Spend', render: (a) => `${formatCurrency(a.actual_amount)} / ${formatCurrency(a.budget_limit)}` },
    { key: 'severity', header: 'Severity', render: (a) => <StatusBadge status={a.severity} /> },
    { key: 'month', header: 'Month', render: (a) => formatMonth(a.period_month), hideOnMobile: true },
  ];

  const ChangeIcon = (s.change_percent ?? 0) >= 0 ? TrendingUp : TrendingDown;

  return (
    <>
      <PageHeader
        title="Cost analytics"
        description="Spend by provider and service, monthly trends and budget guardrails"
        actions={
          can('budgets:write') && (
            <Button icon={<Plus className="h-4 w-4" />} onClick={() => setOpen(true)}>
              New budget
            </Button>
          )
        }
      />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Month to date" value={formatCurrency(s.current_month)} tone="violet" />
        <StatCard label="Forecast (month)" value={formatCurrency(s.forecast_current_month)} hint={<span className="inline-flex items-center gap-1"><ChangeIcon className="h-3 w-3" aria-hidden />{formatPercent(s.change_percent)} vs last month</span>} />
        <StatCard label="Last month" value={formatCurrency(s.previous_month)} />
        <StatCard label="Active budgets" value={budgets.data?.filter((b) => b.is_active).length ?? '-'} tone="warning" hint={`${alerts.data?.total ?? 0} cost alert(s)`} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Monthly spend by provider" description="Last 6 months (current month is month-to-date)" className="lg:col-span-2">
          <div className="h-64" data-testid="trend-chart">
            <ResponsiveContainer>
              <BarChart data={trendData} margin={{ left: 0, right: 8 }}>
                <CartesianGrid {...GRID_PROPS} />
                <XAxis dataKey="month" {...AXIS_PROPS} />
                <YAxis {...AXIS_PROPS} tickFormatter={(v: number) => formatCurrency(v, true)} width={70} />
                <Tooltip {...TOOLTIP_PROPS} formatter={(v: number) => formatCurrency(v)} />
                <Legend {...LEGEND_PROPS} />
                {(['aws', 'azure', 'gcp'] as const).map((p) => (
                  <Bar key={p} dataKey={p} name={providerLabel(p)} stackId="spend" fill={PROVIDER_COLORS[p]} radius={p === 'gcp' ? [4, 4, 0, 0] : undefined} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Provider comparison" description="This month">
          <div className="h-44">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={providerShare} dataKey="value" nameKey="name" innerRadius={45} outerRadius={70} paddingAngle={3} stroke="none">
                  {providerShare.map((p) => (
                    <Cell key={p.key} fill={PROVIDER_COLORS[p.key]} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_PROPS} formatter={(v: number) => formatCurrency(v)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="mt-2 space-y-1.5 text-sm">
            {s.by_provider.map((p) => (
              <li key={p.provider} className="flex items-center justify-between">
                <ProviderBadge provider={p.provider} />
                <span className="tabular-nums text-ink">{formatCurrency(p.current_month)}</span>
                <span className={`w-16 text-right text-xs tabular-nums ${(p.change_percent ?? 0) > 0 ? 'text-rose-300' : 'text-emerald-300'}`}>
                  {formatPercent(p.change_percent)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Top services this month">
          <div className="h-72">
            <ResponsiveContainer>
              <BarChart data={topServices} layout="vertical" margin={{ left: 10, right: 16 }}>
                <CartesianGrid {...GRID_PROPS} horizontal={false} vertical />
                <XAxis type="number" {...AXIS_PROPS} tickFormatter={(v: number) => formatCurrency(v, true)} />
                <YAxis type="category" dataKey="label" {...AXIS_PROPS} width={170} />
                <Tooltip {...TOOLTIP_PROPS} formatter={(v: number) => formatCurrency(v)} />
                <Bar dataKey="value" name="Spend" radius={[0, 4, 4, 0]}>
                  {topServices.map((x, i) => (
                    <Cell key={x.label} fill={PROVIDER_COLORS[x.provider] ?? SERIES_COLORS[i % SERIES_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Budgets" description="Month-to-date spend against monthly limits">
          {budgets.isPending && <Spinner />}
          <ul className="space-y-4">
            {(budgets.data ?? []).map((b) => (
              <li key={b.id}>
                <div className="mb-1 flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-ink">
                    {b.name} <span className="text-xs text-faint">· {b.provider ? providerLabel(b.provider) : 'all providers'} · alert at {b.alert_threshold_percent}%</span>
                  </p>
                  {can('budgets:write') && (
                    <button type="button" className="rounded p-1 text-faint hover:bg-elevated hover:text-rose-300" aria-label={`Delete budget ${b.name}`} onClick={() => remove.mutate(b.id)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
                <BudgetBar budget={b} />
              </li>
            ))}
            {budgets.data?.length === 0 && <li className="text-sm text-muted">No budgets defined.</li>}
          </ul>
        </Card>
      </div>

      <Card title="Cost alerts" className="mt-6" description="Raised when a budget crosses its threshold or 100%">
        {alerts.data && <DataTable caption="Cost alerts" columns={alertColumns} rows={alerts.data.items} rowKey={(a) => a.id} emptyTitle="No cost alerts" />}
      </Card>
      <BudgetModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
