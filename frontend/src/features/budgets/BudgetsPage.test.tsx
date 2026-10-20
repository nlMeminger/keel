import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import { BudgetsPage } from './BudgetsPage'

function renderBudgetsPage() {
  return renderWithProviders(<BudgetsPage />)
}

function pageOf(items: object[]) {
  return {
    data: items,
    pagination: { page: 1, page_size: 25, total_count: items.length, total_pages: 1 },
  }
}

const groceries = {
  id: 'cat1',
  owner_id: null,
  primary_category: 'Groceries',
  detailed_category: null,
  icon: null,
  color: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const budget = {
  id: 'b1',
  category_id: 'cat1',
  amount_limit: '300.00',
  period: 'monthly',
  start_date: '2026-01-01',
  spend_so_far: '45.00',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('BudgetsPage', () => {
  it('renders a budget with its live spend-vs-limit', async () => {
    server.use(
      http.get('/api/v1/categories', () => HttpResponse.json(pageOf([groceries]))),
      http.get('/api/v1/budgets', () => HttpResponse.json(pageOf([budget]))),
    )
    renderBudgetsPage()

    const list = await screen.findByRole('list')
    expect(within(list).getByText(/Groceries/)).toBeInTheDocument()
    expect(within(list).getByText(/45.00 of 300.00 spent/)).toBeInTheDocument()
  })

  it('creates an overall budget', async () => {
    let created = false
    const overallBudget = { ...budget, id: 'b2', category_id: null }
    server.use(
      http.get('/api/v1/categories', () => HttpResponse.json(pageOf([groceries]))),
      http.get('/api/v1/budgets', () => HttpResponse.json(pageOf(created ? [overallBudget] : []))),
      http.post('/api/v1/budgets', async ({ request }) => {
        const body = (await request.json()) as { category_id: string | null }
        expect(body.category_id).toBeNull()
        created = true
        return HttpResponse.json({ data: overallBudget }, { status: 201 })
      }),
    )
    renderBudgetsPage()

    await waitFor(() => expect(screen.queryByText(/Loading budgets/)).not.toBeInTheDocument())
    await userEvent.type(screen.getByLabelText('Monthly limit'), '300')
    await userEvent.type(screen.getByLabelText('Start date'), '2026-01-01')
    await userEvent.click(screen.getByRole('button', { name: 'Add budget' }))

    const list = await screen.findByRole('list')
    expect(await within(list).findByText(/Overall/)).toBeInTheDocument()
  })

  it('deletes a budget', async () => {
    let deleted = false
    server.use(
      http.get('/api/v1/categories', () => HttpResponse.json(pageOf([groceries]))),
      http.get('/api/v1/budgets', () => HttpResponse.json(pageOf(deleted ? [] : [budget]))),
      http.delete('/api/v1/budgets/b1', () => {
        deleted = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderBudgetsPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    const list = screen.getByRole('list')
    await waitFor(() => expect(within(list).queryByText(/Groceries/)).not.toBeInTheDocument())
  })
})
