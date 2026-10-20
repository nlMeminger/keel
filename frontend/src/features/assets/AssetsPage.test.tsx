import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/mocks/server'
import { AssetsPage } from './AssetsPage'

function renderAssetsPage() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <AssetsPage />
    </QueryClientProvider>,
  )
}

function pageOf(items: object[]) {
  return {
    data: items,
    pagination: { page: 1, page_size: 25, total_count: items.length, total_pages: 1 },
  }
}

const asset = {
  id: 'as1',
  name: 'Family car',
  asset_type: 'vehicle',
  current_value: '18000.00',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('AssetsPage', () => {
  it('lists assets', async () => {
    server.use(http.get('/api/v1/assets', () => HttpResponse.json(pageOf([asset]))))
    renderAssetsPage()

    expect(await screen.findByText(/Family car/)).toBeInTheDocument()
  })

  it('creates an asset', async () => {
    let created = false
    server.use(
      http.get('/api/v1/assets', () => HttpResponse.json(pageOf(created ? [asset] : []))),
      http.post('/api/v1/assets', () => {
        created = true
        return HttpResponse.json({ data: asset }, { status: 201 })
      }),
    )
    renderAssetsPage()

    await waitFor(() => expect(screen.queryByText(/Loading assets/)).not.toBeInTheDocument())
    await userEvent.type(screen.getByLabelText('Name'), 'Family car')
    await userEvent.type(screen.getByLabelText(/Type/), 'vehicle')
    await userEvent.type(screen.getByLabelText('Current value'), '18000')
    await userEvent.click(screen.getByRole('button', { name: 'Add asset' }))

    expect(await screen.findByText(/Family car/)).toBeInTheDocument()
  })

  it('updates an asset value', async () => {
    let updated = false
    server.use(
      http.get('/api/v1/assets', () =>
        HttpResponse.json(pageOf([updated ? { ...asset, current_value: '19000.00' } : asset])),
      ),
      http.patch('/api/v1/assets/as1', () => {
        updated = true
        return HttpResponse.json({ data: { ...asset, current_value: '19000.00' } })
      }),
    )
    renderAssetsPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    const input = screen.getByDisplayValue('18000.00')
    await userEvent.clear(input)
    await userEvent.type(input, '19000')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText(/19000.00/)).toBeInTheDocument()
  })

  it('deletes an asset', async () => {
    let deleted = false
    server.use(
      http.get('/api/v1/assets', () => HttpResponse.json(pageOf(deleted ? [] : [asset]))),
      http.delete('/api/v1/assets/as1', () => {
        deleted = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderAssetsPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(screen.queryByText(/Family car/)).not.toBeInTheDocument())
  })
})
