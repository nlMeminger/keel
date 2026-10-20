import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import type { PaginatedResponse } from '../../lib/pagination'
import type { components } from '../../types/api'

export type Transaction = components['schemas']['TransactionPublic']
export type TransactionCreateInput = components['schemas']['TransactionCreateRequest']
export type TransactionUpdateInput = components['schemas']['TransactionUpdateRequest']

export interface TransactionFilters {
  account_id?: string
  category_id?: string
  description?: string
  date_from?: string
  date_to?: string
  pending?: boolean
  transfer_status?: string
  page?: number
}

function buildQuery(filters: TransactionFilters): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

export function useTransactions(filters: TransactionFilters = {}) {
  return useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => apiFetch<PaginatedResponse<Transaction>>(`/transactions${buildQuery(filters)}`),
  })
}

export function useCreateTransaction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: TransactionCreateInput) =>
      apiFetch<{ data: Transaction }>('/transactions', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['transactions'] }),
  })
}

export function useUpdateTransaction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: TransactionUpdateInput }) =>
      apiFetch<{ data: Transaction }>(`/transactions/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    // Confirming/rejecting a transfer updates the PAIRED transaction too, which this
    // response doesn't include — invalidate the whole list rather than setQueryData.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['transactions'] }),
  })
}

export function useDeleteTransaction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch(`/transactions/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['transactions'] }),
  })
}
