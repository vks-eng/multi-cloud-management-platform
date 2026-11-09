// Pure formatting helpers (unit-tested in format.test.ts).

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
const usdCompact = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  maximumFractionDigits: 1,
});

export function toNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === '') return 0;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

export function formatCurrency(value: string | number | null | undefined, compact = false): string {
  const n = toNumber(value);
  return compact && Math.abs(n) >= 10_000 ? usdCompact.format(n) : usd.format(n);
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '-';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '-';
  return value.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '-';
  return d.toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function formatMonth(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit', timeZone: 'UTC' });
}

export function timeAgo(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return 'never';
  const seconds = Math.round((now.getTime() - new Date(iso).getTime()) / 1000);
  if (seconds < 45) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

const RESOURCE_TYPE_LABELS: Record<string, string> = {
  ec2_instance: 'EC2 instance',
  s3_bucket: 'S3 bucket',
  azure_vm: 'Azure VM',
  azure_storage_account: 'Storage account',
  gcp_compute_instance: 'Compute instance',
  gcp_bucket: 'GCS bucket',
};

export function resourceTypeLabel(type: string): string {
  return RESOURCE_TYPE_LABELS[type] ?? type.replace(/_/g, ' ');
}

export const PROVIDER_LABELS: Record<string, string> = { aws: 'AWS', azure: 'Azure', gcp: 'GCP' };

export function providerLabel(provider: string | null | undefined): string {
  return provider ? (PROVIDER_LABELS[provider] ?? provider.toUpperCase()) : '-';
}

export function humanize(text: string): string {
  return text.replace(/[._]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
