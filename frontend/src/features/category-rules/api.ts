import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import type { PaginatedResponse } from '../../lib/pagination'
import type { components } from '../../types/api'

export type CategoryRule = components['schemas']['CategoryRulePublic']
export type CategoryRuleCreateInput = components['schemas']['CategoryRuleCreateRequest']
export type CategoryRuleUpdateInput = components['schemas']['CategoryRuleUpdateRequest']
export type CategoryRuleConditions = components['schemas']['CategoryRuleConditions']
export type TransactionMatch = components['schemas']['TransactionMatchPublic']

export function useCategoryRules() {
  return useQuery({
    queryKey: ['category-rules'],
    queryFn: () => apiFetch<PaginatedResponse<CategoryRule>>('/category-rules').then((r) => r.data),
  })
}

export function useCreateCategoryRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CategoryRuleCreateInput) =>
      apiFetch<{ data: CategoryRule }>('/category-rules', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['category-rules'] }),
  })
}

export function useUpdateCategoryRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: CategoryRuleUpdateInput }) =>
      apiFetch<{ data: CategoryRule }>(`/category-rules/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['category-rules'] }),
  })
}

export function useDeleteCategoryRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch(`/category-rules/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['category-rules'] }),
  })
}

export function useTestCategoryRule() {
  return useMutation({
    mutationFn: (conditions: CategoryRuleConditions) =>
      apiFetch<{ data: { matches: TransactionMatch[] } }>('/category-rules/test', {
        method: 'POST',
        body: JSON.stringify(conditions),
      }).then((r) => r.data.matches),
  })
}

export function useApplyCategoryRules() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<{ data: { job_id: string } }>('/category-rules/apply', {
        method: 'POST',
      }).then((r) => r.data.job_id),
    // Transactions may have been recategorized — the list elsewhere in the app shouldn't
    // show stale category_id values once the job completes.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['transactions'] }),
  })
}
