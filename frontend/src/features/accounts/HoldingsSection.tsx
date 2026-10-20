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
    <div>
      <h3>Holdings</h3>
      <form onSubmit={handleAdd}>
        <input
          placeholder="Symbol"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          required
        />
        <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required />
        <input
          placeholder="Quantity"
          type="number"
          step="0.000001"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          required
        />
        <input
          placeholder="Cost basis"
          type="number"
          step="0.01"
          value={costBasis}
          onChange={(e) => setCostBasis(e.target.value)}
          required
        />
        <button type="submit" disabled={createHolding.isPending}>
          Add holding
        </button>
      </form>
      {createHolding.isError && (
        <p role="alert">
          {createHolding.error instanceof ApiError
            ? createHolding.error.message
            : 'Failed to add holding.'}
        </p>
      )}
      {isLoading || !holdings ? (
        <p>Loading holdings…</p>
      ) : (
        <ul>
          {holdings.map((holding) => (
            <li key={holding.id}>
              {holding.symbol} — {holding.quantity} units, cost basis {holding.cost_basis}
              {holding.current_value && ` (current value ${holding.current_value})`}
              {holding.source === 'manual' && (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      const value = window.prompt('Current value?', holding.current_value ?? '')
                      if (value !== null) {
                        updateHolding.mutate({ id: holding.id, input: { current_value: value } })
                      }
                    }}
                  >
                    Set value
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteHolding.mutate(holding.id)}
                    disabled={deleteHolding.isPending}
                  >
                    Remove
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
