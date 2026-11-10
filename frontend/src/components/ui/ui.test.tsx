import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { roleHasPermission } from '../../auth/permissions';
import { ProviderBadge, StatusBadge, statusTone } from './Badge';
import { Button } from './Button';
import { Card, ErrorState, StatCard, errorMessage } from './Card';
import { DataTable, Pagination } from './DataTable';
import { SelectField, TextField } from './Field';
import { Modal } from './Modal';

describe('Button', () => {
  it('fires clicks and is disabled while loading', async () => {
    const onClick = vi.fn();
    const { rerender } = render(<Button onClick={onClick}>Save</Button>);
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onClick).toHaveBeenCalledOnce();
    rerender(
      <Button onClick={onClick} loading>
        Save
      </Button>,
    );
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Save' })).toHaveAttribute('aria-busy', 'true');
  });
});

describe('Badges', () => {
  it('maps statuses to tones', () => {
    expect(statusTone('running')).toBe('green');
    expect(statusTone('critical')).toBe('red');
    expect(statusTone('something-new')).toBe('gray');
  });
  it('renders status and provider labels', () => {
    render(
      <>
        <StatusBadge status="status_changed" />
        <ProviderBadge provider="azure" />
      </>,
    );
    expect(screen.getByText('status changed')).toBeInTheDocument();
    expect(screen.getByText('Azure')).toBeInTheDocument();
  });
});

describe('Card, StatCard and ErrorState', () => {
  it('renders title, actions and content', () => {
    render(
      <Card title="Budgets" actions={<button type="button">Add</button>}>
        body
      </Card>,
    );
    expect(screen.getByRole('heading', { name: 'Budgets' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument();
  });
  it('shows a KPI', () => {
    render(<StatCard label="Open alerts" value={5} hint="1 critical" />);
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('1 critical')).toBeInTheDocument();
  });
  it('shows API errors with a retry action', async () => {
    const retry = vi.fn();
    render(<ErrorState error={new ApiError(500, 'internal_error', 'Boom')} onRetry={retry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Boom');
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retry).toHaveBeenCalled();
    expect(errorMessage('weird')).toBe('Something went wrong');
  });
});

describe('Form fields', () => {
  it('associates labels and announces errors', () => {
    render(
      <>
        <TextField label="Name" error="Required" />
        <SelectField label="Provider" options={[{ value: 'aws', label: 'AWS' }]} />
      </>,
    );
    const input = screen.getByLabelText('Name');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAccessibleDescription('Required');
    expect(screen.getByLabelText('Provider')).toHaveValue('aws');
  });
});

describe('Modal', () => {
  it('renders as a dialog and closes on Escape', async () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <Modal open title="Confirm" onClose={onClose}>
        content
      </Modal>,
    );
    expect(screen.getByRole('dialog', { name: 'Confirm' })).toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
    rerender(
      <Modal open={false} title="Confirm" onClose={onClose}>
        content
      </Modal>,
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('DataTable and Pagination', () => {
  const rows = [
    { id: '1', name: 'alpha' },
    { id: '2', name: 'beta' },
  ];
  it('renders rows and handles row clicks', async () => {
    const onRowClick = vi.fn();
    render(
      <DataTable caption="Things" columns={[{ key: 'n', header: 'Name', render: (r) => r.name }]} rows={rows} rowKey={(r) => r.id} onRowClick={onRowClick} />,
    );
    expect(screen.getByRole('table', { name: 'Things' })).toBeInTheDocument();
    await userEvent.click(screen.getByText('beta'));
    expect(onRowClick).toHaveBeenCalledWith(rows[1]);
  });
  it('shows an empty state', () => {
    render(<DataTable columns={[]} rows={[]} rowKey={() => 'x'} emptyTitle="Nothing here" />);
    expect(screen.getByText('Nothing here')).toBeInTheDocument();
  });
  it('paginates', async () => {
    const onChange = vi.fn();
    const { rerender } = render(<Pagination total={45} limit={20} offset={0} onChange={onChange} />);
    expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(onChange).toHaveBeenCalledWith(20);
    rerender(<Pagination total={10} limit={20} offset={0} onChange={onChange} />);
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });
});

describe('RBAC helper', () => {
  it('mirrors the backend role matrix', () => {
    expect(roleHasPermission('admin', 'users:manage')).toBe(true);
    expect(roleHasPermission('operator', 'infra:apply')).toBe(true);
    expect(roleHasPermission('operator', 'accounts:write')).toBe(false);
    expect(roleHasPermission('viewer', 'resources:sync')).toBe(false);
    expect(roleHasPermission('viewer', 'costs:read')).toBe(true);
    expect(roleHasPermission(undefined, 'costs:read')).toBe(false);
  });
});
