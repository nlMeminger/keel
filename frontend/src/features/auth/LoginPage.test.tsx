import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import { LoginPage } from './LoginPage'

function renderLoginPage() {
  return renderWithProviders(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<p>Landed on home</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  it('navigates home on successful login', async () => {
    server.use(
      http.post('/api/v1/auth/login', () =>
        HttpResponse.json({
          data: {
            access_token: 'token-abc',
            user: {
              id: 'u1',
              email: 'a@example.com',
              name: 'Ada',
              timezone: 'UTC',
              role: 'user',
              status: 'active',
              must_change_password: false,
              created_at: '2026-01-01T00:00:00Z',
            },
          },
        }),
      ),
    )
    renderLoginPage()

    await userEvent.type(screen.getByLabelText('Email'), 'a@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'correct-password')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('Landed on home')).toBeInTheDocument()
  })

  it('shows an error message on invalid credentials', async () => {
    server.use(
      http.post('/api/v1/auth/login', () =>
        HttpResponse.json(
          { error: { code: 'invalid_credentials', message: 'Incorrect email or password.' } },
          { status: 401 },
        ),
      ),
    )
    renderLoginPage()

    await userEvent.type(screen.getByLabelText('Email'), 'a@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-password')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.')
  })
})
