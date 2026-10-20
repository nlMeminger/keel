import { createContext, useContext } from 'react'

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

export const AuthStatusContext = createContext<AuthStatus>('loading')

export function useAuthStatus(): AuthStatus {
  return useContext(AuthStatusContext)
}
