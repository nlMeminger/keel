import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import type { Bank } from './api'
import { BankDetailPage } from './BankDetailPage'
import { BanksPage } from './BanksPage'

// react-plaid-link loads Plaid's own embed script and iframe — nothing jsdom can run, and
// no network call MSW could intercept at the API boundary. Stubbed here, driven through its
// onSuccess callback to simulate a user completing Plaid's real Link UI; every actual
// backend call it triggers (link-token, exchange-token) still goes through MSW below.
let capturedOnSuccess: ((publicToken: string) => void) | null = null
const openLinkMock = vi.fn()
vi.mock('react-plaid-link', () => ({
  usePlaidLink: (opts: { token: string; onSuccess: (publicToken: string) => void }) => {
    capturedOnSuccess = opts.onSuccess
    return { open: openLinkMock, ready: opts.token !== '' }
  },
}))

function renderBanksPage() {
  return renderWithProviders(
    <MemoryRouter initialEntries={['/banks']}>
      <Routes>
        <Route path="/banks" element={<BanksPage />} />
        <Route path="/banks/:bankId" element={<BankDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

const chase: Bank = {
  id: 'b1',
  institution_name: 'Chase',
  health: 'healthy',
  last_synced_at: '2026-01-01T00:00:00Z',
  account_count: 2,
}

function banksResponse(banks: Bank[]) {
  return {
    data: banks,
    pagination: { page: 1, page_size: 25, total_count: banks.length, total_pages: 1 },
  }
}

describe('BanksPage', () => {
  it('lists linked banks with health, account count, and last sync', async () => {
    server.use(http.get('/api/v1/banks', () => HttpResponse.json(banksResponse([chase]))))
    renderBanksPage()

    expect(await screen.findByText('Chase')).toBeInTheDocument()
    expect(screen.getByText('Healthy')).toBeInTheDocument()
    expect(screen.getByText(/2 accounts/)).toBeInTheDocument()
  })

  it('shows a distinct state for a bank needing reauth', async () => {
    server.use(
      http.get('/api/v1/banks', () =>
        HttpResponse.json(banksResponse([{ ...chase, health: 'needs_reauth' }])),
      ),
    )
    renderBanksPage()

    expect(await screen.findByText('Needs reauth')).toBeInTheDocument()
  })

  it('shows an empty state with no linked banks', async () => {
    server.use(http.get('/api/v1/banks', () => HttpResponse.json(banksResponse([]))))
    renderBanksPage()

    expect(await screen.findByText('No banks linked yet.')).toBeInTheDocument()
  })

  it('shows an error state instead of hanging when the list fails to load', async () => {
    server.use(
      http.get('/api/v1/banks', () =>
        HttpResponse.json({ error: { code: 'x', message: 'x' } }, { status: 500 }),
      ),
    )
    renderBanksPage()

    expect(await screen.findByText('Failed to load banks.')).toBeInTheDocument()
  })

  it('navigates to the bank detail page when a bank is clicked', async () => {
    server.use(
      http.get('/api/v1/banks', () => HttpResponse.json(banksResponse([chase]))),
      http.get('/api/v1/banks/b1', () => HttpResponse.json({ data: chase })),
      http.get('/api/v1/accounts', () =>
        HttpResponse.json({
          data: [],
          pagination: { page: 1, page_size: 25, total_count: 0, total_pages: 1 },
        }),
      ),
    )
    renderBanksPage()

    await userEvent.click(await screen.findByRole('link', { name: 'Chase' }))

    expect(await screen.findByRole('heading', { name: 'Chase' })).toBeInTheDocument()
    expect(await screen.findByText('No accounts pulled for this bank yet.')).toBeInTheDocument()
  })

  it('unlinking a bank removes it from the list', async () => {
    let unlinked = false
    server.use(
      http.get('/api/v1/banks', () => HttpResponse.json(banksResponse(unlinked ? [] : [chase]))),
      http.delete('/api/v1/banks/b1', () => {
        unlinked = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderBanksPage()

    expect(await screen.findByText('Chase')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Unlink' }))

    await waitFor(() => expect(screen.queryByText('Chase')).not.toBeInTheDocument())
  })

  it('syncing a bank polls the job to completion and refreshes the last-synced time', async () => {
    let jobCallCount = 0
    let synced = false
    server.use(
      http.get('/api/v1/banks', () =>
        HttpResponse.json(
          banksResponse([{ ...chase, last_synced_at: synced ? '2026-02-01T00:00:00Z' : null }]),
        ),
      ),
      http.post('/api/v1/banks/b1/sync', () =>
        HttpResponse.json({ data: { id: 'job-1' } }, { status: 202 }),
      ),
      http.get('/api/v1/sync/jobs/job-1', () => {
        jobCallCount += 1
        if (jobCallCount < 2) {
          return HttpResponse.json({
            data: {
              id: 'job-1',
              type: 'balance_sync',
              status: 'running',
              progress: null,
              started_at: '2026-02-01T00:00:00Z',
              finished_at: null,
              error: null,
            },
          })
        }
        synced = true
        return HttpResponse.json({
          data: {
            id: 'job-1',
            type: 'balance_sync',
            status: 'succeeded',
            progress: null,
            started_at: '2026-02-01T00:00:00Z',
            finished_at: '2026-02-01T00:00:05Z',
            error: null,
          },
        })
      }),
    )
    renderBanksPage()

    expect(await screen.findByText(/never synced/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Sync now' }))

    await waitFor(() => expect(screen.getByText(/last synced/)).toBeInTheDocument(), {
      timeout: 4_000,
    })
  }, 8_000)

  it('a failed sync surfaces an error instead of a spinner that never resolves', async () => {
    server.use(
      http.get('/api/v1/banks', () => HttpResponse.json(banksResponse([chase]))),
      http.post('/api/v1/banks/b1/sync', () =>
        HttpResponse.json({ data: { id: 'job-2' } }, { status: 202 }),
      ),
      http.get('/api/v1/sync/jobs/job-2', () =>
        HttpResponse.json({
          data: {
            id: 'job-2',
            type: 'balance_sync',
            status: 'failed',
            progress: null,
            started_at: '2026-02-01T00:00:00Z',
            finished_at: '2026-02-01T00:00:05Z',
            error: 'Plaid item revoked.',
          },
        }),
      ),
    )
    renderBanksPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Sync now' }))

    expect(await screen.findByText('Plaid item revoked.')).toBeInTheDocument()
  }, 8_000)

  it('linking a bank fetches a Link token, opens Plaid Link, and shows the new bank on success', async () => {
    let linked = false
    server.use(
      http.get('/api/v1/banks', () => HttpResponse.json(banksResponse(linked ? [chase] : []))),
      http.post('/api/v1/plaid/link-token', () =>
        HttpResponse.json({
          data: { link_token: 'link-sandbox-abc', expiration: '2026-01-01T00:00:00Z' },
        }),
      ),
      http.post('/api/v1/plaid/exchange-token', async ({ request }) => {
        const body = (await request.json()) as { public_token: string }
        expect(body.public_token).toBe('public-sandbox-xyz')
        linked = true
        return HttpResponse.json({ data: chase })
      }),
    )
    renderBanksPage()

    expect(await screen.findByText('No banks linked yet.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Link a bank' }))

    await waitFor(() => expect(openLinkMock).toHaveBeenCalled())
    capturedOnSuccess?.('public-sandbox-xyz')

    expect(await screen.findByText('Chase')).toBeInTheDocument()
  })

  it('shows an error if starting the Link flow fails', async () => {
    server.use(
      http.get('/api/v1/banks', () => HttpResponse.json(banksResponse([]))),
      http.post('/api/v1/plaid/link-token', () =>
        HttpResponse.json({ error: { code: 'plaid_disabled', message: 'x' } }, { status: 403 }),
      ),
    )
    renderBanksPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Link a bank' }))

    expect(await screen.findByText('Failed to start linking a bank.')).toBeInTheDocument()
  })
})
