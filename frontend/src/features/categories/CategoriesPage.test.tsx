import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import { CategoriesPage } from './CategoriesPage'

function renderCategoriesPage() {
  return renderWithProviders(<CategoriesPage />)
}

const systemCategory = {
  id: 'sys1',
  owner_id: null,
  primary_category: 'Transfer',
  detailed_category: null,
  icon: null,
  color: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const customCategory = {
  id: 'c1',
  owner_id: 'u1',
  primary_category: 'Hobbies',
  detailed_category: null,
  icon: null,
  color: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function mockCategoryList(system: object[], custom: object[]) {
  server.use(
    http.get('/api/v1/categories', ({ request }) => {
      const scope = new URL(request.url).searchParams.get('scope')
      const items = scope === 'system' ? system : custom
      return HttpResponse.json({
        data: items,
        pagination: { page: 1, page_size: 25, total_count: items.length, total_pages: 1 },
      })
    }),
  )
}

describe('CategoriesPage', () => {
  it('renders system categories without edit/delete controls', async () => {
    mockCategoryList([systemCategory], [])
    renderCategoriesPage()

    expect(await screen.findByText('Transfer')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
  })

  it('creates a custom category', async () => {
    let created = false
    server.use(
      http.get('/api/v1/categories', ({ request }) => {
        const scope = new URL(request.url).searchParams.get('scope')
        const items = scope === 'system' ? [] : created ? [customCategory] : []
        return HttpResponse.json({
          data: items,
          pagination: { page: 1, page_size: 25, total_count: items.length, total_pages: 1 },
        })
      }),
      http.post('/api/v1/categories', () => {
        created = true
        return HttpResponse.json({ data: customCategory }, { status: 201 })
      }),
    )
    renderCategoriesPage()

    await waitFor(() => expect(screen.queryByText(/Loading categories/)).not.toBeInTheDocument())
    await userEvent.type(screen.getByLabelText('New category'), 'Hobbies')
    await userEvent.click(screen.getByRole('button', { name: 'Add category' }))

    expect(await screen.findByText('Hobbies')).toBeInTheDocument()
  })

  it('shows a reassign picker when deleting a category still in use', async () => {
    mockCategoryList([], [customCategory])
    server.use(
      http.delete('/api/v1/categories/c1', () =>
        HttpResponse.json(
          { error: { code: 'category_in_use', message: 'still in use' } },
          { status: 409 },
        ),
      ),
    )
    renderCategoriesPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    expect(await screen.findByText(/still used by some transactions/)).toBeInTheDocument()
  })
})
