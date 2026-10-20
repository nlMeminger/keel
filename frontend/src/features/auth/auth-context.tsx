import { useEffect, useState, type ReactNode } from 'react'
import { refreshAccessToken } from '../../lib/api-client'
import { getAccessToken, subscribeToAccessToken } from '../../lib/auth'
import { AuthStatusContext, type AuthStatus } from './auth-status-context'

/** Attempts a silent refresh on mount so a reload doesn't force a re-login while the
 * httpOnly refresh cookie is still valid, then tracks token presence afterward. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')

  useEffect(() => {
    let active = true
    void refreshAccessToken().then((ok) => {
      if (active) setStatus(ok ? 'authenticated' : 'unauthenticated')
    })
    const unsubscribe = subscribeToAccessToken(() => {
      setStatus(getAccessToken() ? 'authenticated' : 'unauthenticated')
    })
    return () => {
      active = false
      unsubscribe()
    }
  }, [])

  return <AuthStatusContext.Provider value={status}>{children}</AuthStatusContext.Provider>
}
