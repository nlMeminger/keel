import { Badge, Button, Group, Paper, Stack, Text, TextInput, Title } from '@mantine/core'
import { useState } from 'react'
import { type Asset, useAssets, useCreateAsset, useDeleteAsset, useUpdateAsset } from './api'

function CreateAssetForm() {
  const createAsset = useCreateAsset()
  const [name, setName] = useState('')
  const [assetType, setAssetType] = useState('')
  const [currentValue, setCurrentValue] = useState('')

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    createAsset.mutate(
      { name, asset_type: assetType, current_value: currentValue },
      {
        onSuccess: () => {
          setName('')
          setAssetType('')
          setCurrentValue('')
        },
      },
    )
  }

  return (
    <Paper withBorder p="lg" radius="md" component="form" onSubmit={handleSubmit}>
      <Stack>
        <Title order={2} size="h4">
          Add asset
        </Title>
        <TextInput label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
        <TextInput
          label="Type (e.g. real_estate, vehicle)"
          value={assetType}
          onChange={(e) => setAssetType(e.target.value)}
          required
        />
        <TextInput
          label="Current value"
          type="number"
          step="0.01"
          value={currentValue}
          onChange={(e) => setCurrentValue(e.target.value)}
          required
        />
        <Button type="submit" loading={createAsset.isPending}>
          Add asset
        </Button>
      </Stack>
    </Paper>
  )
}

function AssetRow({ asset }: { asset: Asset }) {
  const updateAsset = useUpdateAsset()
  const deleteAsset = useDeleteAsset()
  const [editing, setEditing] = useState(false)
  const [currentValue, setCurrentValue] = useState(asset.current_value)

  function handleSave() {
    updateAsset.mutate(
      { id: asset.id, input: { current_value: currentValue } },
      { onSuccess: () => setEditing(false) },
    )
  }

  return (
    <Paper component="li" withBorder p="md" radius="md" style={{ listStyle: 'none' }}>
      <Group justify="space-between">
        <Group gap="xs">
          <Text fw={500}>{asset.name}</Text>
          <Badge variant="light">{asset.asset_type}</Badge>
          {editing ? (
            <TextInput
              size="xs"
              type="number"
              step="0.01"
              value={currentValue}
              onChange={(e) => setCurrentValue(e.target.value)}
            />
          ) : (
            <Text c="dimmed">{asset.current_value}</Text>
          )}
        </Group>
        <Group gap="xs">
          {editing ? (
            <>
              <Button size="sm" onClick={handleSave} loading={updateAsset.isPending}>
                Save
              </Button>
              <Button size="sm" variant="subtle" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </>
          ) : (
            <Button size="sm" variant="subtle" onClick={() => setEditing(true)}>
              Edit
            </Button>
          )}
          <Button
            size="sm"
            variant="subtle"
            color="red"
            onClick={() => deleteAsset.mutate(asset.id)}
            loading={deleteAsset.isPending}
          >
            Delete
          </Button>
        </Group>
      </Group>
    </Paper>
  )
}

export function AssetsPage() {
  const { data: assets, isLoading } = useAssets()

  return (
    <Stack>
      <Title order={1}>Assets</Title>
      <CreateAssetForm />
      {isLoading || !assets ? (
        <Text>Loading assets…</Text>
      ) : (
        <Stack gap="sm" component="ul" style={{ padding: 0 }}>
          {assets.map((asset) => (
            <AssetRow key={asset.id} asset={asset} />
          ))}
        </Stack>
      )}
    </Stack>
  )
}
