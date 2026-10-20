import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import { setAccessToken } from '../../lib/auth'
import type { SessionSummary, User } from './types'

export function useRegister() {
  return useMutation({
    mutationFn: (input: { email: string; password: string; name: string }) =>
      apiFetch<{ data: User }>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(input),
        skipAuthRetry: true,
      }),
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { email: string; password: string }) =>
      apiFetch<{ data: { access_token: string; user: User } }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(input),
        skipAuthRetry: true,
      }),
    onSuccess: (result) => {
      setAccessToken(result.data.access_token)
      queryClient.setQueryData(['me'], result.data.user)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/auth/logout', { method: 'POST' }),
    onSuccess: () => {
      setAccessToken(null)
      queryClient.clear()
    },
  })
}

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => apiFetch<{ data: User }>('/auth/me').then((r) => r.data),
  })
}

export function useUpdateMe() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { name?: string; timezone?: string }) =>
      apiFetch<{ data: User }>('/auth/me', { method: 'PATCH', body: JSON.stringify(input) }),
    onSuccess: (result) => queryClient.setQueryData(['me'], result.data),
  })
}

export function useSessions() {
  return useQuery({
    queryKey: ['sessions'],
    queryFn: () => apiFetch<{ data: SessionSummary[] }>('/auth/sessions').then((r) => r.data),
  })
}

export function useRevokeSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: string) =>
      apiFetch(`/auth/sessions/${sessionId}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  })
}

export function useRevokeOtherSessions() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/auth/sessions', { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  })
}
