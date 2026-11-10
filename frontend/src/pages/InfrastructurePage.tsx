import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, FileCode2, Play, Rocket, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { ApiError } from '../api/client';
import { api } from '../api/endpoints';
import type { ProvisioningPlanned, ProvisioningRequest, Template, TemplateParam } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { Badge, ProviderBadge, StatusBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card, CodeBlock, EmptyState, ErrorState, PageHeader, Spinner, errorMessage } from '../components/ui/Card';
import { DataTable, type Column } from '../components/ui/DataTable';
import { SelectField, TextField } from '../components/ui/Field';
import { Modal } from '../components/ui/Modal';
import { formatDateTime } from '../lib/format';

type Values = Record<string, string | boolean | number>;

function defaults(template: Template): Values {
  const values: Values = {};
  template.params.forEach((p) => {
    if (p.default !== null && p.default !== undefined) values[p.key] = p.default as string | boolean | number;
    else values[p.key] = p.type === 'boolean' ? false : '';
  });
  return values;
}

function ParamInput({ param, value, error, onChange }: { param: TemplateParam; value: Values[string]; error?: string; onChange: (v: Values[string]) => void }) {
  if (param.type === 'enum') {
    return (
      <SelectField
        label={param.label}
        value={String(value)}
        error={error}
        onChange={(e) => onChange(e.target.value)}
        options={param.options.map((o) => ({ value: o, label: o }))}
      />
    );
  }
  if (param.type === 'boolean') {
    return (
      <label className="flex items-center gap-2 self-end pb-2 text-sm text-ink">
        <input type="checkbox" className="h-4 w-4 rounded border-line bg-canvas accent-orbit-400" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
        {param.label}
      </label>
    );
  }
  return (
    <TextField
      label={`${param.label}${param.required ? '' : ' (optional)'}`}
      type={param.type === 'integer' ? 'number' : 'text'}
      value={String(value ?? '')}
      min={param.minimum ?? undefined}
      max={param.maximum ?? undefined}
      hint={param.description || undefined}
      error={error}
      onChange={(e) => onChange(param.type === 'integer' ? Number(e.target.value) : e.target.value)}
    />
  );
}

export function ConfirmPanel({ plan, onDone }: { plan: ProvisioningPlanned; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [typed, setTyped] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const apply = useMutation({
    mutationFn: () => api.apply(plan.id, plan.confirmation_token, typed),
    onSuccess: () => {
      ['provisioning', 'resources', 'overview', 'accounts'].forEach((k) => void queryClient.invalidateQueries({ queryKey: [k] }));
    },
  });
  const cancel = useMutation({
    mutationFn: () => api.cancel(plan.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['provisioning'] });
      onDone();
    },
  });
  const destroying = plan.action === 'destroy';
  const result = apply.data;

  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          {destroying ? 'Destroy plan' : 'Execution plan'} · <span className="font-mono">{plan.resource_name}</span>
        </span>
      }
      description={`${plan.account_name ?? ''} · template ${plan.template_key}`}
      actions={plan.plan_is_mock ? <Badge tone="amber">MOCK PLAN</Badge> : <Badge tone="green">terraform plan</Badge>}
      className="border-orbit-400/30"
    >
      <div className="mb-3 flex flex-wrap gap-2 text-xs">
        <Badge tone="green">+{plan.plan_summary.add ?? 0} to add</Badge>
        <Badge tone="blue">~{plan.plan_summary.change ?? 0} to change</Badge>
        <Badge tone="red">-{plan.plan_summary.destroy ?? 0} to destroy</Badge>
      </div>
      <CodeBlock label="Terraform plan output">{plan.plan_output}</CodeBlock>

      {result ? (
        <div role="status" className="mt-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
          <p className="font-semibold">Request {result.status}</p>
          {result.apply_output && <pre className="mt-1 whitespace-pre-wrap font-mono text-xs">{result.apply_output}</pre>}
          {result.error && <p className="mt-1">{result.error}</p>}
          <Button size="sm" variant="secondary" className="mt-3" onClick={onDone}>
            Done
          </Button>
        </div>
      ) : (
        <form
          className="mt-4 space-y-3 rounded-xl border border-amber-500/25 bg-amber-500/5 p-4"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            apply.mutate();
          }}
        >
          <p className="flex items-start gap-2 text-sm text-amber-100">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            Nothing has been applied yet. Review the plan, then type the resource name to confirm.
            The one-time confirmation token expires {formatDateTime(plan.confirmation_expires_at)}.
          </p>
          <TextField
            label={`Type "${plan.resource_name}" to confirm`}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            autoComplete="off"
          />
          <label className="flex items-center gap-2 text-sm text-ink">
            <input type="checkbox" className="h-4 w-4 accent-orbit-400" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} />
            I have reviewed this plan and want to {destroying ? 'destroy' : 'create'} these resources
          </label>
          {apply.isError && (
            <p role="alert" className="text-sm text-rose-300">
              {errorMessage(apply.error)}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              type="submit"
              variant={destroying ? 'danger' : 'primary'}
              icon={<Rocket className="h-4 w-4" />}
              disabled={typed !== plan.resource_name || !acknowledged}
              loading={apply.isPending}
            >
              Confirm & apply
            </Button>
            <Button variant="secondary" icon={<XCircle className="h-4 w-4" />} loading={cancel.isPending} onClick={() => cancel.mutate()}>
              Cancel plan
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}

function PlanForm({ templates, onPlanned }: { templates: Template[]; onPlanned: (p: ProvisioningPlanned) => void }) {
  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.accounts });
  const [templateKey, setTemplateKey] = useState(templates[0]?.key ?? '');
  const template = templates.find((t) => t.key === templateKey) ?? templates[0];
  const eligible = useMemo(() => (accounts.data ?? []).filter((a) => a.provider === template?.provider), [accounts.data, template]);
  const [accountId, setAccountId] = useState('');
  const [values, setValues] = useState<Values>(() => (template ? defaults(template) : {}));
  const [preview, setPreview] = useState<string | null>(null);

  useEffect(() => {
    if (template) setValues(defaults(template));
    setPreview(null);
  }, [template]);
  useEffect(() => {
    if (!eligible.some((a) => a.id === accountId)) setAccountId(eligible[0]?.id ?? '');
  }, [eligible, accountId]);

  const payload = () => ({ ...values });
  const previewMutation = useMutation({
    mutationFn: () => api.previewTemplate(template.key, accountId, payload()),
    onSuccess: (r) => setPreview(r.hcl),
  });
  const plan = useMutation({
    mutationFn: () => api.plan({ cloud_account_id: accountId, template_key: template.key, parameters: payload() }),
    onSuccess: onPlanned,
  });
  const err = (plan.error ?? previewMutation.error) as unknown;
  const fieldErrors = err instanceof ApiError ? err.fieldErrors : {};

  if (!template) return <EmptyState title="No templates available" />;
  return (
    <Card title="New provisioning request" description="Templates render hardened Terraform HCL. Planning never changes anything.">
      <div className="grid gap-3 md:grid-cols-2">
        <SelectField
          label="Template"
          value={template.key}
          onChange={(e) => setTemplateKey(e.target.value)}
          options={templates.map((t) => ({ value: t.key, label: `${t.title} (${t.provider.toUpperCase()})` }))}
        />
        <SelectField
          label="Target account"
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
          options={eligible.length ? eligible.map((a) => ({ value: a.id, label: a.name })) : [{ value: '', label: `No ${template.provider.toUpperCase()} accounts` }]}
        />
      </div>
      <p className="mt-3 text-xs text-muted">
        {template.description} · Resources: <span className="font-mono">{template.terraform_resources.join(', ')}</span> · Est. {template.estimated_monthly_cost}
      </p>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {template.params.map((p) => (
          <ParamInput key={p.key} param={p} value={values[p.key]} error={fieldErrors[p.key]} onChange={(v) => setValues((s) => ({ ...s, [p.key]: v }))} />
        ))}
      </div>
      {err !== null && err !== undefined && (
        <p role="alert" className="mt-3 text-sm text-rose-300">
          {errorMessage(err)}
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="secondary" icon={<FileCode2 className="h-4 w-4" />} disabled={!accountId} loading={previewMutation.isPending} onClick={() => previewMutation.mutate()}>
          Preview HCL
        </Button>
        <Button icon={<Play className="h-4 w-4" />} disabled={!accountId} loading={plan.isPending} onClick={() => plan.mutate()}>
          Generate plan
        </Button>
      </div>
      {preview && (
        <div className="mt-4">
          <CodeBlock label="Rendered Terraform configuration">{preview}</CodeBlock>
        </div>
      )}
    </Card>
  );
}

export function InfrastructurePage() {
  const { can } = useAuth();
  const [plan, setPlan] = useState<ProvisioningPlanned | null>(() => {
    try {
      const raw = sessionStorage.getItem('cloudorbit.pendingPlan');
      if (raw) {
        sessionStorage.removeItem('cloudorbit.pendingPlan');
        return JSON.parse(raw) as ProvisioningPlanned;
      }
    } catch {
      /* ignore */
    }
    return null;
  });
  const [selected, setSelected] = useState<ProvisioningRequest | null>(null);
  const templates = useQuery({ queryKey: ['templates'], queryFn: api.templates });
  const tf = useQuery({ queryKey: ['terraform-status'], queryFn: api.terraformStatus });
  const history = useQuery({ queryKey: ['provisioning'], queryFn: () => api.provisioning({ limit: 50 }) });

  const columns: Column<ProvisioningRequest>[] = [
    { key: 'name', header: 'Resource', render: (r) => <span className="font-mono text-ink">{r.resource_name}</span> },
    { key: 'action', header: 'Action', render: (r) => <Badge tone={r.action === 'destroy' ? 'red' : 'violet'}>{r.action}</Badge> },
    { key: 'provider', header: 'Provider', render: (r) => <ProviderBadge provider={r.provider} />, hideOnMobile: true },
    { key: 'template', header: 'Template', render: (r) => r.template_key, hideOnMobile: true },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} /> },
    { key: 'mock', header: 'Plan', render: (r) => (r.plan_is_mock ? <Badge tone="amber">mock</Badge> : <Badge tone="green">terraform</Badge>), hideOnMobile: true },
    { key: 'created', header: 'Requested', render: (r) => formatDateTime(r.created_at), hideOnMobile: true },
  ];

  return (
    <>
      <PageHeader
        title="Infrastructure"
        description="Terraform templates → plan → explicit confirmation → apply. Every step is audited."
        actions={
          tf.data && (
            <Badge tone={tf.data.mock_reason ? 'amber' : 'green'}>
              {tf.data.mock_reason ? `Mock plans: ${tf.data.mock_reason}` : `terraform at ${tf.data.binary_path}`}
            </Badge>
          )
        }
      />
      <div className="space-y-6">
        {plan && <ConfirmPanel plan={plan} onDone={() => setPlan(null)} />}
        {!plan && can('infra:plan') && templates.data && <PlanForm templates={templates.data} onPlanned={setPlan} />}
        {templates.isPending && <Spinner label="Loading templates" />}
        {templates.isError && <ErrorState error={templates.error} />}

        <Card title="Provisioning history" description="Every plan, confirmation and apply, newest first">
          {history.isPending && <Spinner />}
          {history.isError && <ErrorState error={history.error} onRetry={() => history.refetch()} />}
          {history.data && (
            <DataTable
              caption="Provisioning requests"
              columns={columns}
              rows={history.data.items}
              rowKey={(r) => r.id}
              onRowClick={setSelected}
              emptyTitle="No provisioning requests yet"
            />
          )}
        </Card>
      </div>
      {selected && (
        <Modal open wide title={`${selected.action} · ${selected.resource_name}`} onClose={() => setSelected(null)}>
          <div className="mb-3 flex flex-wrap gap-2">
            <StatusBadge status={selected.status} />
            {selected.plan_is_mock && <Badge tone="amber">MOCK PLAN</Badge>}
          </div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-faint">Rendered HCL</h3>
          <CodeBlock label="Rendered HCL">{selected.rendered_hcl}</CodeBlock>
          <h3 className="mb-1 mt-4 text-xs font-semibold uppercase tracking-wider text-faint">Plan output</h3>
          <CodeBlock label="Plan output">{selected.plan_output}</CodeBlock>
          {selected.apply_output && (
            <>
              <h3 className="mb-1 mt-4 text-xs font-semibold uppercase tracking-wider text-faint">Apply output</h3>
              <CodeBlock label="Apply output">{selected.apply_output}</CodeBlock>
            </>
          )}
        </Modal>
      )}
    </>
  );
}
