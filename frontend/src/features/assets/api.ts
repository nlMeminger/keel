import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import type { PaginatedResponse } from '../../lib/pagination'
import type { components } from '../../types/api'

export type Asset = components['schemas']['AssetPublic']
export type AssetCreateInput = components['schemas']['AssetCreateRequest']
export type AssetUpdateInput = components['schemas']['AssetUpdateRequest']

export function useAssets() {
  return useQuery({
    queryKey: ['assets'],
    queryFn: () => apiFetch<PaginatedResponse<Asset>>('/assets').then((r) => r.data),
  })
}

export function useCreateAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: AssetCreateInput) =>
      apiFetch<{ data: Asset }>('/assets', { method: 'POST', body: JSON.stringify(input) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['assets'] }),
  })
}

export function useUpdateAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: AssetUpdateInput }) =>
      apiFetch<{ data: Asset }>(`/assets/${id}`, { method: 'PATCH', body: JSON.stringify(input) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['assets'] }),
  })
}

export function useDeleteAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch(`/assets/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['assets'] }),
  })
}
