import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../../test/render'
import { server } from '../../../test/mocks/server'
import { UsersPage } from './UsersPage'

function renderPage() {
  return renderWithProviders(
    <MemoryRouter>
      <UsersPage />
    </MemoryRouter>,
  )
}

function pageOf(items: object[]) {
  return {
    data: items,
    pagination: { page: 1, page_size: 25, total_count: items.length, total_pages: 1 },
  }
}

const activeUser = {
  id: 'u1',
  email: 'active@example.com',
  name: 'Active User',
  role: 'user',
  status: 'active',
  plaid_enabled: true,
  plaid_monthly_call_limit: null,
  plaid_calls_this_month: 0,
  must_change_password: false,
  linked_bank_count: 2,
  created_at: '2026-01-01T00:00:00Z',
  last_login_at: null,
}

describe('UsersPage', () => {
  it('renders a list of users', async () => {
    server.use(http.get('/api/v1/admin/users', () => HttpResponse.json(pageOf([activeUser]))))
    renderPage()
    expect(await screen.findByText('active@example.com')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('shows an error state instead of hanging when the list fails to load', async () => {
    server.use(
      http.get('/api/v1/admin/users', () =>
        HttpResponse.json({ error: { code: 'x', message: 'x' } }, { status: 500 }),
      ),
    )
    renderPage()
    expect(await screen.findByText('Failed to load users.')).toBeInTheDocument()
  })

  it('suspends an active user', async () => {
    let status = 'active'
    server.use(
      http.get('/api/v1/admin/users', () => HttpResponse.json(pageOf([{ ...activeUser, status }]))),
      http.patch('/api/v1/admin/users/u1', async ({ request }) => {
        const body = (await request.json()) as { status: string }
        status = body.status
        return HttpResponse.json({ data: { ...activeUser, status } })
      }),
    )
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Suspend' }))
    expect(await screen.findByRole('button', { name: 'Activate' })).toBeInTheDocument()
  })

  it('filters by role', async () => {
    const adminUser = { ...activeUser, id: 'u2', email: 'admin@example.com', role: 'admin' }
    server.use(
      http.get('/api/v1/admin/users', ({ request }) => {
        const url = new URL(request.url)
        const matching = url.searchParams.get('role') === 'admin' ? [adminUser] : [activeUser]
        return HttpResponse.json(pageOf(matching))
      }),
    )
    renderPage()
    expect(await screen.findByText('active@example.com')).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText('Role'), 'admin')
    expect(await screen.findByText('admin@example.com')).toBeInTheDocument()
    expect(screen.queryByText('active@example.com')).not.toBeInTheDocument()
  })
})
