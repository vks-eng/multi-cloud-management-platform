// Response/request types mirroring the backend Pydantic schemas (app/schemas/*).
// Decimal fields are serialised by the API as strings.

export type Provider = 'aws' | 'azure' | 'gcp';
export type Role = 'admin' | 'operator' | 'viewer';

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  job_title: string | null;
  timezone: string;
  last_login_at: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface RolePermissions {
  role: Role;
  description: string;
  permissions: string[];
}

export interface CloudAccount {
  id: string;
  name: string;
  provider: Provider;
  external_id: string;
  default_region: string;
  description: string | null;
  credential_hint: string | null;
  credentials_rotated_at: string | null;
  status: 'pending' | 'connected' | 'error';
  status_message: string | null;
  last_validated_at: string | null;
  last_synced_at: string | null;
  is_active: boolean;
  created_at: string;
  resource_count: number;
}

export interface CloudAccountCreate {
  name: string;
  provider: Provider;
  external_id: string;
  default_region: string;
  description?: string;
  credentials: Record<string, string>;
}

export interface ConnectionTestResult {
  ok: boolean;
  message: string;
  identity: string | null;
  adapter: string;
}

export interface SyncJob {
  id: string;
  cloud_account_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  trigger: string;
  started_at: string | null;
  finished_at: string | null;
  resources_found: number;
  resources_created: number;
  resources_updated: number;
  resources_deleted: number;
  error: string | null;
  created_at: string;
}

export interface Resource {
  id: string;
  cloud_account_id: string;
  account_name: string | null;
  provider: Provider;
  resource_type: string;
  external_id: string;
  name: string;
  region: string;
  status: string;
  attributes: Record<string, unknown>;
  tags: Record<string, string>;
  monthly_cost_estimate: string;
  managed_by_platform: boolean;
  first_seen_at: string;
  last_seen_at: string;
  deleted_at: string | null;
}

export interface ResourceChange {
  id: string;
  resource_id: string;
  resource_name: string | null;
  change_type: string;
  source: string;
  changes: Record<string, unknown>;
  actor_id: string | null;
  created_at: string;
}

export interface ResourceMetric {
  captured_at: string;
  cpu_percent: number | null;
  memory_percent: number | null;
  network_in_mb: number | null;
  network_out_mb: number | null;
  storage_used_gb: number | null;
}

export interface TemplateParam {
  key: string;
  label: string;
  type: 'string' | 'integer' | 'boolean' | 'enum';
  required: boolean;
  default: unknown;
  options: string[];
  pattern: string | null;
  description: string;
  minimum: number | null;
  maximum: number | null;
}

export interface Template {
  key: string;
  provider: Provider;
  resource_type: string;
  title: string;
  description: string;
  terraform_resources: string[];
  estimated_monthly_cost: string;
  params: TemplateParam[];
}

export interface TerraformStatus {
  binary_found: boolean;
  binary_path: string | null;
  mode: string;
  mock_reason: string | null;
  apply_enabled: boolean;
}

export interface ProvisioningRequest {
  id: string;
  cloud_account_id: string;
  account_name: string | null;
  provider: Provider | null;
  action: 'create' | 'destroy';
  template_key: string;
  resource_name: string;
  parameters: Record<string, unknown>;
  status: 'planned' | 'applying' | 'applied' | 'failed' | 'cancelled' | 'expired';
  rendered_hcl: string;
  plan_output: string;
  plan_summary: { add?: number; change?: number; destroy?: number };
  plan_is_mock: boolean;
  apply_output: string | null;
  confirmation_expires_at: string | null;
  requested_by_id: string | null;
  confirmed_by_id: string | null;
  applied_at: string | null;
  error: string | null;
  target_resource_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProvisioningPlanned extends ProvisioningRequest {
  confirmation_token: string;
}

export interface Alert {
  id: string;
  severity: 'info' | 'warning' | 'critical';
  category: string;
  title: string;
  message: string;
  status: 'open' | 'acknowledged' | 'resolved';
  cloud_account_id: string | null;
  resource_id: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface AuditLog {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  status: 'success' | 'failure';
  details: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface LoginEvent {
  id: string;
  user_id: string | null;
  email: string;
  success: boolean;
  failure_reason: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface CountItem {
  key: string;
  count: number;
}

export interface UsagePoint {
  timestamp: string;
  avg_cpu_percent: number | null;
  avg_memory_percent: number | null;
  network_in_mb: number;
  network_out_mb: number;
}

export interface DashboardOverview {
  total_resources: number;
  running_compute: number;
  stopped_compute: number;
  storage_resources: number;
  accounts: { connected: number; error: number; pending: number; last_sync_at: string | null };
  by_provider: CountItem[];
  by_status: CountItem[];
  by_type: CountItem[];
  by_region: CountItem[];
  usage: {
    avg_cpu_percent: number | null;
    avg_memory_percent: number | null;
    total_storage_gb: number;
    high_cpu_resources: number;
    series: UsagePoint[];
  };
  month_to_date_cost: string;
  estimated_monthly_run_rate: string;
  open_alerts: number;
  critical_alerts: number;
  recent_alerts: Alert[];
  recent_activity: AuditLog[];
}

export interface ProviderCost {
  provider: Provider;
  current_month: string;
  previous_month: string;
  change_percent: number | null;
}

export interface CostSummary {
  currency: string;
  current_month: string;
  previous_month: string;
  change_percent: number | null;
  forecast_current_month: string;
  by_provider: ProviderCost[];
}

export interface MonthlyTrendPoint {
  month: string;
  aws: string;
  azure: string;
  gcp: string;
  total: string;
}

export interface ServiceCost {
  provider: Provider;
  service: string;
  amount: string;
}

export interface Budget {
  id: string;
  name: string;
  provider: Provider | null;
  cloud_account_id: string | null;
  monthly_limit: string;
  alert_threshold_percent: number;
  is_active: boolean;
  created_at: string;
  current_spend: string;
  utilization_percent: number;
}

export interface BudgetCreate {
  name: string;
  provider?: Provider | null;
  cloud_account_id?: string | null;
  monthly_limit: string;
  alert_threshold_percent: number;
}

export interface CostAlert {
  id: string;
  budget_id: string;
  budget_name: string | null;
  period_month: string;
  threshold_percent: number;
  actual_amount: string;
  budget_limit: string;
  severity: 'warning' | 'critical';
  acknowledged: boolean;
  created_at: string;
}
