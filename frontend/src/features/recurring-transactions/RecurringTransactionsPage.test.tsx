import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import { RecurringTransactionsPage } from './RecurringTransactionsPage'

function renderPage() {
  return renderWithProviders(<RecurringTransactionsPage />)
}

function pageOf(items: object[]) {
  return {
    data: items,
    pagination: { page: 1, page_size: 25, total_count: items.length, total_pages: 1 },
  }
}

const netflix = {
  id: 'rt1',
  name: 'Netflix',
  amount_expected: '15.99',
  frequency: 'monthly',
  account_id: null,
  category_id: null,
  merchant_id: null,
  next_due_date: null,
  last_paid_date: null,
  is_bill: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('RecurringTransactionsPage', () => {
  it('renders a recurring transaction with its cadence', async () => {
    server.use(
      http.get('/api/v1/recurring-transactions', () => HttpResponse.json(pageOf([netflix]))),
    )
    renderPage()

    const list = await screen.findByRole('list')
    expect(within(list).getByText('Netflix')).toBeInTheDocument()
    expect(within(list).getByText(/15.99 \/ monthly/)).toBeInTheDocument()
    expect(within(list).getByText(/last paid never/)).toBeInTheDocument()
  })

  it('creates a recurring transaction', async () => {
    let created = false
    server.use(
      http.get('/api/v1/recurring-transactions', () =>
        HttpResponse.json(pageOf(created ? [netflix] : [])),
      ),
      http.post('/api/v1/recurring-transactions', async ({ request }) => {
        const body = (await request.json()) as { name: string }
        expect(body.name).toBe('Netflix')
        created = true
        return HttpResponse.json({ data: netflix }, { status: 201 })
      }),
    )
    renderPage()

    await waitFor(() =>
      expect(screen.queryByText(/Loading recurring transactions/)).not.toBeInTheDocument(),
    )
    await userEvent.type(screen.getByLabelText('Name'), 'Netflix')
    await userEvent.type(screen.getByLabelText('Expected amount'), '15.99')
    await userEvent.click(screen.getByRole('button', { name: 'Add recurring transaction' }))

    const list = await screen.findByRole('list')
    expect(await within(list).findByText('Netflix')).toBeInTheDocument()
  })

  it('records a payment and reflects the new last_paid_date', async () => {
    const paid = { ...netflix, last_paid_date: '2026-01-05' }
    server.use(
      http.get('/api/v1/recurring-transactions', () => HttpResponse.json(pageOf([netflix]))),
      http.post('/api/v1/recurring-transactions/rt1/payments', () =>
        HttpResponse.json({ data: paid }, { status: 201 }),
      ),
    )
    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Record payment' }))

    expect(await screen.findByText(/last paid 2026-01-05/)).toBeInTheDocument()
  })

  it('removes a recurring transaction', async () => {
    let removed = false
    server.use(
      http.get('/api/v1/recurring-transactions', () =>
        HttpResponse.json(pageOf(removed ? [] : [netflix])),
      ),
      http.delete('/api/v1/recurring-transactions/rt1', () => {
        removed = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Remove' }))
    const list = screen.getByRole('list')
    await waitFor(() => expect(within(list).queryByText('Netflix')).not.toBeInTheDocument())
  })
})
