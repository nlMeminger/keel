import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStatus } from '../features/auth/auth-status-context'

export function ProtectedRoute() {
  const status = useAuthStatus()

  if (status === 'loading') {
    return <p>Loading…</p>
  }
  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}
