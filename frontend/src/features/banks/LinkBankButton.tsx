import { Button, Stack, Text } from '@mantine/core'
import { useEffect } from 'react'
import { usePlaidLink } from 'react-plaid-link'
import { useCreateLinkToken, useExchangeToken } from './api'

/** "Link a bank" entry point (ROADMAP 7.9) — fetches a Link token, hands it to Plaid's own
 * Link UI, then exchanges the public_token it returns for a real bank connection. Plaid
 * Link only becomes `ready` once it has a non-empty token, so opening it waits on that via
 * the effect below rather than wiring a token straight into the button's onClick. */
export function LinkBankButton() {
  const createLinkToken = useCreateLinkToken()
  const exchangeToken = useExchangeToken()

  const { open, ready } = usePlaidLink({
    token: createLinkToken.data?.link_token ?? '',
    onSuccess: (publicToken) => {
      if (publicToken) exchangeToken.mutate(publicToken)
    },
  })

  useEffect(() => {
    if (ready && createLinkToken.data) {
      open()
    }
  }, [ready, createLinkToken.data, open])

  const error = createLinkToken.isError
    ? 'Failed to start linking a bank.'
    : exchangeToken.isError
      ? 'Failed to link that bank.'
      : null

  return (
    <Stack gap={4}>
      <Button
        onClick={() => createLinkToken.mutate()}
        loading={createLinkToken.isPending || exchangeToken.isPending}
      >
        Link a bank
      </Button>
      {error && (
        <Text role="alert" c="red" size="sm">
          {error}
        </Text>
      )}
    </Stack>
  )
}
