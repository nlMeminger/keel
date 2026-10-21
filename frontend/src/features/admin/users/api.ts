import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../../lib/api-client'
import type { PaginatedResponse } from '../../../lib/pagination'
import type { components } from '../../../types/api'

export type AdminUser = components['schemas']['AdminUserPublic']
type UserUpdateInput = components['schemas']['AdminUserUpdateRequest']
type PlaidAccessInput = components['schemas']['AdminPlaidAccessUpdateRequest']

export function useAdminUsers(filters: { role?: string; status?: string }) {
  const params = new URLSearchParams()
  if (filters.role) params.set('role', filters.role)
  if (filters.status) params.set('status', filters.status)
  const query = params.toString()

  return useQuery({
    queryKey: ['admin', 'users', filters],
    queryFn: () =>
      apiFetch<PaginatedResponse<AdminUser>>(`/admin/users${query ? `?${query}` : ''}`).then(
        (r) => r.data,
      ),
  })
}

export function useAdminUser(userId: string) {
  return useQuery({
    queryKey: ['admin', 'users', userId],
    queryFn: () => apiFetch<{ data: AdminUser }>(`/admin/users/${userId}`).then((r) => r.data),
  })
}

export function useUpdateAdminUser(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: UserUpdateInput) =>
      apiFetch<{ data: AdminUser }>(`/admin/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })
}

export function useUpdatePlaidAccess(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: PlaidAccessInput) =>
      apiFetch<{ data: AdminUser }>(`/admin/users/${userId}/plaid-access`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })
}

export function useResetPassword(userId: string) {
  return useMutation({
    mutationFn: (password?: string) =>
      apiFetch<{ data: components['schemas']['AdminResetPasswordResponseData'] }>(
        `/admin/users/${userId}/reset-password`,
        { method: 'POST', body: JSON.stringify({ password: password ?? null }) },
      ).then((r) => r.data),
  })
}

export function useRevokeSessions(userId: string) {
  return useMutation({
    mutationFn: () => apiFetch(`/admin/users/${userId}/revoke-sessions`, { method: 'POST' }),
  })
}

export function useDeleteAdminUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) =>
      apiFetch(`/admin/users/${userId}`, {
        method: 'DELETE',
        body: JSON.stringify({ confirm: true }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })
}
