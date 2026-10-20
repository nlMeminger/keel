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
    <form onSubmit={handleSubmit}>
      <h2>Add budget</h2>
      <label>
        Category
        <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
          <option value="">Overall (all spending)</option>
          {(categories ?? []).map((category) => (
            <option key={category.id} value={category.id}>
              {category.primary_category}
            </option>
          ))}
        </select>
      </label>
      <label>
        Monthly limit
        <input
          type="number"
          step="0.01"
          value={amountLimit}
          onChange={(e) => setAmountLimit(e.target.value)}
          required
        />
      </label>
      <label>
        Start date
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          required
        />
      </label>
      <button type="submit" disabled={createBudget.isPending}>
        Add budget
      </button>
    </form>
  )
}

function BudgetRow({ budget, categoryName }: { budget: Budget; categoryName: string }) {
  const deleteBudget = useDeleteBudget()
  const limit = Number(budget.amount_limit)
  const spent = Number(budget.spend_so_far)
  const percent = limit > 0 ? Math.min(100, Math.round((spent / limit) * 100)) : 0

  return (
    <li>
      <strong>{categoryName}</strong>: {budget.spend_so_far} of {budget.amount_limit} spent (
      {percent}%)
      <progress value={spent} max={limit} />
      <button
        type="button"
        onClick={() => deleteBudget.mutate(budget.id)}
        disabled={deleteBudget.isPending}
      >
        Delete
      </button>
    </li>
  )
}

export function BudgetsPage() {
  const { data: categories } = useCategories('all')
  const { data: budgets, isLoading } = useBudgets()
  const categoryNames = new Map((categories ?? []).map((c) => [c.id, c.primary_category]))

  return (
    <main>
      <h1>Budgets</h1>
      <CreateBudgetForm />
      {isLoading || !budgets ? (
        <p>Loading budgets…</p>
      ) : (
        <ul>
          {budgets.map((budget) => (
            <BudgetRow
              key={budget.id}
              budget={budget}
              categoryName={
                budget.category_id ? (categoryNames.get(budget.category_id) ?? '') : 'Overall'
              }
            />
          ))}
        </ul>
      )}
    </main>
  )
}
