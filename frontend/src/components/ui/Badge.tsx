import clsx from 'clsx';
import type { ReactNode } from 'react';
import { providerLabel } from '../../lib/format';

export type Tone = 'gray' | 'green' | 'amber' | 'red' | 'blue' | 'indigo';

const TONES: Record<Tone, string> = {
  gray: 'bg-slate-100 text-slate-700 ring-slate-200',
  green: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  red: 'bg-rose-50 text-rose-800 ring-rose-200',
  blue: 'bg-sky-50 text-sky-800 ring-sky-200',
  indigo: 'bg-brand-50 text-brand-700 ring-brand-200',
};

export function Badge({ tone = 'gray', children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const STATUS_TONES: Record<string, Tone> = {
  running: 'green',
  available: 'green',
  connected: 'green',
  succeeded: 'green',
  applied: 'green',
  success: 'green',
  resolved: 'green',
  stopped: 'amber',
  pending: 'amber',
  warning: 'amber',
  open: 'amber',
  planned: 'blue',
  queued: 'blue',
  applying: 'blue',
  provisioning: 'blue',
  acknowledged: 'blue',
  error: 'red',
  failed: 'red',
  failure: 'red',
  critical: 'red',
  terminated: 'gray',
  deleted: 'gray',
  cancelled: 'gray',
  expired: 'gray',
  info: 'indigo',
};

export function statusTone(status: string): Tone {
  return STATUS_TONES[status] ?? 'gray';
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={statusTone(status)}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {status.replace(/_/g, ' ')}
    </Badge>
  );
}

const PROVIDER_STYLES: Record<string, string> = {
  aws: 'bg-orange-50 text-orange-900 ring-orange-200',
  azure: 'bg-sky-50 text-sky-900 ring-sky-200',
  gcp: 'bg-emerald-50 text-emerald-900 ring-emerald-200',
};

export function ProviderBadge({ provider }: { provider: string | null | undefined }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded px-1.5 py-0.5 text-xs font-semibold ring-1 ring-inset',
        PROVIDER_STYLES[provider ?? ''] ?? 'bg-slate-100 text-slate-700 ring-slate-200',
      )}
    >
      {providerLabel(provider)}
    </span>
  );
}
