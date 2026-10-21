import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/api-client'
import { useJobPolling } from '../../hooks/use-job-polling'
import type { PaginatedResponse } from '../../lib/pagination'

// Hand-written, not generated from types/api.ts: the backend has no /banks routes yet
// (ROADMAP.md Phase 7.1-7.3). Swap these for `components['schemas'][...]` once those land
// and `npm run generate:types` picks up the real schemas.
export type BankHealth = 'healthy' | 'needs_reauth' | 'error'

export interface Bank {
  id: string
  institution_name: string
  health: BankHealth
  last_synced_at: string | null
  account_count: number
}

export function useBanks() {
  return useQuery({
    queryKey: ['banks'],
    queryFn: () => apiFetch<PaginatedResponse<Bank>>('/banks').then((r) => r.data),
  })
}

export function useBank(bankId: string) {
  return useQuery({
    queryKey: ['banks', bankId],
    enabled: bankId !== '',
    queryFn: () => apiFetch<{ data: Bank }>(`/banks/${bankId}`).then((r) => r.data),
  })
}

export function useSyncBank() {
  return useMutation({
    mutationFn: (bankId: string) =>
      apiFetch<{ data: { id: string } }>(`/banks/${bankId}/sync`, { method: 'POST' }).then(
        (r) => r.data,
      ),
  })
}

export function useUnlinkBank() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (bankId: string) => apiFetch(`/banks/${bankId}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['banks'] }),
  })
}

/** Triggers a bank sync, polls the returned job via the shared job-polling contract
 * (API_SPEC.md §16), and refreshes the bank list once it completes. Shared between BanksPage's
 * per-row sync button and BankDetailPage's header sync button so the polling/invalidation logic
 * lives in one place. */
export function useBankSync(bankId: string) {
  const queryClient = useQueryClient()
  const syncBank = useSyncBank()
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJobPolling(jobId)

  useEffect(() => {
    if (job.data?.status === 'succeeded') {
      queryClient.invalidateQueries({ queryKey: ['banks'] })
      setJobId(null)
    }
  }, [job.data?.status, queryClient])

  const isPolling = jobId !== null && job.data?.status !== 'succeeded' && job.data?.status !== 'failed'

  return {
    sync: () => syncBank.mutate(bankId, { onSuccess: (data) => setJobId(data.id) }),
    isSyncing: syncBank.isPending || isPolling,
    syncError: job.data?.status === 'failed' ? (job.data.error ?? 'Sync failed.') : null,
  }
}
