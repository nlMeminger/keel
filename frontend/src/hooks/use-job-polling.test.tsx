import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../test/render'
import { server } from '../test/mocks/server'
import { computeRefetchInterval, useJobPolling, type JobStatus } from './use-job-polling'

describe('computeRefetchInterval', () => {
  it('polls every 2s while pending/running under 30s elapsed', () => {
    expect(computeRefetchInterval(0, 'pending')).toBe(2_000)
    expect(computeRefetchInterval(29_999, 'running')).toBe(2_000)
  })

  it('backs off to 10s once past 30s elapsed', () => {
    expect(computeRefetchInterval(30_001, 'running')).toBe(10_000)
  })

  it('stops polling once the status is terminal', () => {
    expect(computeRefetchInterval(0, 'succeeded')).toBe(false)
    expect(computeRefetchInterval(0, 'failed')).toBe(false)
  })

  it('does not poll before any status is known', () => {
    expect(computeRefetchInterval(0, undefined)).toBe(false)
  })
})

function job(overrides: Partial<JobStatus>): JobStatus {
  return {
    id: 'job-1',
    type: 'bulk_import',
    status: 'running',
    progress: null,
    started_at: null,
    finished_at: null,
    error: null,
    ...overrides,
  }
}

function JobStatusHarness({ jobId }: { jobId: string }) {
  const { data } = useJobPolling(jobId)
  return <p>status: {data?.status ?? 'loading'}</p>
}

function renderHarness(jobId: string) {
  return renderWithProviders(<JobStatusHarness jobId={jobId} />)
}

describe('useJobPolling', () => {
  it('shows a live in-progress state, then clears itself at the terminal state without a tight poll loop', async () => {
    let callCount = 0
    server.use(
      http.get('/api/v1/sync/jobs/job-1', () => {
        callCount += 1
        return HttpResponse.json({
          data: callCount < 2 ? job({ status: 'running' }) : job({ status: 'succeeded' }),
        })
      }),
    )

    renderHarness('job-1')

    await waitFor(() => expect(screen.getByText('status: running')).toBeInTheDocument())
    expect(callCount).toBe(1)

    // The 2s poll interval fires with real timers — a genuine round trip, not simulated time.
    await waitFor(() => expect(screen.getByText('status: succeeded')).toBeInTheDocument(), {
      timeout: 4_000,
    })
    expect(callCount).toBe(2)

    const countAtTerminal = callCount
    await new Promise((resolve) => setTimeout(resolve, 2_500))
    expect(callCount).toBe(countAtTerminal)
  }, 8_000)
})
