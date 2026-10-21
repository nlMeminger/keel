import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import { AccountDetailPage } from './AccountDetailPage'

function renderAccountDetailPage(accountId = 'a1') {
  return renderWithProviders(
    <MemoryRouter initialEntries={[`/accounts/${accountId}`]}>
      <Routes>
        <Route path="/accounts/:accountId" element={<AccountDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

const creditCard = {
  id: 'a1',
  name: 'Rewards Card',
  account_type: 'credit_card',
  balance: '250.00',
  detail: { credit_limit: 5000, apr: 19.99 },
  is_active: true,
  is_plaid_linked: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('AccountDetailPage', () => {
  it('shows account balance and type-specific detail fields', async () => {
    server.use(http.get('/api/v1/accounts/a1', () => HttpResponse.json({ data: creditCard })))
    renderAccountDetailPage()

    expect(await screen.findByRole('heading', { name: 'Rewards Card' })).toBeInTheDocument()
    expect(screen.getByText('250.00')).toBeInTheDocument()
    expect(screen.getByText('Credit limit: 5000')).toBeInTheDocument()
    expect(screen.getByText('APR (%): 19.99')).toBeInTheDocument()
  })

  it('links to transactions filtered to this account', async () => {
    server.use(http.get('/api/v1/accounts/a1', () => HttpResponse.json({ data: creditCard })))
    renderAccountDetailPage()

    const link = await screen.findByRole('link', { name: 'View transactions' })
    expect(link).toHaveAttribute('href', '/transactions?account_id=a1')
  })

  it('links a bank-linked account back to its bank', async () => {
    server.use(
      http.get('/api/v1/accounts/a1', () =>
        HttpResponse.json({
          data: { ...creditCard, is_plaid_linked: true, bank_id: 'bank-1' },
        }),
      ),
    )
    renderAccountDetailPage()

    const link = await screen.findByRole('link', { name: 'bank-linked' })
    expect(link).toHaveAttribute('href', '/banks/bank-1')
  })

  it('shows an unlinked bank-linked badge (no link) for an account whose bank was unlinked', async () => {
    server.use(
      http.get('/api/v1/accounts/a1', () =>
        HttpResponse.json({
          data: { ...creditCard, is_plaid_linked: true, bank_id: null },
        }),
      ),
    )
    renderAccountDetailPage()

    expect(await screen.findByText('bank-linked')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'bank-linked' })).not.toBeInTheDocument()
  })

  it("shows a not-found state for an id that doesn't belong to the user (or doesn't exist)", async () => {
    server.use(
      http.get('/api/v1/accounts/a1', () =>
        HttpResponse.json(
          { error: { code: 'not_found', message: 'Account not found.' } },
          { status: 404 },
        ),
      ),
    )
    renderAccountDetailPage()

    expect(await screen.findByText('Account not found.')).toBeInTheDocument()
  })
})
