import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import type { PaginatedResponse } from '../../lib/pagination'
import type { components } from '../../types/api'

export type Account = components['schemas']['AccountPublic']
export type AccountCreateInput = components['schemas']['AccountCreateRequest']
export type AccountUpdateInput = components['schemas']['AccountUpdateRequest']
export type Holding = components['schemas']['HoldingPublic']
export type HoldingCreateInput = components['schemas']['HoldingCreateRequest']
export type HoldingUpdateInput = components['schemas']['HoldingUpdateRequest']

export function useAccounts(
  filters: { type?: string; active?: boolean; bank_id?: string } = {},
) {
  const params = new URLSearchParams()
  if (filters.type) params.set('type', filters.type)
  if (filters.active !== undefined) params.set('active', String(filters.active))
  // bank_id isn't implemented server-side until Phase 7.3 (API_SPEC.md §4) — sending it is a
  // no-op against today's real backend, only the mocked tests for BankDetailPage honor it.
  if (filters.bank_id) params.set('bank_id', filters.bank_id)
  const query = params.toString()
  return useQuery({
    queryKey: ['accounts', filters],
    queryFn: () =>
      apiFetch<PaginatedResponse<Account>>(`/accounts${query ? `?${query}` : ''}`).then(
        (r) => r.data,
      ),
  })
}

export function useAccount(accountId: string) {
  return useQuery({
    queryKey: ['accounts', accountId],
    enabled: accountId !== '',
    queryFn: () => apiFetch<{ data: Account }>(`/accounts/${accountId}`).then((r) => r.data),
  })
}

export function useCreateAccount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: AccountCreateInput) =>
      apiFetch<{ data: Account }>('/accounts', { method: 'POST', body: JSON.stringify(input) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accounts'] }),
  })
}

export function useUpdateAccount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: AccountUpdateInput }) =>
      apiFetch<{ data: Account }>(`/accounts/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accounts'] }),
  })
}

export function useDeactivateAccount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch(`/accounts/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accounts'] }),
  })
}

export function useHoldings(accountId: string | null) {
  return useQuery({
    queryKey: ['holdings', accountId],
    enabled: accountId !== null,
    queryFn: () =>
      apiFetch<PaginatedResponse<Holding>>(`/accounts/${accountId}/holdings`).then((r) => r.data),
  })
}

export function useCreateHolding(accountId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: HoldingCreateInput) =>
      apiFetch<{ data: Holding }>(`/accounts/${accountId}/holdings`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['holdings', accountId] }),
  })
}

export function useUpdateHolding(accountId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: HoldingUpdateInput }) =>
      apiFetch<{ data: Holding }>(`/accounts/${accountId}/holdings/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['holdings', accountId] }),
  })
}

export function useDeleteHolding(accountId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/accounts/${accountId}/holdings/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['holdings', accountId] }),
  })
}
