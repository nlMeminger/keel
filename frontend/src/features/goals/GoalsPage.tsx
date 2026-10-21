import { Button, Group, Paper, Progress, Stack, Text, TextInput, Title } from '@mantine/core'
import { useState } from 'react'
import { type Goal, useAddContribution, useCreateGoal, useDeleteGoal, useGoals } from './api'

function CreateGoalForm() {
  const createGoal = useCreateGoal()
  const [name, setName] = useState('')
  const [targetAmount, setTargetAmount] = useState('')
  const [targetDate, setTargetDate] = useState('')

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    createGoal.mutate(
      { name, target_amount: targetAmount, target_date: targetDate || null },
      {
        onSuccess: () => {
          setName('')
          setTargetAmount('')
          setTargetDate('')
        },
      },
    )
  }

  return (
    <Paper withBorder p="lg" radius="md" component="form" onSubmit={handleSubmit}>
      <Stack>
        <Title order={2} size="h4">
          Add goal
        </Title>
        <TextInput label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
        <TextInput
          label="Target amount"
          type="number"
          step="0.01"
          value={targetAmount}
          onChange={(e) => setTargetAmount(e.target.value)}
          required
        />
        <TextInput
          label="Target date (optional)"
          type="date"
          value={targetDate}
          onChange={(e) => setTargetDate(e.target.value)}
        />
        <Button type="submit" loading={createGoal.isPending}>
          Add goal
        </Button>
      </Stack>
    </Paper>
  )
}

function GoalRow({ goal }: { goal: Goal }) {
  const deleteGoal = useDeleteGoal()
  const addContribution = useAddContribution()
  const [amount, setAmount] = useState('')

  const target = Number(goal.target_amount)
  const progress = Number(goal.progress_amount)
  const percent = target > 0 ? Math.min(100, Math.round((progress / target) * 100)) : 0

  function handleContribute(event: React.FormEvent) {
    event.preventDefault()
    addContribution.mutate(
      { goalId: goal.id, input: { amount, date: new Date().toISOString().slice(0, 10) } },
      { onSuccess: () => setAmount('') },
    )
  }

  return (
    <Paper component="li" withBorder p="md" radius="md" style={{ listStyle: 'none' }}>
      <Stack gap="xs">
        <Group justify="space-between">
          <Text fw={500}>{goal.name}</Text>
          <Button
            size="sm"
            variant="subtle"
            color="red"
            onClick={() => deleteGoal.mutate(goal.id)}
            loading={deleteGoal.isPending}
          >
            Delete
          </Button>
        </Group>
        <Text size="sm" c="dimmed">
          {goal.progress_amount} of {goal.target_amount} ({percent}%)
        </Text>
        <Progress value={percent} />
        <Group component="form" onSubmit={handleContribute} gap="xs">
          <TextInput
            type="number"
            step="0.01"
            placeholder="Contribution amount"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
            style={{ flex: 1 }}
          />
          <Button type="submit" size="sm" loading={addContribution.isPending}>
            Add contribution
          </Button>
        </Group>
      </Stack>
    </Paper>
  )
}

export function GoalsPage() {
  const { data: goals, isLoading } = useGoals()

  return (
    <Stack>
      <Title order={1}>Savings goals</Title>
      <CreateGoalForm />
      {isLoading || !goals ? (
        <Text>Loading goals…</Text>
      ) : (
        <Stack gap="sm" component="ul" style={{ padding: 0 }}>
          {goals.map((goal) => (
            <GoalRow key={goal.id} goal={goal} />
          ))}
        </Stack>
      )}
    </Stack>
  )
}
