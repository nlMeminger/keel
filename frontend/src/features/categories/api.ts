import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import type { PaginatedResponse } from '../../lib/pagination'
import type { components } from '../../types/api'

export type Category = components['schemas']['CategoryPublic']
export type CategoryCreateInput = components['schemas']['CategoryCreateRequest']
export type CategoryUpdateInput = components['schemas']['CategoryUpdateRequest']

export function useCategories(scope: 'system' | 'custom' | 'all' = 'all') {
  return useQuery({
    queryKey: ['categories', scope],
    queryFn: () =>
      apiFetch<PaginatedResponse<Category>>(`/categories?scope=${scope}`).then((r) => r.data),
  })
}

export function useCreateCategory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CategoryCreateInput) =>
      apiFetch<{ data: Category }>('/categories', { method: 'POST', body: JSON.stringify(input) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['categories'] }),
  })
}

export function useUpdateCategory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: CategoryUpdateInput }) =>
      apiFetch<{ data: Category }>(`/categories/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['categories'] }),
  })
}

export function useDeleteCategory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reassignTo }: { id: string; reassignTo?: string }) =>
      apiFetch(`/categories/${id}${reassignTo ? `?reassign_to=${reassignTo}` : ''}`, {
        method: 'DELETE',
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['categories'] }),
  })
}
