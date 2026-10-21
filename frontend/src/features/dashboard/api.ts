import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import type { components } from '../../types/api'

export type DashboardSummary = components['schemas']['DashboardSummary']

export function useDashboardSummary() {
  return useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: () => apiFetch<{ data: DashboardSummary }>('/dashboard/summary').then((r) => r.data),
  })
}
