import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/mocks/server'
import { AccountsPage } from './AccountsPage'

function renderAccountsPage() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <AccountsPage />
    </QueryClientProvider>,
  )
}

const baseAccount = {
  id: 'a1',
  name: 'Checking',
  account_type: 'checking',
  balance: '100.00',
  detail: {},
  is_active: true,
  is_plaid_linked: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('AccountsPage', () => {
  it('lists accounts', async () => {
    server.use(
      http.get('/api/v1/accounts', () =>
        HttpResponse.json({
          data: [baseAccount],
          pagination: { page: 1, page_size: 25, total_count: 1, total_pages: 1 },
        }),
      ),
    )
    renderAccountsPage()

    expect(await screen.findByText(/Checking/)).toBeInTheDocument()
  })

  it('creates an account and the list updates without a manual refresh', async () => {
    let created = false
    server.use(
      http.get('/api/v1/accounts', () =>
        HttpResponse.json({
          data: created ? [baseAccount] : [],
          pagination: { page: 1, page_size: 25, total_count: created ? 1 : 0, total_pages: 1 },
        }),
      ),
      http.post('/api/v1/accounts', () => {
        created = true
        return HttpResponse.json({ data: baseAccount }, { status: 201 })
      }),
    )
    renderAccountsPage()

    await waitFor(() => expect(screen.queryByText(/Loading accounts/)).not.toBeInTheDocument())

    await userEvent.type(screen.getByLabelText('Name'), 'Checking')
    await userEvent.click(screen.getByRole('button', { name: 'Add account' }))

    expect(await screen.findByText(/Checking/)).toBeInTheDocument()
  })

  it('switching account type changes which detail fields are shown', async () => {
    server.use(
      http.get('/api/v1/accounts', () =>
        HttpResponse.json({
          data: [],
          pagination: { page: 1, page_size: 25, total_count: 0, total_pages: 1 },
        }),
      ),
    )
    renderAccountsPage()

    expect(screen.queryByText('Credit limit')).not.toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Type'), 'credit_card')
    expect(await screen.findByText('Credit limit')).toBeInTheDocument()
  })

  it('deactivating an account removes it from the default (active-only) list', async () => {
    let active = true
    server.use(
      http.get('/api/v1/accounts', ({ request }) => {
        const url = new URL(request.url)
        const activeParam = url.searchParams.get('active')
        const matches = activeParam === 'true' ? active : !active
        return HttpResponse.json({
          data: matches ? [baseAccount] : [],
          pagination: { page: 1, page_size: 25, total_count: matches ? 1 : 0, total_pages: 1 },
        })
      }),
      http.delete('/api/v1/accounts/a1', () => {
        active = false
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderAccountsPage()

    expect(await screen.findByText(/Checking/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Deactivate' }))

    await waitFor(() => expect(screen.queryByText(/Checking/)).not.toBeInTheDocument())
  })
})
