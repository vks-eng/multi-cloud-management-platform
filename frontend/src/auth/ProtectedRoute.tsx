import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Spinner } from '../components/ui/Card';
import { useAuth } from './AuthContext';
import type { Permission } from './permissions';

export function ProtectedRoute({ children, permission }: { children: ReactNode; permission?: Permission }) {
  const { user, loading, can } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner label="Loading session" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (permission && !can(permission)) {
    return (
      <div role="alert" className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-6 text-amber-100">
        <h2 className="font-semibold">Access restricted</h2>
        <p className="mt-1 text-sm">
          Your role ({user.role}) does not include the “{permission}” permission. Ask an administrator for access.
        </p>
      </div>
    );
  }
  return <>{children}</>;
}
