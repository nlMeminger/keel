import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/mocks/server'
import { GoalsPage } from './GoalsPage'

function renderGoalsPage() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <GoalsPage />
    </QueryClientProvider>,
  )
}

function pageOf(items: object[]) {
  return {
    data: items,
    pagination: { page: 1, page_size: 25, total_count: items.length, total_pages: 1 },
  }
}

const goal = {
  id: 'g1',
  name: 'Vacation',
  target_amount: '2000.00',
  target_date: null,
  progress_amount: '300.00',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('GoalsPage', () => {
  it('renders a goal with its progress', async () => {
    server.use(http.get('/api/v1/goals', () => HttpResponse.json(pageOf([goal]))))
    renderGoalsPage()

    const list = await screen.findByRole('list')
    expect(within(list).getByText(/Vacation/)).toBeInTheDocument()
    expect(within(list).getByText(/300.00 of 2000.00/)).toBeInTheDocument()
  })

  it('adding a contribution updates progress immediately from the response, no second fetch', async () => {
    let fetchCount = 0
    server.use(
      http.get('/api/v1/goals', () => {
        fetchCount += 1
        return HttpResponse.json(pageOf([goal]))
      }),
      http.post('/api/v1/goals/g1/contributions', () =>
        HttpResponse.json({ data: { ...goal, progress_amount: '450.00' } }, { status: 201 }),
      ),
    )
    renderGoalsPage()

    const list = await screen.findByRole('list')
    await waitFor(() => expect(fetchCount).toBe(1))

    await userEvent.type(screen.getByPlaceholderText('Contribution amount'), '150')
    await userEvent.click(screen.getByRole('button', { name: 'Add contribution' }))

    expect(await within(list).findByText(/450.00 of 2000.00/)).toBeInTheDocument()
    // Still only the one initial GET — the mutation response updated the cache directly.
    expect(fetchCount).toBe(1)
  })

  it('creates a goal', async () => {
    let created = false
    server.use(
      http.get('/api/v1/goals', () => HttpResponse.json(pageOf(created ? [goal] : []))),
      http.post('/api/v1/goals', () => {
        created = true
        return HttpResponse.json({ data: goal }, { status: 201 })
      }),
    )
    renderGoalsPage()

    await waitFor(() => expect(screen.queryByText(/Loading goals/)).not.toBeInTheDocument())
    await userEvent.type(screen.getByLabelText('Name'), 'Vacation')
    await userEvent.type(screen.getByLabelText('Target amount'), '2000')
    await userEvent.click(screen.getByRole('button', { name: 'Add goal' }))

    expect(await screen.findByText(/Vacation/)).toBeInTheDocument()
  })

  it('deletes a goal', async () => {
    let deleted = false
    server.use(
      http.get('/api/v1/goals', () => HttpResponse.json(pageOf(deleted ? [] : [goal]))),
      http.delete('/api/v1/goals/g1', () => {
        deleted = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderGoalsPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(screen.queryByText(/Vacation/)).not.toBeInTheDocument())
  })
})
