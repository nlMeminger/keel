import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AccountDetailPage } from '../accounts/AccountDetailPage'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import { BankDetailPage } from './BankDetailPage'

function renderBankDetailPage(bankId = 'b1') {
  return renderWithProviders(
    <MemoryRouter initialEntries={[`/banks/${bankId}`]}>
      <Routes>
        <Route path="/banks/:bankId" element={<BankDetailPage />} />
        <Route path="/accounts/:accountId" element={<AccountDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

const chase = {
  id: 'b1',
  institution_name: 'Chase',
  health: 'healthy' as const,
  last_synced_at: '2026-01-01T00:00:00Z',
  account_count: 1,
}

const checking = {
  id: 'a1',
  name: 'Chase Checking',
  account_type: 'checking',
  balance: '500.00',
  detail: {},
  is_active: true,
  is_plaid_linked: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('BankDetailPage', () => {
  it("shows the bank's header and only the accounts scoped to it", async () => {
    server.use(
      http.get('/api/v1/banks/b1', () => HttpResponse.json({ data: chase })),
      http.get('/api/v1/accounts', ({ request }) => {
        const url = new URL(request.url)
        expect(url.searchParams.get('bank_id')).toBe('b1')
        return HttpResponse.json({
          data: [checking],
          pagination: { page: 1, page_size: 25, total_count: 1, total_pages: 1 },
        })
      }),
    )
    renderBankDetailPage()

    expect(await screen.findByRole('heading', { name: 'Chase' })).toBeInTheDocument()
    expect(await screen.findByText('Chase Checking')).toBeInTheDocument()
  })

  it('shows a not-found state for a bank id that does not belong to the user (or does not exist)', async () => {
    server.use(
      http.get('/api/v1/banks/b1', () =>
        HttpResponse.json({ error: { code: 'not_found', message: 'Bank not found.' } }, { status: 404 }),
      ),
    )
    renderBankDetailPage()

    expect(await screen.findByText('Bank not found.')).toBeInTheDocument()
  })

  it('forwards to the account detail page when an account is clicked', async () => {
    server.use(
      http.get('/api/v1/banks/b1', () => HttpResponse.json({ data: chase })),
      http.get('/api/v1/accounts', () =>
        HttpResponse.json({
          data: [checking],
          pagination: { page: 1, page_size: 25, total_count: 1, total_pages: 1 },
        }),
      ),
      http.get('/api/v1/accounts/a1', () => HttpResponse.json({ data: checking })),
    )
    renderBankDetailPage()

    await userEvent.click(await screen.findByRole('link', { name: 'Chase Checking' }))

    expect(await screen.findByRole('heading', { name: 'Chase Checking' })).toBeInTheDocument()
    expect(await screen.findByText('bank-linked')).toBeInTheDocument()
  })
})
