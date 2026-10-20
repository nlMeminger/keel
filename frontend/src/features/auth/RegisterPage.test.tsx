import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/mocks/server'
import { RegisterPage } from './RegisterPage'

function renderRegisterPage() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/register']}>
        <Routes>
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/login" element={<p>Landed on login</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RegisterPage', () => {
  it('navigates to login on successful registration', async () => {
    server.use(
      http.post('/api/v1/auth/register', () =>
        HttpResponse.json(
          {
            data: {
              id: 'u1',
              email: 'new@example.com',
              name: 'New',
              timezone: 'UTC',
              role: 'user',
              status: 'active',
              must_change_password: false,
              created_at: '2026-01-01T00:00:00Z',
            },
          },
          { status: 201 },
        ),
      ),
    )
    renderRegisterPage()

    await userEvent.type(screen.getByLabelText('Name'), 'New User')
    await userEvent.type(screen.getByLabelText('Email'), 'new@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'correct-password')
    await userEvent.click(screen.getByRole('button', { name: 'Register' }))

    expect(await screen.findByText('Landed on login')).toBeInTheDocument()
  })

  it('shows an error message when the email is already taken', async () => {
    server.use(
      http.post('/api/v1/auth/register', () =>
        HttpResponse.json(
          { error: { code: 'email_taken', message: 'An account with this email already exists.' } },
          { status: 409 },
        ),
      ),
    )
    renderRegisterPage()

    await userEvent.type(screen.getByLabelText('Name'), 'New User')
    await userEvent.type(screen.getByLabelText('Email'), 'dupe@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'correct-password')
    await userEvent.click(screen.getByRole('button', { name: 'Register' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('already exists')
  })
})
