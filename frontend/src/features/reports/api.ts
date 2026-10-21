import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../lib/api-client'
import type { PaginatedResponse } from '../../lib/pagination'
import type { components } from '../../types/api'

export type NetWorthHistoryPoint = components['schemas']['NetWorthHistoryPoint']
export type CashFlowPoint = components['schemas']['CashFlowPoint']
export type SpendingByCategoryRow = components['schemas']['SpendingByCategoryRow']
export type CreditHealthResponse = components['schemas']['CreditHealthResponse']
export type HoldingPerformance = components['schemas']['HoldingPerformance']

export function useNetWorthHistory() {
  return useQuery({
    queryKey: ['reports', 'net-worth-history'],
    queryFn: () =>
      apiFetch<PaginatedResponse<NetWorthHistoryPoint>>(
        '/reports/net-worth-history?granularity=month',
      ).then((r) => r.data),
  })
}

export function useCashFlow() {
  return useQuery({
    queryKey: ['reports', 'cash-flow'],
    queryFn: () =>
      apiFetch<PaginatedResponse<CashFlowPoint>>('/reports/cash-flow?granularity=month').then(
        (r) => r.data,
      ),
  })
}

export function useSpendingByCategory() {
  return useQuery({
    queryKey: ['reports', 'spending-by-category'],
    queryFn: () =>
      apiFetch<PaginatedResponse<SpendingByCategoryRow>>('/reports/spending-by-category').then(
        (r) => r.data,
      ),
  })
}

export function useCreditHealth() {
  return useQuery({
    queryKey: ['reports', 'credit-health'],
    queryFn: () =>
      apiFetch<{ data: CreditHealthResponse }>('/reports/credit-health?granularity=month').then(
        (r) => r.data,
      ),
  })
}

export function useInvestments() {
  return useQuery({
    queryKey: ['reports', 'investments'],
    queryFn: () =>
      apiFetch<PaginatedResponse<HoldingPerformance>>('/reports/investments').then((r) => r.data),
  })
}
