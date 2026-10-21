import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import { CategoryRulesPage } from './CategoryRulesPage'

function renderPage() {
  return renderWithProviders(<CategoryRulesPage />)
}

function pageOf(items: object[]) {
  return {
    data: items,
    pagination: { page: 1, page_size: 25, total_count: items.length, total_pages: 1 },
  }
}

const subscriptions = {
  id: 'cat1',
  owner_id: null,
  primary_category: 'Subscriptions',
  detailed_category: null,
  icon: null,
  color: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const rule = {
  id: 'r1',
  merchant_contains: 'netflix',
  amount_min: null,
  amount_max: null,
  account_id: null,
  category_id: 'cat1',
  priority: 100,
  active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('CategoryRulesPage', () => {
  it('renders a rule with its conditions and target category', async () => {
    server.use(
      http.get('/api/v1/categories', () => HttpResponse.json(pageOf([subscriptions]))),
      http.get('/api/v1/accounts', () => HttpResponse.json(pageOf([]))),
      http.get('/api/v1/category-rules', () => HttpResponse.json(pageOf([rule]))),
    )
    renderPage()

    const list = await screen.findByRole('list')
    expect(within(list).getByText(/Subscriptions/)).toBeInTheDocument()
    expect(within(list).getByText(/netflix/)).toBeInTheDocument()
  })

  it('creates a rule', async () => {
    let created = false
    server.use(
      http.get('/api/v1/categories', () => HttpResponse.json(pageOf([subscriptions]))),
      http.get('/api/v1/accounts', () => HttpResponse.json(pageOf([]))),
      http.get('/api/v1/category-rules', () => HttpResponse.json(pageOf(created ? [rule] : []))),
      http.post('/api/v1/category-rules', async ({ request }) => {
        const body = (await request.json()) as { category_id: string }
        expect(body.category_id).toBe('cat1')
        created = true
        return HttpResponse.json({ data: rule }, { status: 201 })
      }),
    )
    renderPage()

    await waitFor(() =>
      expect(screen.queryByText(/Loading category rules/)).not.toBeInTheDocument(),
    )
    await userEvent.type(screen.getByLabelText('Description contains'), 'netflix')
    await userEvent.selectOptions(screen.getByLabelText('Assign category'), 'cat1')
    await userEvent.click(screen.getByRole('button', { name: 'Add rule' }))

    const list = await screen.findByRole('list')
    expect(await within(list).findByText(/Subscriptions/)).toBeInTheDocument()
  })

  it('deletes a rule', async () => {
    let deleted = false
    server.use(
      http.get('/api/v1/categories', () => HttpResponse.json(pageOf([subscriptions]))),
      http.get('/api/v1/accounts', () => HttpResponse.json(pageOf([]))),
      http.get('/api/v1/category-rules', () => HttpResponse.json(pageOf(deleted ? [] : [rule]))),
      http.delete('/api/v1/category-rules/r1', () => {
        deleted = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    const list = screen.getByRole('list')
    await waitFor(() => expect(within(list).queryByText(/netflix/)).not.toBeInTheDocument())
  })

  it('applies rules and shows the job as succeeded', async () => {
    server.use(
      http.get('/api/v1/categories', () => HttpResponse.json(pageOf([subscriptions]))),
      http.get('/api/v1/accounts', () => HttpResponse.json(pageOf([]))),
      http.get('/api/v1/category-rules', () => HttpResponse.json(pageOf([rule]))),
      http.post('/api/v1/category-rules/apply', () =>
        HttpResponse.json({ data: { job_id: 'job1' } }, { status: 202 }),
      ),
      http.get('/api/v1/sync/jobs/job1', () =>
        HttpResponse.json({
          data: {
            id: 'job1',
            type: 'category_rule_apply',
            status: 'succeeded',
            progress: null,
            started_at: '2026-01-01T00:00:00Z',
            finished_at: '2026-01-01T00:00:01Z',
            error: null,
          },
        }),
      ),
    )
    renderPage()

    await userEvent.click(
      await screen.findByRole('button', { name: 'Apply rules to uncategorized transactions' }),
    )

    expect(await screen.findByText(/Done — transactions updated/)).toBeInTheDocument()
  })
})
