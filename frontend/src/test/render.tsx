import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { theme } from '../theme'

// Wraps a component tree with the same providers main.tsx sets up (Mantine, TanStack Query),
// so component tests see real Mantine styling/behavior instead of unstyled HTML.
export function renderWithProviders(ui: ReactElement) {
  // retry: false — an error-state test would otherwise need to outlast React Query's default
  // 3-attempt exponential backoff before the query actually settles into `isError`.
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MantineProvider theme={theme}>
      <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
    </MantineProvider>,
  )
}
