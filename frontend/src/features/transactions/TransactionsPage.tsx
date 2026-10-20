import {
  Badge,
  Button,
  Group,
  NativeSelect,
  Paper,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
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
    <Paper withBorder p="lg" radius="md" component="form" onSubmit={handleSubmit}>
      <Stack>
        <Title order={2} size="h4">
          Add transaction
        </Title>
        <NativeSelect
          label="Account"
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
          required
          data={[
            { value: '', label: 'Select account…' },
            ...(accounts ?? []).map((account) => ({ value: account.id, label: account.name })),
          ]}
        />
        <NativeSelect
          label="Category"
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          data={[
            { value: '', label: 'Uncategorized' },
            ...(categories ?? []).map((category) => ({
              value: category.id,
              label: category.primary_category,
            })),
          ]}
        />
        <TextInput
          label="Amount (positive = inflow, negative = outflow)"
          type="number"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />
        <TextInput
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          required
        />
        <TextInput
          label="Date"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          required
        />
        <Button type="submit" loading={createTransaction.isPending}>
          Add transaction
        </Button>
      </Stack>
    </Paper>
  )
}

function SuggestedTransfers() {
  const { data } = useTransactions({ transfer_status: 'suggested' })
  const updateTransaction = useUpdateTransaction()
  const suggestions = data?.data ?? []

  if (suggestions.length === 0) return null

  return (
    <Paper withBorder p="lg" radius="md">
      <Stack>
        <Title order={2} size="h4">
          Suggested transfers
        </Title>
        {suggestions.map((txn) => (
          <Group key={txn.id} justify="space-between">
            <Text size="sm">
              {txn.date} — {txn.description} ({txn.amount})
            </Text>
            <Group gap="xs">
              <Button
                size="sm"
                onClick={() =>
                  updateTransaction.mutate({ id: txn.id, input: { transfer_status: 'confirmed' } })
                }
                loading={updateTransaction.isPending}
              >
                Confirm transfer
              </Button>
              <Button
                size="sm"
                variant="subtle"
                onClick={() =>
                  updateTransaction.mutate({ id: txn.id, input: { transfer_status: 'rejected' } })
                }
                loading={updateTransaction.isPending}
              >
                Not a transfer
              </Button>
            </Group>
          </Group>
        ))}
      </Stack>
    </Paper>
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
    <Table.Tr>
      <Table.Td>{transaction.date}</Table.Td>
      <Table.Td>
        {transaction.description}{' '}
        <Text component="span" c="dimmed" size="sm">
          ({categoryName})
        </Text>
      </Table.Td>
      <Table.Td>{transaction.amount}</Table.Td>
      <Table.Td>
        <Group gap={4}>
          {transaction.pending && <Badge size="sm">pending</Badge>}
          {transaction.is_transfer && (
            <Badge size="sm" color="grape">
              transfer
            </Badge>
          )}
        </Group>
      </Table.Td>
      <Table.Td>
        {editingNotes ? (
          <Group gap="xs" wrap="nowrap">
            <TextInput
              size="xs"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              aria-label="Notes"
            />
            <Button size="xs" onClick={handleSaveNotes} loading={updateTransaction.isPending}>
              Save notes
            </Button>
          </Group>
        ) : (
          <Button size="xs" variant="subtle" onClick={() => setEditingNotes(true)}>
            {transaction.notes ? `Notes: ${transaction.notes}` : 'Add note'}
          </Button>
        )}
      </Table.Td>
      <Table.Td>
        <Button
          size="xs"
          variant="subtle"
          color="red"
          onClick={() => deleteTransaction.mutate(transaction.id)}
          loading={deleteTransaction.isPending}
        >
          Delete
        </Button>
      </Table.Td>
    </Table.Tr>
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
    <Stack>
      <Title order={1}>Transactions</Title>
      <CreateTransactionForm />
      <SuggestedTransfers />

      <Paper withBorder p="lg" radius="md">
        <Stack>
          <Title order={2} size="h4">
            Filters
          </Title>
          <Group grow>
            <NativeSelect
              label="Filter by account"
              value={filters.account_id ?? ''}
              onChange={(e) => updateFilter({ account_id: e.target.value || undefined })}
              data={[
                { value: '', label: 'All accounts' },
                ...(accounts ?? []).map((account) => ({ value: account.id, label: account.name })),
              ]}
            />
            <TextInput
              label="Description contains"
              value={filters.description ?? ''}
              onChange={(e) => updateFilter({ description: e.target.value || undefined })}
            />
          </Group>
        </Stack>
      </Paper>

      <Title order={2} size="h4">
        All transactions
      </Title>
      {isLoading || !data ? (
        <Text>Loading transactions…</Text>
      ) : (
        <>
          <Table.ScrollContainer minWidth={700}>
            <Table verticalSpacing="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Date</Table.Th>
                  <Table.Th>Description</Table.Th>
                  <Table.Th>Amount</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Notes</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.data.map((txn) => (
                  <TransactionRow
                    key={txn.id}
                    transaction={txn}
                    categoryName={
                      txn.category_id ? (categoryNames.get(txn.category_id) ?? '') : 'none'
                    }
                  />
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              Page {data.pagination.page} of {data.pagination.total_pages}
            </Text>
            <Group gap="xs">
              <Button
                size="sm"
                variant="default"
                disabled={data.pagination.page <= 1}
                onClick={() => setFilters((prev) => ({ ...prev, page: (prev.page ?? 1) - 1 }))}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="default"
                disabled={data.pagination.page >= data.pagination.total_pages}
                onClick={() => setFilters((prev) => ({ ...prev, page: (prev.page ?? 1) + 1 }))}
              >
                Next
              </Button>
            </Group>
          </Group>
        </>
      )}
    </Stack>
  )
}
