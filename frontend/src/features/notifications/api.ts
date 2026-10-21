import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import type { PaginatedResponse } from '../../lib/pagination'
import type { components } from '../../types/api'

export type Notification = components['schemas']['NotificationPublic']

export function useNotifications(unreadOnly = false) {
  return useQuery({
    queryKey: ['notifications', unreadOnly],
    queryFn: () =>
      apiFetch<PaginatedResponse<Notification>>(
        `/notifications${unreadOnly ? '?unread_only=true' : ''}`,
      ).then((r) => r.data),
  })
}

export function useSetNotificationRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, read }: { id: string; read: boolean }) =>
      apiFetch<{ data: Notification }>(`/notifications/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ read }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })
}

export function useDismissNotification() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch(`/notifications/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })
}
