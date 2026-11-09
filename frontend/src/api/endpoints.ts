import { apiRequest } from './client';
import type {
  Alert,
  AuditLog,
  Budget,
  BudgetCreate,
  CloudAccount,
  CloudAccountCreate,
  ConnectionTestResult,
  CostAlert,
  CostSummary,
  DashboardOverview,
  LoginEvent,
  MonthlyTrendPoint,
  Page,
  ProvisioningPlanned,
  ProvisioningRequest,
  Resource,
  ResourceChange,
  ResourceMetric,
  RolePermissions,
  ServiceCost,
  SyncJob,
  Template,
  TerraformStatus,
  TokenResponse,
  User,
} from './types';

export interface ResourceFilters {
  provider?: string;
  resource_type?: string;
  status?: string;
  account_id?: string;
  search?: string;
  sort?: string;
  include_deleted?: boolean;
  limit?: number;
  offset?: number;
}

export const api = {
  // Auth & profile
  login: (email: string, password: string) =>
    apiRequest<TokenResponse>('/auth/login', { method: 'POST', body: { email, password } }),
  register: (data: { email: string; password: string; full_name: string }) =>
    apiRequest<User>('/auth/register', { method: 'POST', body: data }),
  me: () => apiRequest<User>('/auth/me'),
  updateProfile: (data: Partial<Pick<User, 'full_name' | 'job_title' | 'timezone'>>) =>
    apiRequest<User>('/auth/me', { method: 'PATCH', body: data }),
  changePassword: (current_password: string, new_password: string) =>
    apiRequest<{ message: string }>('/auth/me/password', {
      method: 'POST',
      body: { current_password, new_password },
    }),

  // Users
  roles: () => apiRequest<RolePermissions[]>('/users/roles'),
  users: (query?: { search?: string; limit?: number; offset?: number }) =>
    apiRequest<Page<User>>('/users', { query }),
  updateUser: (id: string, data: { role?: string; is_active?: boolean }) =>
    apiRequest<User>(`/users/${id}`, { method: 'PATCH', body: data }),

  // Cloud accounts
  accounts: () => apiRequest<CloudAccount[]>('/cloud-accounts'),
  createAccount: (data: CloudAccountCreate) =>
    apiRequest<CloudAccount>('/cloud-accounts', { method: 'POST', body: data }),
  deleteAccount: (id: string) => apiRequest<void>(`/cloud-accounts/${id}`, { method: 'DELETE' }),
  validateAccount: (id: string) =>
    apiRequest<ConnectionTestResult>(`/cloud-accounts/${id}/validate`, { method: 'POST' }),
  syncAccount: (id: string) => apiRequest<SyncJob>(`/cloud-accounts/${id}/sync`, { method: 'POST' }),
  syncJobs: (id: string) => apiRequest<SyncJob[]>(`/cloud-accounts/${id}/sync-jobs`),

  // Resources
  resources: (filters: ResourceFilters) =>
    apiRequest<Page<Resource>>('/resources', { query: { ...filters } }),
  resource: (id: string) => apiRequest<Resource>(`/resources/${id}`),
  resourceChanges: (id: string) => apiRequest<Page<ResourceChange>>(`/resources/${id}/changes`),
  resourceMetrics: (id: string, hours = 24) =>
    apiRequest<ResourceMetric[]>(`/resources/${id}/metrics`, { query: { hours } }),
  allChanges: (query?: { limit?: number; offset?: number }) =>
    apiRequest<Page<ResourceChange>>('/resources/changes', { query }),

  // Infrastructure
  terraformStatus: () => apiRequest<TerraformStatus>('/infrastructure/terraform'),
  templates: () => apiRequest<Template[]>('/infrastructure/templates'),
  previewTemplate: (key: string, cloud_account_id: string, parameters: Record<string, unknown>) =>
    apiRequest<{ template_key: string; hcl: string }>(`/infrastructure/templates/${key}/preview`, {
      method: 'POST',
      body: { cloud_account_id, parameters },
    }),
  provisioning: (query?: { status?: string; limit?: number; offset?: number }) =>
    apiRequest<Page<ProvisioningRequest>>('/infrastructure/provisioning', { query }),
  plan: (data: { cloud_account_id: string; template_key: string; parameters: Record<string, unknown> }) =>
    apiRequest<ProvisioningPlanned>('/infrastructure/provisioning', { method: 'POST', body: data }),
  planDestroy: (resource_id: string) =>
    apiRequest<ProvisioningPlanned>('/infrastructure/decommission', {
      method: 'POST',
      body: { resource_id },
    }),
  apply: (id: string, confirmation_token: string, confirm_resource_name: string) =>
    apiRequest<ProvisioningRequest>(`/infrastructure/provisioning/${id}/apply`, {
      method: 'POST',
      body: { confirmation_token, confirm_resource_name },
    }),
  cancel: (id: string) =>
    apiRequest<ProvisioningRequest>(`/infrastructure/provisioning/${id}/cancel`, { method: 'POST' }),

  // Monitoring
  overview: (usage_hours = 24) =>
    apiRequest<DashboardOverview>('/dashboard/overview', { query: { usage_hours } }),
  alerts: (query?: { status?: string; severity?: string; limit?: number; offset?: number }) =>
    apiRequest<Page<Alert>>('/alerts', { query }),
  acknowledgeAlert: (id: string) => apiRequest<Alert>(`/alerts/${id}/acknowledge`, { method: 'POST' }),
  resolveAlert: (id: string) => apiRequest<Alert>(`/alerts/${id}/resolve`, { method: 'POST' }),

  // Costs
  costSummary: () => apiRequest<CostSummary>('/costs/summary'),
  costTrends: (months = 6) => apiRequest<MonthlyTrendPoint[]>('/costs/trends', { query: { months } }),
  costByService: () => apiRequest<ServiceCost[]>('/costs/by-service'),
  budgets: () => apiRequest<Budget[]>('/costs/budgets'),
  createBudget: (data: BudgetCreate) => apiRequest<Budget>('/costs/budgets', { method: 'POST', body: data }),
  deleteBudget: (id: string) => apiRequest<void>(`/costs/budgets/${id}`, { method: 'DELETE' }),
  costAlerts: () => apiRequest<Page<CostAlert>>('/costs/alerts', { query: { limit: 50 } }),

  // Audit
  auditLogs: (query?: { action?: string; status?: string; limit?: number; offset?: number }) =>
    apiRequest<Page<AuditLog>>('/audit/logs', { query }),
  accessHistory: (query?: { limit?: number; offset?: number }) =>
    apiRequest<Page<LoginEvent>>('/audit/access-history', { query }),
};
