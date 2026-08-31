import { Navigate, useLocation } from 'react-router-dom';
import { HOME_FOR_ROLE, useAuth } from '../context/AuthContext';
import { Spinner } from './Ui';

/**
 * Client-side route guards.
 *
 * These are a convenience that keeps the UI coherent; the real access control
 * is enforced by the FastAPI role dependencies on every request.
 */
export function RequireAuth({ role, children }) {
  const { isAuthenticated, loading, user } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
        <Spinner label="Restoring your session" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (role && user.role !== role) {
    return <Navigate to={HOME_FOR_ROLE[user.role] || '/home'} replace />;
  }

  return children;
}

/** Sends an already-signed-in visitor to their own portal. */
export function RedirectIfAuthenticated({ children }) {
  const { isAuthenticated, loading, user } = useAuth();
  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
        <Spinner label="Loading" />
      </div>
    );
  }
  if (isAuthenticated) {
    return <Navigate to={HOME_FOR_ROLE[user.role] || '/home'} replace />;
  }
  return children;
}
