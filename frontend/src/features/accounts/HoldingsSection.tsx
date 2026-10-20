import { Button, Group, Paper, Stack, Text, TextInput, Title } from '@mantine/core'
import { useState } from 'react'
import { ApiError } from '../../lib/api-client'
import { useCreateHolding, useDeleteHolding, useHoldings, useUpdateHolding } from './api'

export function HoldingsSection({ accountId }: { accountId: string }) {
  const { data: holdings, isLoading } = useHoldings(accountId)
  const createHolding = useCreateHolding(accountId)
  const updateHolding = useUpdateHolding(accountId)
  const deleteHolding = useDeleteHolding(accountId)

  const [symbol, setSymbol] = useState('')
  const [name, setName] = useState('')
  const [quantity, setQuantity] = useState('')
  const [costBasis, setCostBasis] = useState('')

  function handleAdd(event: React.FormEvent) {
    event.preventDefault()
    createHolding.mutate(
      { symbol, name, quantity, cost_basis: costBasis },
      {
        onSuccess: () => {
          setSymbol('')
          setName('')
          setQuantity('')
          setCostBasis('')
        },
      },
    )
  }

  return (
    <Stack mt="md" pl="md" style={{ borderLeft: '2px solid var(--mantine-color-default-border)' }}>
      <Title order={4} size="h6">
        Holdings
      </Title>
      <form onSubmit={handleAdd}>
        <Group align="flex-end">
          <TextInput
            placeholder="Symbol"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            required
          />
          <TextInput
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <TextInput
            placeholder="Quantity"
            type="number"
            step="0.000001"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            required
          />
          <TextInput
            placeholder="Cost basis"
            type="number"
            step="0.01"
            value={costBasis}
            onChange={(e) => setCostBasis(e.target.value)}
            required
          />
          <Button type="submit" loading={createHolding.isPending}>
            Add holding
          </Button>
        </Group>
      </form>
      {createHolding.isError && (
        <Text role="alert" c="red" size="sm">
          {createHolding.error instanceof ApiError
            ? createHolding.error.message
            : 'Failed to add holding.'}
        </Text>
      )}
      {isLoading || !holdings ? (
        <Text>Loading holdings…</Text>
      ) : (
        <Stack gap="xs">
          {holdings.map((holding) => (
            <Paper key={holding.id} withBorder p="sm" radius="sm">
              <Group justify="space-between">
                <Text size="sm">
                  {holding.symbol} — {holding.quantity} units, cost basis {holding.cost_basis}
                  {holding.current_value && ` (current value ${holding.current_value})`}
                </Text>
                {holding.source === 'manual' && (
                  <Group gap="xs">
                    <Button
                      size="xs"
                      variant="subtle"
                      onClick={() => {
                        const value = window.prompt('Current value?', holding.current_value ?? '')
                        if (value !== null) {
                          updateHolding.mutate({ id: holding.id, input: { current_value: value } })
                        }
                      }}
                    >
                      Set value
                    </Button>
                    <Button
                      size="xs"
                      variant="subtle"
                      color="red"
                      onClick={() => deleteHolding.mutate(holding.id)}
                      loading={deleteHolding.isPending}
                    >
                      Remove
                    </Button>
                  </Group>
                )}
              </Group>
            </Paper>
          ))}
        </Stack>
      )}
    </Stack>
  )
}
