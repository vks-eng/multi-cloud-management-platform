import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Search, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, type ResourceFilters } from '../api/endpoints';
import type { Resource } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { AXIS_PROPS, TOOLTIP_PROPS } from '../components/charts';
import { Badge, ProviderBadge, StatusBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card, ErrorState, PageHeader, Spinner, errorMessage } from '../components/ui/Card';
import { DataTable, Pagination, type Column } from '../components/ui/DataTable';
import { SelectField, TextField } from '../components/ui/Field';
import { Modal } from '../components/ui/Modal';
import { formatCurrency, formatDateTime, humanize, resourceTypeLabel } from '../lib/format';

const PAGE_SIZE = 20;

function ResourceDetail({ resource, onClose }: { resource: Resource; onClose: () => void }) {
  const { can } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const changes = useQuery({ queryKey: ['resource-changes', resource.id], queryFn: () => api.resourceChanges(resource.id) });
  const metrics = useQuery({ queryKey: ['resource-metrics', resource.id], queryFn: () => api.resourceMetrics(resource.id, 24) });
  const decommission = useMutation({
    mutationFn: () => api.planDestroy(resource.id),
    onSuccess: (plan) => {
      void queryClient.invalidateQueries({ queryKey: ['provisioning'] });
      sessionStorage.setItem('cloudorbit.pendingPlan', JSON.stringify(plan));
      navigate('/infrastructure');
    },
  });
  const series = (metrics.data ?? []).map((m) => ({
    t: new Date(m.captured_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
    cpu: m.cpu_percent,
  }));

  return (
    <Modal open title={resource.name} onClose={onClose} wide>
      <div className="flex flex-wrap items-center gap-2">
        <ProviderBadge provider={resource.provider} />
        <Badge>{resourceTypeLabel(resource.resource_type)}</Badge>
        <StatusBadge status={resource.status} />
        {resource.managed_by_platform && <Badge tone="violet">managed by CloudOrbit</Badge>}
      </div>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs text-faint">External ID</dt>
          <dd className="break-all font-mono text-xs text-ink/90">{resource.external_id}</dd>
        </div>
        <div>
          <dt className="text-xs text-faint">Account · Region</dt>
          <dd className="text-ink/90">
            {resource.account_name} · {resource.region}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-faint">Est. monthly cost</dt>
          <dd className="text-ink/90">{formatCurrency(resource.monthly_cost_estimate)}</dd>
        </div>
        <div>
          <dt className="text-xs text-faint">First / last seen</dt>
          <dd className="text-ink/90">
            {formatDateTime(resource.first_seen_at)} / {formatDateTime(resource.last_seen_at)}
          </dd>
        </div>
      </dl>
      <h3 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wider text-faint">Attributes & tags</h3>
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(resource.attributes).map(([k, v]) => (
          <span key={k} className="rounded-md bg-elevated px-2 py-0.5 font-mono text-[11px] text-muted">
            {k}={String(v)}
          </span>
        ))}
        {Object.entries(resource.tags).map(([k, v]) => (
          <span key={`tag-${k}`} className="rounded-md bg-nebula-500/15 px-2 py-0.5 font-mono text-[11px] text-nebula-300">
            #{k}:{v}
          </span>
        ))}
      </div>
      {series.length > 1 && (
        <>
          <h3 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wider text-faint">CPU (24h)</h3>
          <div className="h-32">
            <ResponsiveContainer>
              <LineChart data={series}>
                <XAxis dataKey="t" {...AXIS_PROPS} minTickGap={30} />
                <YAxis {...AXIS_PROPS} domain={[0, 100]} width={30} />
                <Tooltip {...TOOLTIP_PROPS} />
                <Line dataKey="cpu" stroke="#22d3ee" dot={false} strokeWidth={2} name="CPU %" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
      <h3 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wider text-faint">Change history</h3>
      {changes.isPending ? (
        <Spinner />
      ) : (
        <ol className="space-y-2 border-l border-line pl-4">
          {(changes.data?.items ?? []).map((c) => (
            <li key={c.id} className="text-sm">
              <span className="font-medium text-ink">{humanize(c.change_type)}</span>{' '}
              <span className="text-muted">via {c.source}</span>{' '}
              <span className="text-xs text-faint">{formatDateTime(c.created_at)}</span>
              {c.changes && Object.keys(c.changes).length > 0 && (
                <p className="mt-0.5 break-all font-mono text-[11px] text-faint">{JSON.stringify(c.changes)}</p>
              )}
            </li>
          ))}
        </ol>
      )}
      {can('infra:plan') && !resource.deleted_at && (
        <div className="mt-5 flex items-center justify-between gap-3 rounded-xl border border-rose-500/25 bg-rose-500/5 p-3">
          <p className="text-xs text-muted">Create a Terraform destroy plan. Nothing is removed until you confirm it.</p>
          <Button
            size="sm"
            variant="danger"
            icon={<Trash2 className="h-3.5 w-3.5" />}
            loading={decommission.isPending}
            onClick={() => decommission.mutate()}
          >
            Plan decommission
          </Button>
        </div>
      )}
      {decommission.isError && <p className="mt-2 text-sm text-rose-300">{errorMessage(decommission.error)}</p>}
    </Modal>
  );
}

export function ResourcesPage() {
  const [filters, setFilters] = useState<ResourceFilters>({ sort: 'name', offset: 0, limit: PAGE_SIZE });
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Resource | null>(null);
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts });
  const query = useQuery({
    queryKey: ['resources', filters],
    queryFn: () => api.resources(filters),
    placeholderData: keepPreviousData,
  });

  const update = (patch: Partial<ResourceFilters>) => setFilters((f) => ({ ...f, ...patch, offset: 0 }));

  const columns: Column<Resource>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (r) => (
        <div>
          <p className="font-medium text-ink">{r.name}</p>
          <p className="max-w-[16rem] truncate font-mono text-[11px] text-faint">{r.external_id}</p>
        </div>
      ),
    },
    { key: 'provider', header: 'Provider', render: (r) => <ProviderBadge provider={r.provider} /> },
    { key: 'type', header: 'Type', render: (r) => resourceTypeLabel(r.resource_type), hideOnMobile: true },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} /> },
    { key: 'region', header: 'Region', render: (r) => r.region, hideOnMobile: true },
    { key: 'account', header: 'Account', render: (r) => r.account_name, hideOnMobile: true },
    {
      key: 'cost',
      header: 'Est. / month',
      render: (r) => <span className="tabular-nums">{formatCurrency(r.monthly_cost_estimate)}</span>,
      className: 'text-right',
    },
  ];

  return (
    <>
      <PageHeader title="Resource inventory" description="Compute and storage discovered across every connected account" />
      <Card>
        <form
          className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-6"
          onSubmit={(e) => {
            e.preventDefault();
            update({ search: search || undefined });
          }}
          role="search"
        >
          <div className="relative lg:col-span-2">
            <TextField label="Search" placeholder="Name or ID…" value={search} onChange={(e) => setSearch(e.target.value)} />
            <button type="submit" className="absolute bottom-2 right-2 text-faint hover:text-ink" aria-label="Apply search">
              <Search className="h-4 w-4" />
            </button>
          </div>
          <SelectField
            label="Provider"
            value={filters.provider ?? ''}
            onChange={(e) => update({ provider: e.target.value || undefined })}
            options={[
              { value: '', label: 'All providers' },
              { value: 'aws', label: 'AWS' },
              { value: 'azure', label: 'Azure' },
              { value: 'gcp', label: 'GCP' },
            ]}
          />
          <SelectField
            label="Type"
            value={filters.resource_type ?? ''}
            onChange={(e) => update({ resource_type: e.target.value || undefined })}
            options={[
              { value: '', label: 'All types' },
              ...['ec2_instance', 's3_bucket', 'azure_vm', 'azure_storage_account', 'gcp_compute_instance', 'gcp_bucket'].map(
                (t) => ({ value: t, label: resourceTypeLabel(t) }),
              ),
            ]}
          />
          <SelectField
            label="Status"
            value={filters.status ?? ''}
            onChange={(e) => update({ status: e.target.value || undefined })}
            options={[
              { value: '', label: 'Any status' },
              ...['running', 'stopped', 'available', 'provisioning', 'error'].map((s) => ({ value: s, label: humanize(s) })),
            ]}
          />
          <SelectField
            label="Account"
            value={filters.account_id ?? ''}
            onChange={(e) => update({ account_id: e.target.value || undefined })}
            options={[{ value: '', label: 'All accounts' }, ...(accounts.data ?? []).map((a) => ({ value: a.id, label: a.name }))]}
          />
        </form>
        {query.isPending && <Spinner label="Loading resources" />}
        {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
        {query.data && (
          <>
            <div className="mb-2 flex items-center justify-between text-xs text-muted">
              <span>{query.data.total} resources</span>
              <label className="flex items-center gap-2">
                Sort
                <select
                  className="rounded-md bg-canvas px-2 py-1 text-xs text-ink ring-1 ring-line"
                  value={filters.sort}
                  onChange={(e) => update({ sort: e.target.value })}
                >
                  <option value="name">Name A-Z</option>
                  <option value="-cost">Cost (high → low)</option>
                  <option value="-last_seen">Recently seen</option>
                </select>
              </label>
            </div>
            <DataTable
              caption="Cloud resources"
              columns={columns}
              rows={query.data.items}
              rowKey={(r) => r.id}
              onRowClick={setSelected}
              emptyTitle="No resources match these filters"
              emptyDescription="Adjust the filters or sync a cloud account."
            />
            <Pagination
              total={query.data.total}
              limit={PAGE_SIZE}
              offset={filters.offset ?? 0}
              onChange={(offset) => setFilters((f) => ({ ...f, offset }))}
            />
          </>
        )}
      </Card>
      {selected && <ResourceDetail resource={selected} onClose={() => setSelected(null)} />}
      <p className="mt-3 text-xs text-faint">
        <Button variant="ghost" size="sm" onClick={() => update({ include_deleted: !filters.include_deleted })}>
          {filters.include_deleted ? 'Hide' : 'Show'} deleted resources
        </Button>
      </p>
    </>
  );
}
