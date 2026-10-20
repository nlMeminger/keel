import {
  Button,
  Group,
  NativeSelect,
  Paper,
  Progress,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useCategories } from '../categories/api'
import { type Budget, useBudgets, useCreateBudget, useDeleteBudget } from './api'

function CreateBudgetForm() {
  const { data: categories } = useCategories('all')
  const createBudget = useCreateBudget()
  const [categoryId, setCategoryId] = useState('')
  const [amountLimit, setAmountLimit] = useState('')
  const [startDate, setStartDate] = useState('')

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    createBudget.mutate(
      { category_id: categoryId || null, amount_limit: amountLimit, start_date: startDate },
      {
        onSuccess: () => {
          setAmountLimit('')
        },
      },
    )
  }

  return (
    <Paper withBorder p="lg" radius="md" component="form" onSubmit={handleSubmit}>
      <Stack>
        <Title order={2} size="h4">
          Add budget
        </Title>
        <NativeSelect
          label="Category"
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          data={[
            { value: '', label: 'Overall (all spending)' },
            ...(categories ?? []).map((category) => ({
              value: category.id,
              label: category.primary_category,
            })),
          ]}
        />
        <TextInput
          label="Monthly limit"
          type="number"
          step="0.01"
          value={amountLimit}
          onChange={(e) => setAmountLimit(e.target.value)}
          required
        />
        <TextInput
          label="Start date"
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          required
        />
        <Button type="submit" loading={createBudget.isPending}>
          Add budget
        </Button>
      </Stack>
    </Paper>
  )
}

function BudgetRow({ budget, categoryName }: { budget: Budget; categoryName: string }) {
  const deleteBudget = useDeleteBudget()
  const limit = Number(budget.amount_limit)
  const spent = Number(budget.spend_so_far)
  const percent = limit > 0 ? Math.min(100, Math.round((spent / limit) * 100)) : 0

  return (
    <Paper component="li" withBorder p="md" radius="md" style={{ listStyle: 'none' }}>
      <Stack gap="xs">
        <Group justify="space-between">
          <Text fw={500}>{categoryName}</Text>
          <Button
            size="sm"
            variant="subtle"
            color="red"
            onClick={() => deleteBudget.mutate(budget.id)}
            loading={deleteBudget.isPending}
          >
            Delete
          </Button>
        </Group>
        <Text size="sm" c="dimmed">
          {budget.spend_so_far} of {budget.amount_limit} spent ({percent}%)
        </Text>
        <Progress value={percent} color={percent >= 100 ? 'red' : 'teal'} />
      </Stack>
    </Paper>
  )
}

export function BudgetsPage() {
  const { data: categories } = useCategories('all')
  const { data: budgets, isLoading } = useBudgets()
  const categoryNames = new Map((categories ?? []).map((c) => [c.id, c.primary_category]))

  return (
    <Stack>
      <Title order={1}>Budgets</Title>
      <CreateBudgetForm />
      {isLoading || !budgets ? (
        <Text>Loading budgets…</Text>
      ) : (
        <Stack gap="sm" component="ul" style={{ padding: 0 }}>
          {budgets.map((budget) => (
            <BudgetRow
              key={budget.id}
              budget={budget}
              categoryName={
                budget.category_id ? (categoryNames.get(budget.category_id) ?? '') : 'Overall'
              }
            />
          ))}
        </Stack>
      )}
    </Stack>
  )
}
