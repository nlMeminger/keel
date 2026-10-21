import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import { ReportsPage } from './ReportsPage'

function pageOf(items: object[]) {
  return {
    data: items,
    pagination: { page: 1, page_size: 25, total_count: items.length, total_pages: 1 },
  }
}

function mockAllReports() {
  server.use(
    http.get('/api/v1/reports/net-worth-history', () =>
      HttpResponse.json(pageOf([{ date: '2026-01-31', net_worth: '5800.00' }])),
    ),
    http.get('/api/v1/reports/cash-flow', () =>
      HttpResponse.json(
        pageOf([
          {
            period_start: '2026-01-01',
            period_end: '2026-01-31',
            inflow: '1000.00',
            outflow: '200.00',
          },
        ]),
      ),
    ),
    http.get('/api/v1/reports/spending-by-category', () =>
      HttpResponse.json(
        pageOf([{ category_id: 'c1', category_name: 'Groceries', total: '60.00' }]),
      ),
    ),
    http.get('/api/v1/reports/credit-health', () =>
      HttpResponse.json({
        data: {
          accounts: [
            {
              account_id: 'a1',
              name: 'Rewards card',
              balance: '250.00',
              credit_limit: '1000.0',
              utilization: '0.25',
            },
          ],
          overall_utilization: '0.25',
          credit_score_history: [{ date: '2026-01-31', value: '700.00' }],
        },
      }),
    ),
    http.get('/api/v1/reports/investments', () =>
      HttpResponse.json(
        pageOf([
          {
            id: 'h1',
            account_id: 'a2',
            symbol: 'VTI',
            name: 'Vanguard Total Market',
            quantity: '10',
            cost_basis: '2000.00',
            current_value: '2500.00',
            gain_loss: '500.00',
            source: 'manual',
          },
        ]),
      ),
    ),
  )
}

describe('ReportsPage', () => {
  it('renders real data for every report section', async () => {
    mockAllReports()
    renderWithProviders(<ReportsPage />)

    expect(await screen.findByText('5800.00')).toBeInTheDocument()
    expect(screen.getByText('1000.00')).toBeInTheDocument()
    expect(screen.getByText('Groceries')).toBeInTheDocument()
    expect(screen.getByText('Rewards card')).toBeInTheDocument()
    expect(screen.getByText('25%')).toBeInTheDocument()
    expect(screen.getByText('VTI')).toBeInTheDocument()
    expect(screen.getByText('500.00')).toBeInTheDocument()
  })

  it('renders empty states for a brand-new user without erroring', async () => {
    server.use(
      http.get('/api/v1/reports/net-worth-history', () => HttpResponse.json(pageOf([]))),
      http.get('/api/v1/reports/cash-flow', () => HttpResponse.json(pageOf([]))),
      http.get('/api/v1/reports/spending-by-category', () => HttpResponse.json(pageOf([]))),
      http.get('/api/v1/reports/credit-health', () =>
        HttpResponse.json({
          data: { accounts: [], overall_utilization: null, credit_score_history: [] },
        }),
      ),
      http.get('/api/v1/reports/investments', () => HttpResponse.json(pageOf([]))),
    )
    renderWithProviders(<ReportsPage />)

    expect(await screen.findByText('No history yet.')).toBeInTheDocument()
    expect(screen.getByText('No activity yet.')).toBeInTheDocument()
    expect(screen.getByText('No spending this month yet.')).toBeInTheDocument()
    expect(screen.getByText('No credit card accounts yet.')).toBeInTheDocument()
    expect(screen.getByText('No holdings yet.')).toBeInTheDocument()
  })
})
