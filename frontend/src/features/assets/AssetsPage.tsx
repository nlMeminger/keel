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
    <form onSubmit={handleSubmit}>
      <h2>Add asset</h2>
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label>
        Type (e.g. real_estate, vehicle)
        <input value={assetType} onChange={(e) => setAssetType(e.target.value)} required />
      </label>
      <label>
        Current value
        <input
          type="number"
          step="0.01"
          value={currentValue}
          onChange={(e) => setCurrentValue(e.target.value)}
          required
        />
      </label>
      <button type="submit" disabled={createAsset.isPending}>
        Add asset
      </button>
    </form>
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
    <li>
      {editing ? (
        <>
          <input
            type="number"
            step="0.01"
            value={currentValue}
            onChange={(e) => setCurrentValue(e.target.value)}
          />
          <button type="button" onClick={handleSave} disabled={updateAsset.isPending}>
            Save
          </button>
          <button type="button" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </>
      ) : (
        <>
          <strong>{asset.name}</strong> ({asset.asset_type}) — {asset.current_value}
          <button type="button" onClick={() => setEditing(true)}>
            Edit
          </button>
        </>
      )}
      <button
        type="button"
        onClick={() => deleteAsset.mutate(asset.id)}
        disabled={deleteAsset.isPending}
      >
        Delete
      </button>
    </li>
  )
}

export function AssetsPage() {
  const { data: assets, isLoading } = useAssets()

  return (
    <main>
      <h1>Assets</h1>
      <CreateAssetForm />
      {isLoading || !assets ? (
        <p>Loading assets…</p>
      ) : (
        <ul>
          {assets.map((asset) => (
            <AssetRow key={asset.id} asset={asset} />
          ))}
        </ul>
      )}
    </main>
  )
}
