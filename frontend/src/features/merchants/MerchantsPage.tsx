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
    <form onSubmit={handleSubmit}>
      <h2>Add merchant</h2>
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label>
        Aliases (comma-separated)
        <input value={aliasesText} onChange={(e) => setAliasesText(e.target.value)} />
      </label>
      <button type="submit" disabled={createMerchant.isPending}>
        Add merchant
      </button>
    </form>
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
    <li>
      {editing ? (
        <>
          <input value={name} onChange={(e) => setName(e.target.value)} />
          <input value={aliasesText} onChange={(e) => setAliasesText(e.target.value)} />
          <button type="button" onClick={handleSave} disabled={updateMerchant.isPending}>
            Save
          </button>
          <button type="button" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </>
      ) : (
        <>
          <strong>{merchant.name}</strong>
          {merchant.aliases.length > 0 && ` (${merchant.aliases.join(', ')})`}
          <button type="button" onClick={() => setEditing(true)}>
            Edit
          </button>
          <button
            type="button"
            onClick={() => deleteMerchant.mutate(merchant.id)}
            disabled={deleteMerchant.isPending}
          >
            Delete
          </button>
        </>
      )}
    </li>
  )
}

export function MerchantsPage() {
  const { data: merchants, isLoading } = useMerchants()

  return (
    <main>
      <h1>Merchants</h1>
      <CreateMerchantForm />
      {isLoading || !merchants ? (
        <p>Loading merchants…</p>
      ) : (
        <ul>
          {merchants.map((merchant) => (
            <MerchantRow key={merchant.id} merchant={merchant} />
          ))}
        </ul>
      )}
    </main>
  )
}
