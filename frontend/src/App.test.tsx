import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from './App'
import { AuthProvider } from './features/auth/auth-context'
import { server } from './test/mocks/server'

function renderApp(initialPath = '/') {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('App', () => {
  it('redirects an unauthenticated visitor at "/" to the login page', async () => {
    server.use(
      http.post('/api/v1/auth/refresh', () =>
        HttpResponse.json({ error: { code: 'x', message: 'x' } }, { status: 401 }),
      ),
    )
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })

  it('shows the home page once a silent refresh succeeds, with zero console errors', async () => {
    server.use(
      http.post('/api/v1/auth/refresh', () =>
        HttpResponse.json({ data: { access_token: 'token-123' } }),
      ),
      http.get('/api/v1/auth/me', () =>
        HttpResponse.json({
          data: {
            id: 'u1',
            email: 'a@example.com',
            name: 'Ada',
            timezone: 'UTC',
            role: 'user',
            status: 'active',
            must_change_password: false,
            created_at: '2026-01-01T00:00:00Z',
          },
        }),
      ),
    )
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Money App' })).toBeInTheDocument()
    expect(await screen.findByText('Welcome, Ada.')).toBeInTheDocument()
  })
})
