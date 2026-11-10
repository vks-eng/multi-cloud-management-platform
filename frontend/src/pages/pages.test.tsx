import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { api } from '../api/endpoints';
import { App } from '../App';
import { account, budget, costSummary, overview, page, plannedRequest, resource, template } from '../test/fixtures';
import { makeUser, renderPage } from '../test/utils';
import { ConfirmPanel } from './InfrastructurePage';

vi.mock('../api/endpoints', () => ({ api: {} }));

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

function stubApi(overrides: Record<string, unknown> = {}) {
  const defaults: Record<string, unknown> = {
    me: makeUser('admin'),
    overview,
    accounts: [account],
    resources: page([resource]),
    resourceChanges: page([]),
    resourceMetrics: [],
    templates: [template],
    terraformStatus: { binary_found: false, binary_path: null, mode: 'auto', mock_reason: 'CLOUD_PROVIDER_MODE=mock', apply_enabled: false },
    provisioning: page([]),
    costSummary,
    costTrends: [{ month: '2026-11-01', aws: '1294.00', azure: '452.00', gcp: '270.69', total: '2016.69' }],
    costByService: [{ provider: 'aws', service: 'Amazon EC2', amount: '800.00' }],
    budgets: [budget],
    costAlerts: page([]),
    alerts: page(overview.recent_alerts),
    auditLogs: page(overview.recent_activity),
    accessHistory: page([]),
    allChanges: page([]),
    roles: [
      { role: 'admin', description: '', permissions: ['users:manage', 'costs:read'] },
      { role: 'viewer', description: '', permissions: ['costs:read'] },
    ],
    users: page([makeUser('admin')]),
  };
  const all = { ...defaults, ...overrides };
  Object.keys(mocked).forEach((k) => delete mocked[k]);
  Object.entries(all).forEach(([key, value]) => {
    mocked[key] = vi.fn().mockImplementation(() => (value instanceof Error ? Promise.reject(value) : Promise.resolve(value)));
  });
}

beforeEach(() => stubApi());

describe('Authentication flow', () => {
  it('redirects anonymous users to the login page', async () => {
    renderPage(<App />, { path: '/costs', signedIn: false });
    expect(await screen.findByRole('heading', { name: 'Sign in to CloudOrbit' })).toBeInTheDocument();
  });

  it('logs in and lands on the overview dashboard', async () => {
    mocked.login = vi.fn().mockResolvedValue({ access_token: 'jwt', token_type: 'bearer', expires_in: 3600, user: makeUser('operator') });
    renderPage(<App />, { path: '/login', signedIn: false });
    await userEvent.type(screen.getByLabelText('E-mail'), 'operator@cloudorbit.dev');
    await userEvent.type(screen.getByLabelText('Password'), 'CloudOrbit!2026');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeInTheDocument();
    expect(mocked.login).toHaveBeenCalledWith('operator@cloudorbit.dev', 'CloudOrbit!2026');
    expect(sessionStorage.getItem('cloudorbit.token')).toBe('jwt');
  });

  it('shows the API error on failed login', async () => {
    mocked.login = vi.fn().mockRejectedValue(new ApiError(401, 'not_authenticated', 'Incorrect e-mail or password'));
    renderPage(<App />, { path: '/login', signedIn: false });
    await userEvent.type(screen.getByLabelText('E-mail'), 'x@y.dev');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect e-mail or password');
  });

  it('signs out from the top bar', async () => {
    renderPage(<App />);
    await userEvent.click(await screen.findByRole('button', { name: /sign out/i }));
    expect(await screen.findByRole('heading', { name: 'Sign in to CloudOrbit' })).toBeInTheDocument();
    expect(sessionStorage.getItem('cloudorbit.token')).toBeNull();
  });
});

describe('Overview page', () => {
  it('renders KPIs, alerts and recent activity', async () => {
    renderPage(<App />);
    expect(await screen.findByText('Total resources')).toBeInTheDocument();
    expect(screen.getByText('32')).toBeInTheDocument();
    expect(screen.getByText('$2,016.69')).toBeInTheDocument();
    expect(screen.getByText('Public access not blocked on stdevlogs1')).toBeInTheDocument();
    expect(screen.getByText('Cloud Account Create')).toBeInTheDocument();
  });

  it('shows an empty state when nothing is synced', async () => {
    stubApi({ overview: { ...overview, total_resources: 0 } });
    renderPage(<App />);
    expect(await screen.findByText('No resources yet')).toBeInTheDocument();
  });

  it('shows an error with retry', async () => {
    stubApi({ overview: new ApiError(500, 'internal_error', 'Database unavailable') });
    renderPage(<App />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Database unavailable');
  });
});

describe('Navigation respects RBAC', () => {
  it('hides admin-only actions from viewers', async () => {
    stubApi({ me: makeUser('viewer') });
    renderPage(<App />, { path: '/accounts' });
    expect(await screen.findByText('AWS Production')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Connect account' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Validate' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sync now' })).not.toBeInTheDocument();
  });

  it('lets operators sync but not manage accounts', async () => {
    stubApi({ me: makeUser('operator') });
    mocked.syncAccount = vi.fn().mockResolvedValue({ status: 'succeeded', resources_found: 9, resources_created: 1, resources_updated: 2, resources_deleted: 0, error: null });
    renderPage(<App />, { path: '/accounts' });
    await userEvent.click(await screen.findByRole('button', { name: 'Sync now' }));
    expect(await screen.findByText(/Sync complete: 9 found/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Connect account' })).not.toBeInTheDocument();
  });

  it('admins see every navigation entry; viewers do not see restricted pages content', async () => {
    renderPage(<App />);
    const nav = await screen.findByRole('navigation', { name: 'Main navigation' });
    expect(within(nav).getAllByRole('link')).toHaveLength(8);
  });
});

describe('Cloud accounts page', () => {
  it('creates an account with provider-specific credential fields', async () => {
    mocked.createAccount = vi.fn().mockResolvedValue(account);
    renderPage(<App />, { path: '/accounts' });
    await userEvent.click(await screen.findByRole('button', { name: 'Connect account' }));
    const dialog = screen.getByRole('dialog', { name: 'Connect a cloud account' });
    await userEvent.selectOptions(within(dialog).getByLabelText('Provider'), 'azure');
    expect(within(dialog).getByLabelText('Client secret')).toHaveAttribute('type', 'password');
    await userEvent.type(within(dialog).getByLabelText('Display name'), 'Azure Corp');
    await userEvent.type(within(dialog).getByLabelText('Subscription ID (GUID)'), '3f2b8c1e-9a4d-4e6f-8b7a-1c2d3e4f5a6b');
    await userEvent.type(within(dialog).getByLabelText('Tenant ID'), 't');
    await userEvent.type(within(dialog).getByLabelText('Client (application) ID'), 'c');
    await userEvent.type(within(dialog).getByLabelText('Client secret'), 's');
    await userEvent.click(screen.getByRole('button', { name: 'Save account' }));
    await waitFor(() => expect(mocked.createAccount).toHaveBeenCalled());
    expect(mocked.createAccount.mock.calls[0][0]).toMatchObject({
      provider: 'azure',
      name: 'Azure Corp',
      default_region: 'westeurope',
      credentials: { tenant_id: 't', client_id: 'c', client_secret: 's' },
    });
  });
});

describe('Resource inventory page', () => {
  it('filters by provider and opens the detail view', async () => {
    renderPage(<App />, { path: '/resources' });
    expect(await screen.findByText('prod-web-01')).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Provider'), 'gcp');
    await waitFor(() => expect(mocked.resources).toHaveBeenLastCalledWith(expect.objectContaining({ provider: 'gcp', offset: 0 })));
    await userEvent.click(screen.getByText('prod-web-01'));
    const dialog = await screen.findByRole('dialog', { name: 'prod-web-01' });
    expect(within(dialog).getByText('i-0abc123')).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Plan decommission' })).toBeInTheDocument();
  });

  it('shows an empty state for no matches', async () => {
    stubApi({ resources: page([]) });
    renderPage(<App />, { path: '/resources' });
    expect(await screen.findByText('No resources match these filters')).toBeInTheDocument();
  });
});

describe('Infrastructure plan → confirm flow', () => {
  it('generates a plan from a template', async () => {
    mocked.plan = vi.fn().mockResolvedValue(plannedRequest);
    renderPage(<App />, { path: '/infrastructure' });
    await userEvent.type(await screen.findByLabelText('Resource name'), 'team-reports');
    await userEvent.click(screen.getByRole('button', { name: 'Generate plan' }));
    expect(await screen.findByText('MOCK PLAN')).toBeInTheDocument();
    expect(mocked.plan).toHaveBeenCalledWith({
      cloud_account_id: 'acc-1',
      template_key: 'aws_s3_bucket',
      parameters: { name: 'team-reports', region: 'us-east-1', versioning: true },
    });
    expect(screen.getByLabelText('Terraform plan output')).toHaveTextContent('Plan: 4 to add');
  });

  it('keeps apply disabled until the name is typed and the plan acknowledged', async () => {
    mocked.apply = vi.fn().mockResolvedValue({ ...plannedRequest, status: 'applied', apply_output: '[MOCK APPLY] done' });
    renderPage(<ConfirmPanel plan={plannedRequest} onDone={() => {}} />);
    const apply = await screen.findByRole('button', { name: 'Confirm & apply' });
    expect(apply).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Type "team-reports" to confirm'), 'team-report');
    await userEvent.click(screen.getByRole('checkbox'));
    expect(apply).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Type "team-reports" to confirm'), 's');
    expect(apply).toBeEnabled();
    await userEvent.click(apply);
    expect(await screen.findByText('Request applied')).toBeInTheDocument();
    expect(mocked.apply).toHaveBeenCalledWith('prov-1', 'one-time-token-123', 'team-reports');
  });

  it('surfaces a rejected confirmation', async () => {
    mocked.apply = vi.fn().mockRejectedValue(new ApiError(403, 'permission_denied', 'Invalid confirmation token'));
    renderPage(<ConfirmPanel plan={plannedRequest} onDone={() => {}} />);
    await userEvent.type(await screen.findByLabelText('Type "team-reports" to confirm'), 'team-reports');
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(screen.getByRole('button', { name: 'Confirm & apply' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid confirmation token');
  });

  it('hides the plan form from viewers', async () => {
    stubApi({ me: makeUser('viewer') });
    renderPage(<App />, { path: '/infrastructure' });
    expect(await screen.findByText('Provisioning history')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Generate plan' })).not.toBeInTheDocument();
  });
});

describe('Cost analytics page', () => {
  it('renders summary, provider comparison and budgets', async () => {
    renderPage(<App />, { path: '/costs' });
    expect(await screen.findByText('Month to date')).toBeInTheDocument();
    expect(screen.getByText('+5.7% vs last month')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'AWS monthly utilisation' })).toHaveAttribute('aria-valuenow', '91');
    expect(screen.getByRole('button', { name: 'New budget' })).toBeInTheDocument();
  });
});

describe('Monitoring and activity pages', () => {
  it('lists alerts and acknowledges one', async () => {
    mocked.acknowledgeAlert = vi.fn().mockResolvedValue({});
    renderPage(<App />, { path: '/monitoring' });
    const row = (await screen.findAllByText('Public access not blocked on stdevlogs1'))[0];
    expect(row).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Acknowledge' }));
    await waitFor(() => expect(mocked.acknowledgeAlert).toHaveBeenCalledWith('al-1'));
  });

  it('shows the audit log for admins and filters by action', async () => {
    renderPage(<App />, { path: '/activity' });
    expect(await screen.findByText('cloud_account.create')).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Action'), 'provisioning');
    await waitFor(() => expect(mocked.auditLogs).toHaveBeenLastCalledWith(expect.objectContaining({ action: 'provisioning' })));
  });

  it('hides the audit tab from viewers', async () => {
    stubApi({ me: makeUser('viewer') });
    renderPage(<App />, { path: '/activity' });
    expect(await screen.findByRole('tab', { name: 'Access history' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByRole('tab', { name: 'Audit log' })).not.toBeInTheDocument();
  });
});

describe('Settings page', () => {
  it('shows profile, the permission matrix and admin user management', async () => {
    renderPage(<App />, { path: '/settings' });
    expect(await screen.findByRole('heading', { name: 'Profile' })).toBeInTheDocument();
    expect(await screen.findByRole('table', { name: 'Role permission matrix' })).toBeInTheDocument();
    expect(await screen.findByRole('table', { name: 'Users' })).toBeInTheDocument();
  });
});
