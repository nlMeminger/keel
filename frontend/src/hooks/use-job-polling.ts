import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { apiFetch } from '../lib/api-client'

export interface JobProgress {
  current: number
  total: number
}

export type JobRunStatus = 'pending' | 'running' | 'succeeded' | 'failed'

export interface JobStatus {
  id: string
  type: string
  status: JobRunStatus
  progress: JobProgress | null
  started_at: string | null
  finished_at: string | null
  error: string | null
}

const TERMINAL_STATUSES: ReadonlySet<JobRunStatus> = new Set(['succeeded', 'failed'])
const FAST_INTERVAL_MS = 2_000
const SLOW_INTERVAL_MS = 10_000
const BACKOFF_AFTER_MS = 30_000

/** 2s while in flight, backs off to 10s past 30s elapsed, stops once terminal — matches the
 * polling contract every job-returning action shares (API_SPEC.md §16). */
export function computeRefetchInterval(
  elapsedMs: number,
  status: JobRunStatus | undefined,
): number | false {
  if (status === undefined || TERMINAL_STATUSES.has(status)) {
    return false
  }
  return elapsedMs > BACKOFF_AFTER_MS ? SLOW_INTERVAL_MS : FAST_INTERVAL_MS
}

/** Polls a job-returning action's status until it reaches a terminal state. Pass the job id
 * returned by whichever action triggered it; pass null when there's nothing to poll. */
export function useJobPolling(jobId: string | null) {
  const startedAtRef = useRef<number | null>(null)

  useEffect(() => {
    startedAtRef.current = jobId !== null ? Date.now() : null
  }, [jobId])

  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => apiFetch<{ data: JobStatus }>(`/sync/jobs/${jobId}`).then((r) => r.data),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const elapsed = Date.now() - (startedAtRef.current ?? Date.now())
      return computeRefetchInterval(elapsed, query.state.data?.status)
    },
  })
}
