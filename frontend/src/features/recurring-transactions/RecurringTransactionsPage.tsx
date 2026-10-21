import {
  Badge,
  Button,
  Group,
  NativeSelect,
  Paper,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import {
  useCreateRecurringTransaction,
  useDeleteRecurringTransaction,
  useRecordPayment,
  useRecurringTransactions,
  useUpdateRecurringTransaction,
  type RecurringTransaction,
} from './api'

const FREQUENCIES = ['weekly', 'monthly', 'quarterly', 'yearly'] as const

function CreateRecurringForm() {
  const createRecurring = useCreateRecurringTransaction()
  const [name, setName] = useState('')
  const [amountExpected, setAmountExpected] = useState('')
  const [frequency, setFrequency] = useState<(typeof FREQUENCIES)[number]>('monthly')

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    createRecurring.mutate(
      { name, amount_expected: amountExpected, frequency, is_bill: false },
      {
        onSuccess: () => {
          setName('')
          setAmountExpected('')
        },
      },
    )
  }

  return (
    <Paper withBorder p="lg" radius="md" component="form" onSubmit={handleSubmit}>
      <Stack>
        <Title order={2} size="h4">
          Add recurring transaction
        </Title>
        <TextInput label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
        <TextInput
          label="Expected amount"
          type="number"
          step="0.01"
          value={amountExpected}
          onChange={(e) => setAmountExpected(e.target.value)}
          required
        />
        <NativeSelect
          label="Frequency"
          value={frequency}
          onChange={(e) => setFrequency(e.target.value as (typeof FREQUENCIES)[number])}
          data={FREQUENCIES.map((f) => ({ value: f, label: f }))}
        />
        <Button type="submit" loading={createRecurring.isPending}>
          Add recurring transaction
        </Button>
      </Stack>
    </Paper>
  )
}

function RecurringRow({ recurring }: { recurring: RecurringTransaction }) {
  const updateRecurring = useUpdateRecurringTransaction()
  const deleteRecurring = useDeleteRecurringTransaction()
  const recordPayment = useRecordPayment()
  const [paymentAmount, setPaymentAmount] = useState(recurring.amount_expected)

  function handleRecordPayment(event: React.FormEvent) {
    event.preventDefault()
    recordPayment.mutate({
      id: recurring.id,
      input: { amount: paymentAmount, date: new Date().toISOString().slice(0, 10) },
    })
  }

  return (
    <Paper component="li" withBorder p="md" radius="md" style={{ listStyle: 'none' }}>
      <Stack gap="xs">
        <Group justify="space-between">
          <Group gap="xs">
            <Text fw={500}>{recurring.name}</Text>
            {recurring.is_bill && <Badge color="orange">Bill</Badge>}
          </Group>
          <Button
            size="sm"
            variant="subtle"
            color="red"
            onClick={() => deleteRecurring.mutate(recurring.id)}
            loading={deleteRecurring.isPending}
          >
            Remove
          </Button>
        </Group>
        <Text size="sm" c="dimmed">
          {recurring.amount_expected} / {recurring.frequency} — last paid{' '}
          {recurring.last_paid_date ?? 'never'}
        </Text>
        <Group gap="xs">
          <Button
            size="xs"
            variant="light"
            onClick={() =>
              updateRecurring.mutate({
                id: recurring.id,
                input: { is_bill: !recurring.is_bill },
              })
            }
          >
            {recurring.is_bill ? 'Unmark as bill' : 'Mark as bill'}
          </Button>
        </Group>
        <Group component="form" onSubmit={handleRecordPayment} gap="xs">
          <TextInput
            type="number"
            step="0.01"
            aria-label={`Payment amount for ${recurring.name}`}
            value={paymentAmount}
            onChange={(e) => setPaymentAmount(e.target.value)}
            required
            style={{ flex: 1 }}
          />
          <Button type="submit" size="sm" loading={recordPayment.isPending}>
            Record payment
          </Button>
        </Group>
      </Stack>
    </Paper>
  )
}

export function RecurringTransactionsPage() {
  const { data: recurring, isLoading } = useRecurringTransactions()

  return (
    <Stack>
      <Title order={1}>Recurring transactions</Title>
      <CreateRecurringForm />
      {isLoading || !recurring ? (
        <Text>Loading recurring transactions…</Text>
      ) : (
        <Stack gap="sm" component="ul" style={{ padding: 0 }}>
          {recurring.map((row) => (
            <RecurringRow key={row.id} recurring={row} />
          ))}
        </Stack>
      )}
    </Stack>
  )
}
