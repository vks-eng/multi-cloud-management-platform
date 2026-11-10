import clsx from 'clsx';
import {
  Activity,
  BellRing,
  Boxes,
  Cloud,
  DollarSign,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  Wrench,
  X,
} from 'lucide-react';
import { useState, type ComponentType } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import type { Permission } from '../../auth/permissions';
import { Logo } from './Logo';

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  permission?: Permission;
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/accounts', label: 'Cloud accounts', icon: Cloud, permission: 'accounts:read' },
  { to: '/resources', label: 'Inventory', icon: Boxes, permission: 'resources:read' },
  { to: '/infrastructure', label: 'Infrastructure', icon: Wrench, permission: 'infra:read' },
  { to: '/costs', label: 'Cost analytics', icon: DollarSign, permission: 'costs:read' },
  { to: '/monitoring', label: 'Monitoring', icon: BellRing, permission: 'resources:read' },
  { to: '/activity', label: 'Activity logs', icon: Activity },
  { to: '/settings', label: 'Settings', icon: Settings },
];

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth();
  return (
    <nav aria-label="Main navigation" className="flex flex-1 flex-col gap-1 px-3">
      {NAV_ITEMS.filter((item) => !item.permission || can(item.permission)).map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          onClick={onNavigate}
          className={({ isActive }) =>
            clsx(
              'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-orbit-400/10 text-orbit-200 ring-1 ring-inset ring-orbit-400/25'
                : 'text-muted hover:bg-elevated hover:text-ink',
            )
          }
        >
          <item.icon className="h-4 w-4 shrink-0" />
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const initials = (user?.full_name || user?.email || '?')
    .split(/\s+/)
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="min-h-screen bg-canvas">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-line bg-surface/80 py-5 backdrop-blur lg:flex">
        <div className="mb-6 px-6">
          <Logo />
        </div>
        <Sidebar />
        <p className="px-6 text-[11px] text-faint">v1.0 · mock providers by default</p>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} aria-hidden />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col border-r border-line bg-surface py-5">
            <div className="mb-6 flex items-center justify-between px-6">
              <Logo />
              <button
                type="button"
                className="rounded-md p-1 text-muted hover:bg-elevated"
                onClick={() => setMobileOpen(false)}
                aria-label="Close navigation"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-line bg-canvas/85 px-4 backdrop-blur sm:px-6">
          <button
            type="button"
            className="rounded-md p-1.5 text-muted hover:bg-elevated lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="h-5 w-5" />
          </button>
          <p className="hidden text-xs text-faint sm:block">Unified control plane for AWS, Azure and GCP</p>
          <div className="ml-auto flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium text-ink">{user?.full_name}</p>
              <p className="text-[11px] uppercase tracking-wider text-muted">{user?.role}</p>
            </div>
            <span
              className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-orbit-400 to-nebula-500 text-xs font-bold text-canvas"
              aria-hidden
            >
              {initials}
            </span>
            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-muted hover:bg-elevated hover:text-ink"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
