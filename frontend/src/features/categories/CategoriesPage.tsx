import {
  Alert,
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
    <Paper withBorder p="lg" radius="md" component="form" onSubmit={handleSubmit}>
      <Group align="flex-end">
        <TextInput
          label="New category"
          value={primaryCategory}
          onChange={(e) => setPrimaryCategory(e.target.value)}
          required
          style={{ flex: 1 }}
        />
        <Button type="submit" loading={createCategory.isPending}>
          Add category
        </Button>
      </Group>
    </Paper>
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
    <Paper component="li" withBorder p="md" radius="md" style={{ listStyle: 'none' }}>
      {editing ? (
        <Group>
          <TextInput value={name} onChange={(e) => setName(e.target.value)} />
          <Button size="sm" onClick={handleSave} loading={updateCategory.isPending}>
            Save
          </Button>
          <Button size="sm" variant="subtle" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </Group>
      ) : (
        <Group justify="space-between">
          <Text>{category.primary_category}</Text>
          <Group gap="xs">
            <Button size="sm" variant="subtle" onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button
              size="sm"
              variant="subtle"
              color="red"
              onClick={() => handleDelete()}
              loading={deleteCategory.isPending}
            >
              Delete
            </Button>
          </Group>
        </Group>
      )}
      {conflict && (
        <Alert role="alert" color="yellow" mt="sm" title="Category still in use">
          <Stack gap="xs">
            <Text size="sm">
              This category is still used by some transactions. Reassign them to:
            </Text>
            <NativeSelect
              value={reassignTo}
              onChange={(e) => setReassignTo(e.target.value)}
              data={[
                { value: '', label: 'Choose a category…' },
                ...reassignOptions.map((option) => ({
                  value: option.id,
                  label: option.primary_category,
                })),
              ]}
            />
            <Button
              size="sm"
              onClick={() => handleDelete(reassignTo)}
              disabled={!reassignTo}
              loading={deleteCategory.isPending}
            >
              Reassign and delete
            </Button>
          </Stack>
        </Alert>
      )}
    </Paper>
  )
}

export function CategoriesPage() {
  const { data: systemCategories } = useCategories('system')
  const { data: customCategories, isLoading } = useCategories('custom')
  const allCategories = [...(systemCategories ?? []), ...(customCategories ?? [])]

  return (
    <Stack>
      <Title order={1}>Categories</Title>
      <CreateCategoryForm />

      <Title order={2} size="h4">
        System categories
      </Title>
      <Group gap="xs">
        {(systemCategories ?? []).map((category) => (
          <Badge key={category.id} variant="light" size="lg">
            {category.primary_category}
          </Badge>
        ))}
      </Group>

      <Title order={2} size="h4">
        Your categories
      </Title>
      {isLoading || !customCategories ? (
        <Text>Loading categories…</Text>
      ) : (
        <Stack gap="sm" component="ul" style={{ padding: 0 }}>
          {customCategories.map((category) => (
            <CustomCategoryRow
              key={category.id}
              category={category}
              allCategories={allCategories}
            />
          ))}
        </Stack>
      )}
    </Stack>
  )
}
