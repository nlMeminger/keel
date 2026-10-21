import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../../test/render'
import { server } from '../../../test/mocks/server'
import { AuditLogPage } from './AuditLogPage'

function renderPage() {
  return renderWithProviders(
    <MemoryRouter>
      <AuditLogPage />
    </MemoryRouter>,
  )
}

function pageOf(items: object[]) {
  return {
    data: items,
    pagination: { page: 1, page_size: 25, total_count: items.length, total_pages: 1 },
  }
}

const entry = {
  id: 'log1',
  admin_user_id: 'admin1',
  action: 'user.suspend',
  target_type: 'user',
  target_id: 'u1',
  metadata: { status: 'suspended' },
  created_at: '2026-01-01T00:00:00Z',
}

describe('AuditLogPage', () => {
  it('renders audit log entries', async () => {
    server.use(http.get('/api/v1/admin/audit-log', () => HttpResponse.json(pageOf([entry]))))
    renderPage()
    expect(await screen.findByText('user.suspend')).toBeInTheDocument()
    expect(screen.getByText('user:u1')).toBeInTheDocument()
  })

  it('shows an error state instead of hanging when the list fails to load', async () => {
    server.use(
      http.get('/api/v1/admin/audit-log', () =>
        HttpResponse.json({ error: { code: 'x', message: 'x' } }, { status: 500 }),
      ),
    )
    renderPage()
    expect(await screen.findByText('Failed to load audit log.')).toBeInTheDocument()
  })

  it('filters by action', async () => {
    const otherEntry = { ...entry, id: 'log2', action: 'user.delete' }
    server.use(
      http.get('/api/v1/admin/audit-log', ({ request }) => {
        const url = new URL(request.url)
        const action = url.searchParams.get('action')
        const matching = action ? [otherEntry].filter((e) => e.action === action) : [entry]
        return HttpResponse.json(pageOf(matching))
      }),
    )
    renderPage()
    expect(await screen.findByText('user.suspend')).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Filter by action'), 'user.delete')
    expect(await screen.findByText('user.delete')).toBeInTheDocument()
    expect(screen.queryByText('user.suspend')).not.toBeInTheDocument()
  })
})
