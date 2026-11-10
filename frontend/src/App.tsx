import { Link, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';
import { AccountsPage } from './pages/AccountsPage';
import { ActivityPage } from './pages/ActivityPage';
import { CostsPage } from './pages/CostsPage';
import { InfrastructurePage } from './pages/InfrastructurePage';
import { LoginPage, RegisterPage } from './pages/LoginPage';
import { MonitoringPage } from './pages/MonitoringPage';
import { OverviewPage } from './pages/OverviewPage';
import { ResourcesPage } from './pages/ResourcesPage';
import { SettingsPage } from './pages/SettingsPage';

function NotFound() {
  return (
    <div className="py-20 text-center">
      <p className="text-sm font-semibold text-orbit-300">404</p>
      <h1 className="mt-2 text-2xl font-semibold text-ink">Page not found</h1>
      <Link to="/" className="mt-4 inline-block text-sm text-orbit-300 hover:text-orbit-200">
        Back to overview
      </Link>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<OverviewPage />} />
        <Route path="accounts" element={<ProtectedRoute permission="accounts:read"><AccountsPage /></ProtectedRoute>} />
        <Route path="resources" element={<ProtectedRoute permission="resources:read"><ResourcesPage /></ProtectedRoute>} />
        <Route path="infrastructure" element={<ProtectedRoute permission="infra:read"><InfrastructurePage /></ProtectedRoute>} />
        <Route path="costs" element={<ProtectedRoute permission="costs:read"><CostsPage /></ProtectedRoute>} />
        <Route path="monitoring" element={<ProtectedRoute permission="resources:read"><MonitoringPage /></ProtectedRoute>} />
        <Route path="activity" element={<ActivityPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
