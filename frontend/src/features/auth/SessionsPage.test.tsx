import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '../../test/mocks/server'
import { SessionsPage } from './SessionsPage'

function renderSessionsPage() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <SessionsPage />
    </QueryClientProvider>,
  )
}

const sessions = [
  {
    id: 's1',
    created_at: '2026-01-01T00:00:00Z',
    last_used_at: null,
    user_agent: 'Chrome on Mac',
    is_current: true,
  },
  {
    id: 's2',
    created_at: '2026-01-02T00:00:00Z',
    last_used_at: null,
    user_agent: 'Firefox on Linux',
    is_current: false,
  },
]

describe('SessionsPage', () => {
  it('lists sessions and revokes a non-current one', async () => {
    server.use(http.get('/api/v1/auth/sessions', () => HttpResponse.json({ data: sessions })))
    const revokeSpy = vi.fn()
    server.use(
      http.delete('/api/v1/auth/sessions/s2', () => {
        revokeSpy()
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderSessionsPage()

    expect(await screen.findByText(/Chrome on Mac/)).toBeInTheDocument()
    expect(screen.getByText(/this session/)).toBeInTheDocument()
    expect(screen.getByText(/Firefox on Linux/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Revoke' }))
    await waitFor(() => expect(revokeSpy).toHaveBeenCalledOnce())
  })
})
