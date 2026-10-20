import { useState } from 'react'
import { ApiError } from '../../lib/api-client'
import {
  type Category,
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useUpdateCategory,
} from './api'

function CreateCategoryForm() {
  const createCategory = useCreateCategory()
  const [primaryCategory, setPrimaryCategory] = useState('')

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    createCategory.mutate(
      { primary_category: primaryCategory },
      { onSuccess: () => setPrimaryCategory('') },
    )
  }

  return (
    <form onSubmit={handleSubmit}>
      <label>
        New category
        <input
          value={primaryCategory}
          onChange={(e) => setPrimaryCategory(e.target.value)}
          required
        />
      </label>
      <button type="submit" disabled={createCategory.isPending}>
        Add category
      </button>
    </form>
  )
}

function CustomCategoryRow({
  category,
  allCategories,
}: {
  category: Category
  allCategories: Category[]
}) {
  const updateCategory = useUpdateCategory()
  const deleteCategory = useDeleteCategory()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(category.primary_category)
  const [conflict, setConflict] = useState(false)
  const [reassignTo, setReassignTo] = useState('')

  function handleSave() {
    updateCategory.mutate(
      { id: category.id, input: { primary_category: name } },
      { onSuccess: () => setEditing(false) },
    )
  }

  function handleDelete(reassign?: string) {
    deleteCategory.mutate(
      { id: category.id, reassignTo: reassign },
      {
        onSuccess: () => setConflict(false),
        onError: (error) => {
          if (error instanceof ApiError && error.status === 409) {
            setConflict(true)
          }
        },
      },
    )
  }

  const reassignOptions = allCategories.filter((c) => c.id !== category.id)

  return (
    <li>
      {editing ? (
        <>
          <input value={name} onChange={(e) => setName(e.target.value)} />
          <button type="button" onClick={handleSave} disabled={updateCategory.isPending}>
            Save
          </button>
          <button type="button" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </>
      ) : (
        <>
          {category.primary_category}
          <button type="button" onClick={() => setEditing(true)}>
            Edit
          </button>
          <button type="button" onClick={() => handleDelete()} disabled={deleteCategory.isPending}>
            Delete
          </button>
        </>
      )}
      {conflict && (
        <div role="alert">
          <p>This category is still used by some transactions. Reassign them to:</p>
          <select value={reassignTo} onChange={(e) => setReassignTo(e.target.value)}>
            <option value="">Choose a category…</option>
            {reassignOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.primary_category}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => handleDelete(reassignTo)}
            disabled={!reassignTo || deleteCategory.isPending}
          >
            Reassign and delete
          </button>
        </div>
      )}
    </li>
  )
}

export function CategoriesPage() {
  const { data: systemCategories } = useCategories('system')
  const { data: customCategories, isLoading } = useCategories('custom')
  const allCategories = [...(systemCategories ?? []), ...(customCategories ?? [])]

  return (
    <main>
      <h1>Categories</h1>
      <CreateCategoryForm />

      <h2>System categories</h2>
      <ul>
        {(systemCategories ?? []).map((category) => (
          <li key={category.id}>{category.primary_category}</li>
        ))}
      </ul>

      <h2>Your categories</h2>
      {isLoading || !customCategories ? (
        <p>Loading categories…</p>
      ) : (
        <ul>
          {customCategories.map((category) => (
            <CustomCategoryRow
              key={category.id}
              category={category}
              allCategories={allCategories}
            />
          ))}
        </ul>
      )}
    </main>
  )
}
