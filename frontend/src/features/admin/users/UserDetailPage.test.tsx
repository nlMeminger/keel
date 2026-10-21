import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../../test/render'
import { server } from '../../../test/mocks/server'
import { UserDetailPage } from './UserDetailPage'

function renderPage(userId = 'u1') {
  return renderWithProviders(
    <MemoryRouter initialEntries={[`/admin/users/${userId}`]}>
      <Routes>
        <Route path="/admin/users/:userId" element={<UserDetailPage />} />
        <Route path="/admin/users" element={<p>Users list</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

const user = {
  id: 'u1',
  email: 'target@example.com',
  name: 'Target User',
  role: 'user',
  status: 'active',
  plaid_enabled: true,
  plaid_monthly_call_limit: null,
  plaid_calls_this_month: 3,
  must_change_password: false,
  linked_bank_count: 1,
  created_at: '2026-01-01T00:00:00Z',
  last_login_at: null,
}

describe('UserDetailPage', () => {
  it("shows the user's metadata", async () => {
    server.use(http.get('/api/v1/admin/users/u1', () => HttpResponse.json({ data: user })))
    renderPage()
    expect(await screen.findByText('target@example.com')).toBeInTheDocument()
    expect(screen.getByText('Target User')).toBeInTheDocument()
  })

  it('suspends the user', async () => {
    let status = 'active'
    server.use(
      http.get('/api/v1/admin/users/u1', () => HttpResponse.json({ data: { ...user, status } })),
      http.patch('/api/v1/admin/users/u1', async ({ request }) => {
        const body = (await request.json()) as { status: string }
        status = body.status
        return HttpResponse.json({ data: { ...user, status } })
      }),
    )
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Suspend user' }))
    expect(await screen.findByRole('button', { name: 'Activate user' })).toBeInTheDocument()
  })

  it('resets the password and shows the generated one exactly once', async () => {
    server.use(
      http.get('/api/v1/admin/users/u1', () => HttpResponse.json({ data: user })),
      http.post('/api/v1/admin/users/u1/reset-password', () =>
        HttpResponse.json({ data: { temporary_password: 'generated-secret-123' } }),
      ),
    )
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Reset password' }))
    expect(await screen.findByText(/generated-secret-123/)).toBeInTheDocument()
  })

  it('revokes sessions', async () => {
    server.use(
      http.get('/api/v1/admin/users/u1', () => HttpResponse.json({ data: user })),
      http.post(
        '/api/v1/admin/users/u1/revoke-sessions',
        () => new HttpResponse(null, { status: 204 }),
      ),
    )
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Revoke sessions' }))
    expect(await screen.findByText('Sessions revoked.')).toBeInTheDocument()
  })

  it('deletes the user and navigates back to the list', async () => {
    server.use(
      http.get('/api/v1/admin/users/u1', () => HttpResponse.json({ data: user })),
      http.delete('/api/v1/admin/users/u1', () => new HttpResponse(null, { status: 204 })),
    )
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Delete user' }))
    expect(await screen.findByText('Users list')).toBeInTheDocument()
  })
})
