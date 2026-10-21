import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../../lib/api-client'
import type { PaginatedResponse } from '../../../lib/pagination'
import type { components } from '../../../types/api'

export type AuditLogEntry = components['schemas']['AdminAuditLogPublic']

export function useAuditLog(filters: { action?: string }) {
  const params = new URLSearchParams()
  if (filters.action) params.set('action', filters.action)
  const query = params.toString()

  return useQuery({
    queryKey: ['admin', 'audit-log', filters],
    queryFn: () =>
      apiFetch<PaginatedResponse<AuditLogEntry>>(
        `/admin/audit-log${query ? `?${query}` : ''}`,
      ).then((r) => r.data),
  })
}
