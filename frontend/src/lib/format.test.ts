import { describe, expect, it } from 'vitest';
import {
  formatCurrency,
  formatDateTime,
  formatMonth,
  formatNumber,
  formatPercent,
  humanize,
  providerLabel,
  resourceTypeLabel,
  timeAgo,
  toNumber,
} from './format';

describe('format helpers', () => {
  it('parses decimal strings safely', () => {
    expect(toNumber('12.50')).toBe(12.5);
    expect(toNumber(null)).toBe(0);
    expect(toNumber('not-a-number')).toBe(0);
    expect(toNumber(7)).toBe(7);
  });

  it('formats currency, with compact notation for large values', () => {
    expect(formatCurrency('1234.5')).toBe('$1,234.50');
    expect(formatCurrency(0)).toBe('$0.00');
    expect(formatCurrency(125000, true)).toBe('$125K');
    expect(formatCurrency(950, true)).toBe('$950.00');
  });

  it('formats signed percentages and handles missing values', () => {
    expect(formatPercent(5.27)).toBe('+5.3%');
    expect(formatPercent(-2)).toBe('-2.0%');
    expect(formatPercent(0)).toBe('0.0%');
    expect(formatPercent(null)).toBe('-');
  });

  it('formats numbers and dates', () => {
    expect(formatNumber(12345)).toBe('12,345');
    expect(formatNumber(undefined)).toBe('-');
    expect(formatDateTime(null)).toBe('-');
    expect(formatDateTime('garbage')).toBe('-');
    expect(formatMonth('2026-03-01')).toBe('Mar 26');
  });

  it('renders relative time', () => {
    const now = new Date('2026-11-10T12:00:00Z');
    expect(timeAgo(null, now)).toBe('never');
    expect(timeAgo('2026-11-10T11:59:50Z', now)).toBe('just now');
    expect(timeAgo('2026-11-10T11:30:00Z', now)).toBe('30m ago');
    expect(timeAgo('2026-11-10T07:00:00Z', now)).toBe('5h ago');
    expect(timeAgo('2026-11-07T12:00:00Z', now)).toBe('3d ago');
  });

  it('labels providers, resource types and actions', () => {
    expect(providerLabel('aws')).toBe('AWS');
    expect(providerLabel('gcp')).toBe('GCP');
    expect(providerLabel(undefined)).toBe('-');
    expect(resourceTypeLabel('azure_storage_account')).toBe('Storage account');
    expect(resourceTypeLabel('custom_thing')).toBe('custom thing');
    expect(humanize('cloud_account.create')).toBe('Cloud Account Create');
  });
});
