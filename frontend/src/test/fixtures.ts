import type {
  Budget,
  CloudAccount,
  CostSummary,
  DashboardOverview,
  Page,
  ProvisioningPlanned,
  Resource,
  Template,
} from '../api/types';

export function page<T>(items: T[], total = items.length): Page<T> {
  return { items, total, limit: 25, offset: 0 };
}

export const account: CloudAccount = {
  id: 'acc-1',
  name: 'AWS Production',
  provider: 'aws',
  external_id: '123456789012',
  default_region: 'us-east-1',
  description: null,
  credential_hint: 'AKIA********0001',
  credentials_rotated_at: null,
  status: 'connected',
  status_message: 'Last sync succeeded',
  last_validated_at: null,
  last_synced_at: new Date().toISOString(),
  is_active: true,
  created_at: '2026-11-01T00:00:00Z',
  resource_count: 12,
};

export const resource: Resource = {
  id: 'res-1',
  cloud_account_id: 'acc-1',
  account_name: 'AWS Production',
  provider: 'aws',
  resource_type: 'ec2_instance',
  external_id: 'i-0abc123',
  name: 'prod-web-01',
  region: 'us-east-1',
  status: 'running',
  attributes: { instance_size: 't3.medium' },
  tags: { team: 'web' },
  monthly_cost_estimate: '30.37',
  managed_by_platform: false,
  first_seen_at: '2026-11-01T00:00:00Z',
  last_seen_at: '2026-11-09T00:00:00Z',
  deleted_at: null,
};

export const overview: DashboardOverview = {
  total_resources: 32,
  running_compute: 15,
  stopped_compute: 4,
  storage_resources: 13,
  accounts: { connected: 4, error: 0, pending: 0, last_sync_at: new Date().toISOString() },
  by_provider: [
    { key: 'aws', count: 18 },
    { key: 'azure', count: 8 },
    { key: 'gcp', count: 6 },
  ],
  by_status: [
    { key: 'running', count: 15 },
    { key: 'available', count: 13 },
    { key: 'stopped', count: 4 },
  ],
  by_type: [{ key: 'ec2_instance', count: 10 }],
  by_region: [{ key: 'us-east-1', count: 12 }],
  usage: { avg_cpu_percent: 41.2, avg_memory_percent: 55.3, total_storage_gb: 9200, high_cpu_resources: 2, series: [] },
  month_to_date_cost: '2016.69',
  estimated_monthly_run_rate: '1520.00',
  open_alerts: 5,
  critical_alerts: 1,
  recent_alerts: [
    {
      id: 'al-1',
      severity: 'critical',
      category: 'security',
      title: 'Public access not blocked on stdevlogs1',
      message: 'm',
      status: 'open',
      cloud_account_id: null,
      resource_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      resolved_at: null,
    },
  ],
  recent_activity: [
    {
      id: 'au-1',
      actor_id: null,
      actor_email: 'admin@cloudorbit.dev',
      action: 'cloud_account.create',
      target_type: 'cloud_account',
      target_id: 'acc-1',
      status: 'success',
      details: {},
      ip_address: '127.0.0.1',
      created_at: new Date().toISOString(),
    },
  ],
};

export const template: Template = {
  key: 'aws_s3_bucket',
  provider: 'aws',
  resource_type: 's3_bucket',
  title: 'AWS S3 bucket',
  description: 'Private bucket',
  terraform_resources: ['aws_s3_bucket'],
  estimated_monthly_cost: '$0.023 / GB',
  params: [
    { key: 'name', label: 'Resource name', type: 'string', required: true, default: null, options: [], pattern: null, description: '', minimum: null, maximum: null },
    { key: 'region', label: 'Region', type: 'enum', required: true, default: 'us-east-1', options: ['us-east-1', 'eu-west-1'], pattern: null, description: '', minimum: null, maximum: null },
    { key: 'versioning', label: 'Enable versioning', type: 'boolean', required: true, default: true, options: [], pattern: null, description: '', minimum: null, maximum: null },
  ],
};

export const plannedRequest: ProvisioningPlanned = {
  id: 'prov-1',
  cloud_account_id: 'acc-1',
  account_name: 'AWS Production',
  provider: 'aws',
  action: 'create',
  template_key: 'aws_s3_bucket',
  resource_name: 'team-reports',
  parameters: {},
  status: 'planned',
  rendered_hcl: 'resource "aws_s3_bucket" "team_reports" {}',
  plan_output: '[MOCK PLAN] Terraform was NOT executed.\nPlan: 4 to add, 0 to change, 0 to destroy.',
  plan_summary: { add: 4, change: 0, destroy: 0 },
  plan_is_mock: true,
  apply_output: null,
  confirmation_expires_at: new Date(Date.now() + 30 * 60_000).toISOString(),
  requested_by_id: null,
  confirmed_by_id: null,
  applied_at: null,
  error: null,
  target_resource_id: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  confirmation_token: 'one-time-token-123',
};

export const costSummary: CostSummary = {
  currency: 'USD',
  current_month: '2016.69',
  previous_month: '6359.01',
  change_percent: 5.7,
  forecast_current_month: '6722.30',
  by_provider: [
    { provider: 'aws', current_month: '1294.00', previous_month: '4090.05', change_percent: 4.1 },
    { provider: 'azure', current_month: '452.00', previous_month: '1345.00', change_percent: -2.0 },
    { provider: 'gcp', current_month: '270.69', previous_month: '879.45', change_percent: 1.1 },
  ],
};

export const budget: Budget = {
  id: 'bud-1',
  name: 'AWS monthly',
  provider: 'aws',
  cloud_account_id: null,
  monthly_limit: '1424.00',
  alert_threshold_percent: 75,
  is_active: true,
  created_at: '2026-11-01T00:00:00Z',
  current_spend: '1294.00',
  utilization_percent: 90.9,
};
