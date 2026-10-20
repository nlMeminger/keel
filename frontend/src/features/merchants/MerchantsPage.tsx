import { Button, Group, Paper, Stack, Text, TextInput, Title } from '@mantine/core'
import { useState } from 'react'
import {
  type Merchant,
  useCreateMerchant,
  useDeleteMerchant,
  useMerchants,
  useUpdateMerchant,
} from './api'

function parseAliases(raw: string): string[] {
  return raw
    .split(',')
    .map((a) => a.trim())
    .filter((a) => a.length > 0)
}

function CreateMerchantForm() {
  const createMerchant = useCreateMerchant()
  const [name, setName] = useState('')
  const [aliasesText, setAliasesText] = useState('')

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    createMerchant.mutate(
      { name, aliases: parseAliases(aliasesText) },
      {
        onSuccess: () => {
          setName('')
          setAliasesText('')
        },
      },
    )
  }

  return (
    <Paper withBorder p="lg" radius="md" component="form" onSubmit={handleSubmit}>
      <Stack>
        <Title order={2} size="h4">
          Add merchant
        </Title>
        <TextInput label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
        <TextInput
          label="Aliases (comma-separated)"
          value={aliasesText}
          onChange={(e) => setAliasesText(e.target.value)}
        />
        <Button type="submit" loading={createMerchant.isPending}>
          Add merchant
        </Button>
      </Stack>
    </Paper>
  )
}

function MerchantRow({ merchant }: { merchant: Merchant }) {
  const updateMerchant = useUpdateMerchant()
  const deleteMerchant = useDeleteMerchant()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(merchant.name)
  const [aliasesText, setAliasesText] = useState(merchant.aliases.join(', '))

  function handleSave() {
    updateMerchant.mutate(
      { id: merchant.id, input: { name, aliases: parseAliases(aliasesText) } },
      { onSuccess: () => setEditing(false) },
    )
  }

  return (
    <Paper component="li" withBorder p="md" radius="md" style={{ listStyle: 'none' }}>
      {editing ? (
        <Group>
          <TextInput value={name} onChange={(e) => setName(e.target.value)} />
          <TextInput value={aliasesText} onChange={(e) => setAliasesText(e.target.value)} />
          <Button size="sm" onClick={handleSave} loading={updateMerchant.isPending}>
            Save
          </Button>
          <Button size="sm" variant="subtle" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </Group>
      ) : (
        <Group justify="space-between">
          <Text>
            <Text component="span" fw={500}>
              {merchant.name}
            </Text>
            {merchant.aliases.length > 0 && (
              <Text component="span" c="dimmed">
                {' '}
                ({merchant.aliases.join(', ')})
              </Text>
            )}
          </Text>
          <Group gap="xs">
            <Button size="sm" variant="subtle" onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button
              size="sm"
              variant="subtle"
              color="red"
              onClick={() => deleteMerchant.mutate(merchant.id)}
              loading={deleteMerchant.isPending}
            >
              Delete
            </Button>
          </Group>
        </Group>
      )}
    </Paper>
  )
}

export function MerchantsPage() {
  const { data: merchants, isLoading } = useMerchants()

  return (
    <Stack>
      <Title order={1}>Merchants</Title>
      <CreateMerchantForm />
      {isLoading || !merchants ? (
        <Text>Loading merchants…</Text>
      ) : (
        <Stack gap="sm" component="ul" style={{ padding: 0 }}>
          {merchants.map((merchant) => (
            <MerchantRow key={merchant.id} merchant={merchant} />
          ))}
        </Stack>
      )}
    </Stack>
  )
}
