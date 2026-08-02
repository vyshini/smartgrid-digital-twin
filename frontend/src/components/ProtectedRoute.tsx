import { Navigate, Outlet } from 'react-router-dom';
import { useAppSelector } from '../hooks/useAppSelector';

export function ProtectedRoute() {
  const isAuthenticated = useAppSelector((s) => Boolean(s.auth.accessToken));
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
