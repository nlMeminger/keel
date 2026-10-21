import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import { NotificationsPage } from './NotificationsPage'

function renderPage() {
  return renderWithProviders(<NotificationsPage />)
}

function pageOf(items: object[]) {
  return {
    data: items,
    pagination: { page: 1, page_size: 25, total_count: items.length, total_pages: 1 },
  }
}

const unread = {
  id: 'n1',
  type: 'budget_threshold_90',
  title: 'Budget at 90% of its limit',
  body: "You've spent 90 of 100 this period (90%+).",
  related_type: 'budget',
  related_id: 'b1',
  read_at: null,
  created_at: '2026-01-01T00:00:00Z',
}

describe('NotificationsPage', () => {
  it('renders a notification', async () => {
    server.use(http.get('/api/v1/notifications', () => HttpResponse.json(pageOf([unread]))))
    renderPage()

    const list = await screen.findByRole('list')
    expect(within(list).getByText('Budget at 90% of its limit')).toBeInTheDocument()
  })

  it('shows an empty state with no notifications', async () => {
    server.use(http.get('/api/v1/notifications', () => HttpResponse.json(pageOf([]))))
    renderPage()

    expect(await screen.findByText('No notifications.')).toBeInTheDocument()
  })

  it('marks a notification read', async () => {
    let read = false
    server.use(
      http.get('/api/v1/notifications', (info) => {
        const url = new URL(info.request.url)
        if (url.searchParams.get('unread_only') === 'true' && read) {
          return HttpResponse.json(pageOf([]))
        }
        return HttpResponse.json(
          pageOf([{ ...unread, read_at: read ? '2026-01-02T00:00:00Z' : null }]),
        )
      }),
      http.patch('/api/v1/notifications/n1', async ({ request }) => {
        const body = (await request.json()) as { read: boolean }
        read = body.read
        return HttpResponse.json({
          data: { ...unread, read_at: read ? '2026-01-02T00:00:00Z' : null },
        })
      }),
    )
    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Mark read' }))
    expect(await screen.findByRole('button', { name: 'Mark unread' })).toBeInTheDocument()
  })

  it('dismisses a notification', async () => {
    let dismissed = false
    server.use(
      http.get('/api/v1/notifications', () => HttpResponse.json(pageOf(dismissed ? [] : [unread]))),
      http.delete('/api/v1/notifications/n1', () => {
        dismissed = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Dismiss' }))
    await waitFor(() => expect(screen.getByText('No notifications.')).toBeInTheDocument())
  })

  it('filters to unread only', async () => {
    const readOne = { ...unread, id: 'n2', read_at: '2026-01-02T00:00:00Z' }
    server.use(
      http.get('/api/v1/notifications', (info) => {
        const url = new URL(info.request.url)
        const unreadOnly = url.searchParams.get('unread_only') === 'true'
        return HttpResponse.json(pageOf(unreadOnly ? [unread] : [unread, readOne]))
      }),
    )
    renderPage()

    const initialList = await screen.findByRole('list')
    expect(within(initialList).getAllByRole('listitem')).toHaveLength(2)

    await userEvent.click(screen.getByLabelText('Unread only'))
    // Switching filters changes the query key, so the loading state briefly unmounts the
    // list — re-query it fresh each attempt rather than reusing the (now stale) node above.
    await waitFor(() =>
      expect(within(screen.getByRole('list')).getAllByRole('listitem')).toHaveLength(1),
    )
  })
})
