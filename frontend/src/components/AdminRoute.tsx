import { Navigate, Outlet } from 'react-router-dom'
import { useMe } from '../features/auth/api'

// Nested inside ProtectedRoute, so we already know the user is authenticated by the time
// this renders — this only adds the role check. The backend enforces the real boundary
// (app.admin.dependencies.require_admin); this just keeps a non-admin out of the UI for it.
export function AdminRoute() {
  const { data: user, isLoading } = useMe()

  if (isLoading || !user) {
    return <p>Loading…</p>
  }
  if (user.role !== 'admin') {
    return <Navigate to="/" replace />
  }
  return <Outlet />
}
