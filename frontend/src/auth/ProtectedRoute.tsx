import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Spinner } from '../components/ui/Spinner';
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
      <div role="alert" className="m-8 rounded-lg border border-amber-200 bg-amber-50 p-6 text-amber-900">
        <h2 className="font-semibold">Access restricted</h2>
        <p className="mt-1 text-sm">Your role ({user.role}) does not include the “{permission}” permission.</p>
      </div>
    );
  }
  return <>{children}</>;
}
