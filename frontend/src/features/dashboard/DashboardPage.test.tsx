import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import { DashboardPage } from './DashboardPage'

const summary = {
  net_worth: '800.00',
  net_worth_delta: '50.00',
  this_month_inflow: '300.00',
  this_month_outflow: '50.00',
  recent_transactions: [
    {
      id: 't1',
      account_id: 'a1',
      category_id: null,
      merchant_id: null,
      amount: '-50.00',
      description: 'Groceries',
      notes: null,
      date: '2026-01-05',
      pending: false,
      is_transfer: false,
      paired_transaction_id: null,
      transfer_status: 'none',
      created_at: '2026-01-05T00:00:00Z',
      updated_at: '2026-01-05T00:00:00Z',
    },
  ],
  budgets: [
    {
      id: 'b1',
      category_id: null,
      amount_limit: '500.00',
      period: 'monthly',
      start_date: '2026-01-01',
      spend_so_far: '50.00',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
  latest_credit_score: { value: '710.00', date: '2026-01-01', trend: 'up' },
}

describe('DashboardPage', () => {
  it('renders net worth, cash flow, budgets, recent transactions, and credit score', async () => {
    server.use(http.get('/api/v1/dashboard/summary', () => HttpResponse.json({ data: summary })))
    renderWithProviders(<DashboardPage />)

    expect(await screen.findByText('800.00')).toBeInTheDocument()
    expect(screen.getByText('300.00')).toBeInTheDocument()
    expect(screen.getByText(/50.00 of 500.00 spent/)).toBeInTheDocument()
    expect(screen.getByText('Groceries')).toBeInTheDocument()
    expect(screen.getByText('710.00')).toBeInTheDocument()
  })

  it('renders a sensible empty state for a brand-new user, not undefined/broken UI', async () => {
    server.use(
      http.get('/api/v1/dashboard/summary', () =>
        HttpResponse.json({
          data: {
            net_worth: '0',
            net_worth_delta: '0',
            this_month_inflow: '0',
            this_month_outflow: '0',
            recent_transactions: [],
            budgets: [],
            latest_credit_score: null,
          },
        }),
      ),
    )
    renderWithProviders(<DashboardPage />)

    expect(await screen.findByText('No budgets yet.')).toBeInTheDocument()
    expect(screen.getByText('No transactions yet.')).toBeInTheDocument()
  })
})
