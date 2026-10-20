import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import type { PaginatedResponse } from '../../lib/pagination'
import type { components } from '../../types/api'

export type Goal = components['schemas']['SavingsGoalPublic']
export type GoalCreateInput = components['schemas']['SavingsGoalCreateRequest']
export type GoalContributionInput = components['schemas']['GoalContributionCreateRequest']

export function useGoals() {
  return useQuery({
    queryKey: ['goals'],
    queryFn: () => apiFetch<PaginatedResponse<Goal>>('/goals').then((r) => r.data),
  })
}

export function useCreateGoal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: GoalCreateInput) =>
      apiFetch<{ data: Goal }>('/goals', { method: 'POST', body: JSON.stringify(input) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['goals'] }),
  })
}

export function useDeleteGoal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch(`/goals/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['goals'] }),
  })
}

export function useAddContribution() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ goalId, input }: { goalId: string; input: GoalContributionInput }) =>
      apiFetch<{ data: Goal }>(`/goals/${goalId}/contributions`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    // The response already carries the updated goal with fresh progress — no need to
    // invalidate and refetch the whole list.
    onSuccess: (result) => {
      queryClient.setQueryData<Goal[]>(['goals'], (prev) =>
        prev ? prev.map((goal) => (goal.id === result.data.id ? result.data : goal)) : prev,
      )
    },
  })
}
