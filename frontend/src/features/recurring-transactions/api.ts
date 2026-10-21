import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import type { PaginatedResponse } from '../../lib/pagination'
import type { components } from '../../types/api'

export type RecurringTransaction = components['schemas']['RecurringTransactionPublic']
export type RecurringTransactionCreateInput =
  components['schemas']['RecurringTransactionCreateRequest']
export type RecurringTransactionUpdateInput =
  components['schemas']['RecurringTransactionUpdateRequest']
export type RecurringTransactionPaymentInput =
  components['schemas']['RecurringTransactionPaymentCreateRequest']

export function useRecurringTransactions() {
  return useQuery({
    queryKey: ['recurring-transactions'],
    queryFn: () =>
      apiFetch<PaginatedResponse<RecurringTransaction>>('/recurring-transactions').then(
        (r) => r.data,
      ),
  })
}

export function useCreateRecurringTransaction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: RecurringTransactionCreateInput) =>
      apiFetch<{ data: RecurringTransaction }>('/recurring-transactions', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['recurring-transactions'] }),
  })
}

export function useUpdateRecurringTransaction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: RecurringTransactionUpdateInput }) =>
      apiFetch<{ data: RecurringTransaction }>(`/recurring-transactions/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['recurring-transactions'] }),
  })
}

export function useDeleteRecurringTransaction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch(`/recurring-transactions/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['recurring-transactions'] }),
  })
}

export function useRecordPayment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: RecurringTransactionPaymentInput }) =>
      apiFetch<{ data: RecurringTransaction }>(`/recurring-transactions/${id}/payments`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    // The response already carries the parent with a fresh last_paid_date.
    onSuccess: (result) => {
      queryClient.setQueryData<RecurringTransaction[]>(['recurring-transactions'], (prev) =>
        prev ? prev.map((row) => (row.id === result.data.id ? result.data : row)) : prev,
      )
    },
  })
}
