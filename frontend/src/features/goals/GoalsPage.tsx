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
    <form onSubmit={handleSubmit}>
      <h2>Add goal</h2>
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label>
        Target amount
        <input
          type="number"
          step="0.01"
          value={targetAmount}
          onChange={(e) => setTargetAmount(e.target.value)}
          required
        />
      </label>
      <label>
        Target date (optional)
        <input type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
      </label>
      <button type="submit" disabled={createGoal.isPending}>
        Add goal
      </button>
    </form>
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
    <li>
      <strong>{goal.name}</strong>: {goal.progress_amount} of {goal.target_amount} ({percent}%)
      <progress value={progress} max={target} />
      <form onSubmit={handleContribute}>
        <input
          type="number"
          step="0.01"
          placeholder="Contribution amount"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />
        <button type="submit" disabled={addContribution.isPending}>
          Add contribution
        </button>
      </form>
      <button
        type="button"
        onClick={() => deleteGoal.mutate(goal.id)}
        disabled={deleteGoal.isPending}
      >
        Delete
      </button>
    </li>
  )
}

export function GoalsPage() {
  const { data: goals, isLoading } = useGoals()

  return (
    <main>
      <h1>Savings goals</h1>
      <CreateGoalForm />
      {isLoading || !goals ? (
        <p>Loading goals…</p>
      ) : (
        <ul>
          {goals.map((goal) => (
            <GoalRow key={goal.id} goal={goal} />
          ))}
        </ul>
      )}
    </main>
  )
}
