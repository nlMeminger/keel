import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import type { PaginatedResponse } from '../../lib/pagination'
import type { components } from '../../types/api'

export type Merchant = components['schemas']['MerchantPublic']
export type MerchantCreateInput = components['schemas']['MerchantCreateRequest']
export type MerchantUpdateInput = components['schemas']['MerchantUpdateRequest']

export function useMerchants() {
  return useQuery({
    queryKey: ['merchants'],
    queryFn: () => apiFetch<PaginatedResponse<Merchant>>('/merchants').then((r) => r.data),
  })
}

export function useCreateMerchant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: MerchantCreateInput) =>
      apiFetch<{ data: Merchant }>('/merchants', { method: 'POST', body: JSON.stringify(input) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['merchants'] }),
  })
}

export function useUpdateMerchant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: MerchantUpdateInput }) =>
      apiFetch<{ data: Merchant }>(`/merchants/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['merchants'] }),
  })
}

export function useDeleteMerchant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch(`/merchants/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['merchants'] }),
  })
}
