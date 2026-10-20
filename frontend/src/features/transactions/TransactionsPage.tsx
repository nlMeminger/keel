import { useState } from 'react'
import { useAccounts } from '../accounts/api'
import { useCategories } from '../categories/api'
import {
  type Transaction,
  type TransactionFilters,
  useCreateTransaction,
  useDeleteTransaction,
  useTransactions,
  useUpdateTransaction,
} from './api'

function CreateTransactionForm() {
  const { data: accounts } = useAccounts({ active: true })
  const { data: categories } = useCategories('all')
  const createTransaction = useCreateTransaction()

  const [accountId, setAccountId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [date, setDate] = useState('')

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    createTransaction.mutate(
      {
        account_id: accountId,
        category_id: categoryId || null,
        amount,
        description,
        date,
        pending: false,
      },
      {
        onSuccess: () => {
          setAmount('')
          setDescription('')
        },
      },
    )
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>Add transaction</h2>
      <label>
        Account
        <select value={accountId} onChange={(e) => setAccountId(e.target.value)} required>
          <option value="">Select account…</option>
          {(accounts ?? []).map((account) => (
            <option key={account.id} value={account.id}>
              {account.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Category
        <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
          <option value="">Uncategorized</option>
          {(categories ?? []).map((category) => (
            <option key={category.id} value={category.id}>
              {category.primary_category}
            </option>
          ))}
        </select>
      </label>
      <label>
        Amount (positive = inflow, negative = outflow)
        <input
          type="number"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />
      </label>
      <label>
        Description
        <input value={description} onChange={(e) => setDescription(e.target.value)} required />
      </label>
      <label>
        Date
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
      </label>
      <button type="submit" disabled={createTransaction.isPending}>
        Add transaction
      </button>
    </form>
  )
}

function SuggestedTransfers() {
  const { data } = useTransactions({ transfer_status: 'suggested' })
  const updateTransaction = useUpdateTransaction()
  const suggestions = data?.data ?? []

  if (suggestions.length === 0) return null

  return (
    <section>
      <h2>Suggested transfers</h2>
      <ul>
        {suggestions.map((txn) => (
          <li key={txn.id}>
            {txn.date} — {txn.description} ({txn.amount})
            <button
              type="button"
              onClick={() =>
                updateTransaction.mutate({ id: txn.id, input: { transfer_status: 'confirmed' } })
              }
              disabled={updateTransaction.isPending}
            >
              Confirm transfer
            </button>
            <button
              type="button"
              onClick={() =>
                updateTransaction.mutate({ id: txn.id, input: { transfer_status: 'rejected' } })
              }
              disabled={updateTransaction.isPending}
            >
              Not a transfer
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

function TransactionRow({
  transaction,
  categoryName,
}: {
  transaction: Transaction
  categoryName: string
}) {
  const updateTransaction = useUpdateTransaction()
  const deleteTransaction = useDeleteTransaction()
  const [editingNotes, setEditingNotes] = useState(false)
  const [notes, setNotes] = useState(transaction.notes ?? '')

  function handleSaveNotes() {
    updateTransaction.mutate(
      { id: transaction.id, input: { notes } },
      { onSuccess: () => setEditingNotes(false) },
    )
  }

  return (
    <li>
      {transaction.date} — {transaction.description} — {transaction.amount} ({categoryName})
      {transaction.pending && ' [pending]'}
      {transaction.is_transfer && ' [transfer]'}
      {editingNotes ? (
        <>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} />
          <button type="button" onClick={handleSaveNotes} disabled={updateTransaction.isPending}>
            Save notes
          </button>
        </>
      ) : (
        <button type="button" onClick={() => setEditingNotes(true)}>
          {transaction.notes ? `Notes: ${transaction.notes}` : 'Add note'}
        </button>
      )}
      <button
        type="button"
        onClick={() => deleteTransaction.mutate(transaction.id)}
        disabled={deleteTransaction.isPending}
      >
        Delete
      </button>
    </li>
  )
}

export function TransactionsPage() {
  const { data: accounts } = useAccounts({ active: true })
  const { data: categories } = useCategories('all')
  const [filters, setFilters] = useState<TransactionFilters>({ page: 1 })

  const { data, isLoading } = useTransactions(filters)
  const categoryNames = new Map((categories ?? []).map((c) => [c.id, c.primary_category]))

  function updateFilter(patch: Partial<TransactionFilters>) {
    setFilters((prev) => ({ ...prev, ...patch, page: 1 }))
  }

  return (
    <main>
      <h1>Transactions</h1>
      <CreateTransactionForm />
      <SuggestedTransfers />

      <h2>Filters</h2>
      <label>
        Filter by account
        <select
          value={filters.account_id ?? ''}
          onChange={(e) => updateFilter({ account_id: e.target.value || undefined })}
        >
          <option value="">All accounts</option>
          {(accounts ?? []).map((account) => (
            <option key={account.id} value={account.id}>
              {account.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Description contains
        <input
          value={filters.description ?? ''}
          onChange={(e) => updateFilter({ description: e.target.value || undefined })}
        />
      </label>

      <h2>All transactions</h2>
      {isLoading || !data ? (
        <p>Loading transactions…</p>
      ) : (
        <>
          <ul>
            {data.data.map((txn) => (
              <TransactionRow
                key={txn.id}
                transaction={txn}
                categoryName={txn.category_id ? (categoryNames.get(txn.category_id) ?? '') : 'none'}
              />
            ))}
          </ul>
          <p>
            Page {data.pagination.page} of {data.pagination.total_pages}
          </p>
          <button
            type="button"
            disabled={data.pagination.page <= 1}
            onClick={() => setFilters((prev) => ({ ...prev, page: (prev.page ?? 1) - 1 }))}
          >
            Previous
          </button>
          <button
            type="button"
            disabled={data.pagination.page >= data.pagination.total_pages}
            onClick={() => setFilters((prev) => ({ ...prev, page: (prev.page ?? 1) + 1 }))}
          >
            Next
          </button>
        </>
      )}
    </main>
  )
}
