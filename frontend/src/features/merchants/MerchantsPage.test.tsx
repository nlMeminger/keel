import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/render'
import { server } from '../../test/mocks/server'
import { MerchantsPage } from './MerchantsPage'

function renderMerchantsPage() {
  return renderWithProviders(<MerchantsPage />)
}

const merchant = {
  id: 'm1',
  name: 'Coffee Co',
  aliases: ['COFFEE CO #123'],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('MerchantsPage', () => {
  it('lists merchants with their aliases', async () => {
    server.use(
      http.get('/api/v1/merchants', () =>
        HttpResponse.json({
          data: [merchant],
          pagination: { page: 1, page_size: 25, total_count: 1, total_pages: 1 },
        }),
      ),
    )
    renderMerchantsPage()

    expect(await screen.findByText(/Coffee Co/)).toBeInTheDocument()
    expect(screen.getByText(/COFFEE CO #123/)).toBeInTheDocument()
  })

  it('creates a merchant with comma-separated aliases', async () => {
    let created = false
    server.use(
      http.get('/api/v1/merchants', () =>
        HttpResponse.json({
          data: created ? [merchant] : [],
          pagination: { page: 1, page_size: 25, total_count: created ? 1 : 0, total_pages: 1 },
        }),
      ),
      http.post('/api/v1/merchants', async ({ request }) => {
        const body = (await request.json()) as { name: string; aliases: string[] }
        expect(body.aliases).toEqual(['COFFEE CO #123', 'COFFEECO ONLINE'])
        created = true
        return HttpResponse.json({ data: merchant }, { status: 201 })
      }),
    )
    renderMerchantsPage()

    await waitFor(() => expect(screen.queryByText(/Loading merchants/)).not.toBeInTheDocument())
    await userEvent.type(screen.getByLabelText('Name'), 'Coffee Co')
    await userEvent.type(screen.getByLabelText(/Aliases/), 'COFFEE CO #123, COFFEECO ONLINE')
    await userEvent.click(screen.getByRole('button', { name: 'Add merchant' }))

    expect(await screen.findByText(/Coffee Co/)).toBeInTheDocument()
  })

  it('deletes a merchant', async () => {
    let deleted = false
    server.use(
      http.get('/api/v1/merchants', () =>
        HttpResponse.json({
          data: deleted ? [] : [merchant],
          pagination: { page: 1, page_size: 25, total_count: deleted ? 0 : 1, total_pages: 1 },
        }),
      ),
      http.delete('/api/v1/merchants/m1', () => {
        deleted = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderMerchantsPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(screen.queryByText(/Coffee Co/)).not.toBeInTheDocument())
  })
})
