import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import { TransactionsPage } from './TransactionsPage'

function renderTransactionsPage(initialPath = '/transactions') {
  return renderWithProviders(
    <MemoryRouter initialEntries={[initialPath]}>
      <TransactionsPage />
    </MemoryRouter>,
  )
}

function pageOf(items: object[]) {
  return {
    data: items,
    pagination: { page: 1, page_size: 25, total_count: items.length, total_pages: 1 },
  }
}

const account = {
  id: 'a1',
  name: 'Checking',
  account_type: 'checking',
  balance: '0',
  detail: {},
  is_active: true,
  is_plaid_linked: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const groceries = {
  id: 'cat1',
  owner_id: null,
  primary_category: 'Groceries',
  detailed_category: null,
  icon: null,
  color: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const txn = {
  id: 't1',
  account_id: 'a1',
  category_id: 'cat1',
  merchant_id: null,
  amount: '-45.00',
  description: 'Groceries run',
  notes: null,
  date: '2026-01-10',
  pending: false,
  is_transfer: false,
  paired_transaction_id: null,
  transfer_status: 'none',
  created_at: '2026-01-10T00:00:00Z',
  updated_at: '2026-01-10T00:00:00Z',
}

function setupBaseHandlers(transactions: object[], suggested: object[] = []) {
  server.use(
    http.get('/api/v1/accounts', () => HttpResponse.json(pageOf([account]))),
    http.get('/api/v1/categories', () => HttpResponse.json(pageOf([groceries]))),
    http.get('/api/v1/transactions', ({ request }) => {
      const status = new URL(request.url).searchParams.get('transfer_status')
      return HttpResponse.json(pageOf(status === 'suggested' ? suggested : transactions))
    }),
  )
}

describe('TransactionsPage', () => {
  it('lists transactions with resolved category name', async () => {
    setupBaseHandlers([txn])
    renderTransactionsPage()

    expect(await screen.findByText(/Groceries run/)).toBeInTheDocument()
    expect(screen.getByText(/\(Groceries\)/)).toBeInTheDocument()
  })

  it('shows suggested transfers with confirm/reject controls', async () => {
    const suggestedTxn = {
      ...txn,
      id: 't2',
      transfer_status: 'suggested',
      description: 'Transfer out',
    }
    setupBaseHandlers([], [suggestedTxn])
    renderTransactionsPage()

    expect(await screen.findByText(/Transfer out/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm transfer' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Not a transfer' })).toBeInTheDocument()
  })

  it('confirming a suggested transfer updates the list without a manual reload', async () => {
    const suggestedTxn = {
      ...txn,
      id: 't2',
      transfer_status: 'suggested',
      description: 'Transfer out',
    }
    let confirmed = false
    server.use(
      http.get('/api/v1/accounts', () => HttpResponse.json(pageOf([account]))),
      http.get('/api/v1/categories', () => HttpResponse.json(pageOf([groceries]))),
      http.get('/api/v1/transactions', ({ request }) => {
        const status = new URL(request.url).searchParams.get('transfer_status')
        if (status === 'suggested') {
          return HttpResponse.json(pageOf(confirmed ? [] : [suggestedTxn]))
        }
        return HttpResponse.json(pageOf([]))
      }),
      http.patch('/api/v1/transactions/t2', () => {
        confirmed = true
        return HttpResponse.json({ data: { ...suggestedTxn, transfer_status: 'confirmed' } })
      }),
    )
    renderTransactionsPage()

    expect(await screen.findByText(/Transfer out/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm transfer' }))

    await waitFor(() => expect(screen.queryByText(/Transfer out/)).not.toBeInTheDocument())
  })

  it('creates a transaction', async () => {
    let created = false
    server.use(
      http.get('/api/v1/accounts', () => HttpResponse.json(pageOf([account]))),
      http.get('/api/v1/categories', () => HttpResponse.json(pageOf([groceries]))),
      http.get('/api/v1/transactions', ({ request }) => {
        const status = new URL(request.url).searchParams.get('transfer_status')
        if (status === 'suggested') return HttpResponse.json(pageOf([]))
        return HttpResponse.json(pageOf(created ? [txn] : []))
      }),
      http.post('/api/v1/transactions', () => {
        created = true
        return HttpResponse.json({ data: txn }, { status: 201 })
      }),
    )
    renderTransactionsPage()

    await waitFor(() => expect(screen.queryByText(/Loading transactions/)).not.toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText('Account'), 'a1')
    await userEvent.type(screen.getByLabelText(/Amount/), '-45.00')
    await userEvent.type(screen.getByLabelText('Description'), 'Groceries run')
    await userEvent.type(screen.getByLabelText('Date'), '2026-01-10')
    await userEvent.click(screen.getByRole('button', { name: 'Add transaction' }))

    expect(await screen.findByText(/Groceries run/)).toBeInTheDocument()
  })

  it('pre-filters by account when arriving via a ?account_id= deep link', async () => {
    let requestedAccountId: string | null = null
    server.use(
      http.get('/api/v1/accounts', () => HttpResponse.json(pageOf([account]))),
      http.get('/api/v1/categories', () => HttpResponse.json(pageOf([groceries]))),
      http.get('/api/v1/transactions', ({ request }) => {
        const url = new URL(request.url)
        if (url.searchParams.get('transfer_status') === 'suggested') {
          return HttpResponse.json(pageOf([]))
        }
        requestedAccountId = url.searchParams.get('account_id')
        return HttpResponse.json(pageOf([txn]))
      }),
    )
    renderTransactionsPage('/transactions?account_id=a1')

    expect(await screen.findByText(/Groceries run/)).toBeInTheDocument()
    expect(requestedAccountId).toBe('a1')
    expect(screen.getByLabelText('Filter by account')).toHaveValue('a1')
  })
})
