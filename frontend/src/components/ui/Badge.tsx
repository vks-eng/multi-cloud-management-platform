import clsx from 'clsx';
import type { ReactNode } from 'react';
import { providerLabel } from '../../lib/format';

export type Tone = 'gray' | 'green' | 'amber' | 'red' | 'blue' | 'violet';

const TONES: Record<Tone, string> = {
  gray: 'bg-slate-500/15 text-slate-300 ring-slate-500/30',
  green: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  amber: 'bg-amber-500/15 text-amber-300 ring-amber-500/30',
  red: 'bg-rose-500/15 text-rose-300 ring-rose-500/30',
  blue: 'bg-sky-500/15 text-sky-300 ring-sky-500/30',
  violet: 'bg-nebula-500/15 text-nebula-300 ring-nebula-500/30',
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
  info: 'violet',
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
  aws: 'bg-amber-500/15 text-amber-300 ring-amber-500/30',
  azure: 'bg-sky-500/15 text-sky-300 ring-sky-500/30',
  gcp: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
};

export function ProviderBadge({ provider }: { provider: string | null | undefined }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-semibold tracking-wide ring-1 ring-inset',
        PROVIDER_STYLES[provider ?? ''] ?? TONES.gray,
      )}
    >
      {providerLabel(provider)}
    </span>
  );
}
