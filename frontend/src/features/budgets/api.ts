import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import type { PaginatedResponse } from '../../lib/pagination'
import type { components } from '../../types/api'

export type Budget = components['schemas']['BudgetPublic']
export type BudgetCreateInput = components['schemas']['BudgetCreateRequest']
export type BudgetUpdateInput = components['schemas']['BudgetUpdateRequest']

export function useBudgets() {
  return useQuery({
    queryKey: ['budgets'],
    queryFn: () => apiFetch<PaginatedResponse<Budget>>('/budgets').then((r) => r.data),
  })
}

export function useCreateBudget() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: BudgetCreateInput) =>
      apiFetch<{ data: Budget }>('/budgets', { method: 'POST', body: JSON.stringify(input) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['budgets'] }),
  })
}

export function useUpdateBudget() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: BudgetUpdateInput }) =>
      apiFetch<{ data: Budget }>(`/budgets/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['budgets'] }),
  })
}

export function useDeleteBudget() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch(`/budgets/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['budgets'] }),
  })
}
