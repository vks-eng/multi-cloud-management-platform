import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { KeyRound, Plus, RefreshCw, ShieldCheck, Trash2 } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { ApiError } from '../api/client';
import { api } from '../api/endpoints';
import type { CloudAccount, CloudAccountCreate, Provider } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { ProviderBadge, StatusBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card, EmptyState, ErrorState, PageHeader, Spinner, errorMessage } from '../components/ui/Card';
import { SelectField, TextField } from '../components/ui/Field';
import { Modal } from '../components/ui/Modal';
import { timeAgo } from '../lib/format';

const CREDENTIAL_FIELDS: Record<Provider, { key: string; label: string; secret?: boolean; multiline?: boolean }[]> = {
  aws: [
    { key: 'access_key_id', label: 'Access key ID' },
    { key: 'secret_access_key', label: 'Secret access key', secret: true },
    { key: 'session_token', label: 'Session token (optional)', secret: true },
  ],
  azure: [
    { key: 'tenant_id', label: 'Tenant ID' },
    { key: 'client_id', label: 'Client (application) ID' },
    { key: 'client_secret', label: 'Client secret', secret: true },
  ],
  gcp: [{ key: 'service_account_json', label: 'Service account key (JSON)', secret: true, multiline: true }],
};

const EXTERNAL_ID_LABEL: Record<Provider, string> = {
  aws: 'AWS account ID (12 digits)',
  azure: 'Subscription ID (GUID)',
  gcp: 'Project ID',
};

const DEFAULT_REGION: Record<Provider, string> = { aws: 'us-east-1', azure: 'westeurope', gcp: 'us-central1' };

function AddAccountModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState<Provider>('aws');
  const [form, setForm] = useState({ name: '', external_id: '', default_region: DEFAULT_REGION.aws, description: '' });
  const [creds, setCreds] = useState<Record<string, string>>({});
  const mutation = useMutation({
    mutationFn: (data: CloudAccountCreate) => api.createAccount(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
      setCreds({});
      setForm({ name: '', external_id: '', default_region: DEFAULT_REGION[provider], description: '' });
      onClose();
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const credentials = Object.fromEntries(Object.entries(creds).filter(([, v]) => v.trim() !== ''));
    mutation.mutate({ ...form, provider, credentials });
  };
  const fieldErrors = mutation.error instanceof ApiError ? mutation.error.fieldErrors : {};

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Connect a cloud account"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="add-account" loading={mutation.isPending}>
            Save account
          </Button>
        </>
      }
    >
      <form id="add-account" onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        <SelectField
          label="Provider"
          value={provider}
          onChange={(e) => {
            const p = e.target.value as Provider;
            setProvider(p);
            setCreds({});
            setForm((f) => ({ ...f, default_region: DEFAULT_REGION[p] }));
          }}
          options={[
            { value: 'aws', label: 'AWS account' },
            { value: 'azure', label: 'Azure subscription' },
            { value: 'gcp', label: 'GCP project' },
          ]}
        />
        <TextField label="Display name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        <TextField
          label={EXTERNAL_ID_LABEL[provider]}
          value={form.external_id}
          onChange={(e) => setForm({ ...form, external_id: e.target.value })}
          required
        />
        <TextField
          label="Default region"
          value={form.default_region}
          onChange={(e) => setForm({ ...form, default_region: e.target.value })}
        />
        <TextField
          label="Description"
          className="sm:col-span-2"
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
        <fieldset className="rounded-xl border border-line p-3 sm:col-span-2">
          <legend className="flex items-center gap-1.5 px-1 text-xs font-semibold text-muted">
            <KeyRound className="h-3.5 w-3.5" aria-hidden /> Credentials (encrypted at rest, never shown again)
          </legend>
          <div className="grid gap-3">
            {CREDENTIAL_FIELDS[provider].map((f) =>
              f.multiline ? (
                <div key={f.key}>
                  <label htmlFor={`cred-${f.key}`} className="block text-xs font-medium text-muted">
                    {f.label}
                  </label>
                  <textarea
                    id={`cred-${f.key}`}
                    rows={4}
                    className="mt-1 block w-full rounded-lg border-0 bg-canvas px-3 py-2 font-mono text-xs text-ink ring-1 ring-inset ring-line focus:ring-2 focus:ring-orbit-400"
                    value={creds[f.key] ?? ''}
                    onChange={(e) => setCreds({ ...creds, [f.key]: e.target.value })}
                  />
                </div>
              ) : (
                <TextField
                  key={f.key}
                  label={f.label}
                  type={f.secret ? 'password' : 'text'}
                  autoComplete="off"
                  value={creds[f.key] ?? ''}
                  error={fieldErrors[f.key]}
                  onChange={(e) => setCreds({ ...creds, [f.key]: e.target.value })}
                />
              ),
            )}
          </div>
        </fieldset>
        {mutation.isError && (
          <p role="alert" className="text-sm text-rose-300 sm:col-span-2">
            {errorMessage(mutation.error)}
            {Object.keys(fieldErrors).length > 0 && ` (${Object.keys(fieldErrors).join(', ')})`}
          </p>
        )}
      </form>
    </Modal>
  );
}

function AccountCard({ account }: { account: CloudAccount }) {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['accounts'] });
    void queryClient.invalidateQueries({ queryKey: ['overview'] });
    void queryClient.invalidateQueries({ queryKey: ['resources'] });
  };
  const validate = useMutation({
    mutationFn: () => api.validateAccount(account.id),
    onSuccess: (r) => {
      setMessage(`${r.ok ? 'Connected' : 'Failed'}: ${r.message}${r.identity ? ` (${r.identity})` : ''}`);
      refresh();
    },
    onError: (e) => setMessage(errorMessage(e)),
  });
  const sync = useMutation({
    mutationFn: () => api.syncAccount(account.id),
    onSuccess: (job) => {
      setMessage(
        job.status === 'succeeded'
          ? `Sync complete: ${job.resources_found} found, ${job.resources_created} new, ${job.resources_updated} updated, ${job.resources_deleted} removed`
          : `Sync ${job.status}${job.error ? `: ${job.error}` : ''}`,
      );
      refresh();
    },
    onError: (e) => setMessage(errorMessage(e)),
  });
  const remove = useMutation({ mutationFn: () => api.deleteAccount(account.id), onSuccess: refresh });

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ProviderBadge provider={account.provider} />
            <h3 className="font-semibold text-ink">{account.name}</h3>
          </div>
          <p className="mt-1 font-mono text-xs text-muted">{account.external_id}</p>
        </div>
        <StatusBadge status={account.status} />
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        <div>
          <dt className="text-faint">Resources</dt>
          <dd className="mt-0.5 text-sm font-semibold text-ink">{account.resource_count}</dd>
        </div>
        <div>
          <dt className="text-faint">Region</dt>
          <dd className="mt-0.5 text-ink/90">{account.default_region}</dd>
        </div>
        <div>
          <dt className="text-faint">Last sync</dt>
          <dd className="mt-0.5 text-ink/90">{timeAgo(account.last_synced_at)}</dd>
        </div>
        <div>
          <dt className="text-faint">Credential</dt>
          <dd className="mt-0.5 truncate font-mono text-ink/90" title="Masked hint; secrets are never returned">
            {account.credential_hint ?? '-'}
          </dd>
        </div>
      </dl>
      {account.status_message && <p className="mt-3 text-xs text-muted">{account.status_message}</p>}
      {message && (
        <p role="status" className="mt-3 rounded-lg bg-elevated px-3 py-2 text-xs text-ink/90">
          {message}
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        {can('accounts:write') && (
          <Button size="sm" variant="secondary" icon={<ShieldCheck className="h-3.5 w-3.5" />} loading={validate.isPending} onClick={() => validate.mutate()}>
            Validate
          </Button>
        )}
        {can('resources:sync') && (
          <Button size="sm" variant="secondary" icon={<RefreshCw className="h-3.5 w-3.5" />} loading={sync.isPending} onClick={() => sync.mutate()}>
            Sync now
          </Button>
        )}
        {can('accounts:write') && (
          <Button
            size="sm"
            variant="ghost"
            icon={<Trash2 className="h-3.5 w-3.5" />}
            loading={remove.isPending}
            onClick={() => {
              if (window.confirm(`Remove ${account.name} and its inventory from CloudOrbit?`)) remove.mutate();
            }}
          >
            Remove
          </Button>
        )}
      </div>
    </Card>
  );
}

export function AccountsPage() {
  const { can } = useAuth();
  const [open, setOpen] = useState(false);
  const query = useQuery({ queryKey: ['accounts'], queryFn: api.accounts });

  return (
    <>
      <PageHeader
        title="Cloud accounts"
        description="AWS accounts, Azure subscriptions and GCP projects connected to CloudOrbit"
        actions={
          can('accounts:write') && (
            <Button icon={<Plus className="h-4 w-4" />} onClick={() => setOpen(true)}>
              Connect account
            </Button>
          )
        }
      />
      {query.isPending && <Spinner label="Loading accounts" />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
      {query.data && query.data.length === 0 && (
        <EmptyState title="No cloud accounts" description="Connect your first account to start discovering resources." />
      )}
      {query.data && query.data.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {query.data.map((a) => (
            <AccountCard key={a.id} account={a} />
          ))}
        </div>
      )}
      <AddAccountModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
