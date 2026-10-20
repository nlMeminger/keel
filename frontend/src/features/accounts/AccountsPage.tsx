import { useState } from 'react'
import { ApiError } from '../../lib/api-client'
import {
  type Account,
  type AccountCreateInput,
  useAccounts,
  useCreateAccount,
  useDeactivateAccount,
  useUpdateAccount,
} from './api'
import { HoldingsSection } from './HoldingsSection'

const ACCOUNT_TYPES = [
  'checking',
  'savings',
  'credit_card',
  'investment',
  'loan',
  'mortgage',
  'student_loan',
] as const

type AccountType = (typeof ACCOUNT_TYPES)[number]

const DETAIL_FIELDS: Record<AccountType, { key: string; label: string; required?: boolean }[]> = {
  checking: [{ key: 'overdraft_limit', label: 'Overdraft limit' }],
  savings: [{ key: 'interest_rate', label: 'Interest rate (%)' }],
  credit_card: [
    { key: 'credit_limit', label: 'Credit limit', required: true },
    { key: 'apr', label: 'APR (%)' },
  ],
  investment: [{ key: 'account_subtype', label: 'Subtype (e.g. brokerage, 401k)' }],
  loan: [
    { key: 'principal', label: 'Principal', required: true },
    { key: 'interest_rate', label: 'Interest rate (%)' },
    { key: 'term_months', label: 'Term (months)' },
  ],
  mortgage: [
    { key: 'principal', label: 'Principal', required: true },
    { key: 'interest_rate', label: 'Interest rate (%)' },
    { key: 'term_months', label: 'Term (months)' },
    { key: 'escrow_balance', label: 'Escrow balance' },
  ],
  student_loan: [
    { key: 'principal', label: 'Principal', required: true },
    { key: 'interest_rate', label: 'Interest rate (%)' },
    { key: 'servicer', label: 'Servicer' },
  ],
}

function CreateAccountForm() {
  const createAccount = useCreateAccount()
  const [name, setName] = useState('')
  const [accountType, setAccountType] = useState<AccountType>('checking')
  const [balance, setBalance] = useState('0')
  const [detail, setDetail] = useState<Record<string, string>>({})

  function handleDetailChange(key: string, value: string) {
    setDetail((prev) => ({ ...prev, [key]: value }))
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const numericDetail: Record<string, number | string> = {}
    for (const field of DETAIL_FIELDS[accountType]) {
      const raw = detail[field.key]
      if (raw === undefined || raw === '') continue
      numericDetail[field.key] =
        field.key === 'servicer' || field.key === 'account_subtype' ? raw : Number(raw)
    }
    const input: AccountCreateInput = {
      name,
      account_type: accountType,
      balance,
      detail: numericDetail,
    }
    createAccount.mutate(input, {
      onSuccess: () => {
        setName('')
        setBalance('0')
        setDetail({})
      },
    })
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>Add account</h2>
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label>
        Type
        <select
          value={accountType}
          onChange={(e) => {
            setAccountType(e.target.value as AccountType)
            setDetail({})
          }}
        >
          {ACCOUNT_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </label>
      <label>
        Balance
        <input
          type="number"
          step="0.01"
          value={balance}
          onChange={(e) => setBalance(e.target.value)}
          required
        />
      </label>
      {DETAIL_FIELDS[accountType].map((field) => (
        <label key={field.key}>
          {field.label}
          <input
            value={detail[field.key] ?? ''}
            onChange={(e) => handleDetailChange(field.key, e.target.value)}
            required={field.required}
          />
        </label>
      ))}
      {createAccount.isError && (
        <p role="alert">
          {createAccount.error instanceof ApiError
            ? createAccount.error.message
            : 'Failed to create account.'}
        </p>
      )}
      <button type="submit" disabled={createAccount.isPending}>
        Add account
      </button>
    </form>
  )
}

function AccountRow({ account }: { account: Account }) {
  const updateAccount = useUpdateAccount()
  const deactivateAccount = useDeactivateAccount()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(account.name)
  const [balance, setBalance] = useState(account.balance)

  function handleSave() {
    updateAccount.mutate(
      { id: account.id, input: { name, balance } },
      { onSuccess: () => setEditing(false) },
    )
  }

  return (
    <li>
      {editing ? (
        <>
          <input value={name} onChange={(e) => setName(e.target.value)} />
          <input
            type="number"
            step="0.01"
            value={balance}
            onChange={(e) => setBalance(e.target.value)}
          />
          <button type="button" onClick={handleSave} disabled={updateAccount.isPending}>
            Save
          </button>
          <button type="button" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </>
      ) : (
        <>
          <strong>{account.name}</strong> ({account.account_type}) — {account.balance}
          {!account.is_active && ' [deactivated]'}
          <button type="button" onClick={() => setEditing(true)}>
            Edit
          </button>
          {account.is_active && (
            <button
              type="button"
              onClick={() => deactivateAccount.mutate(account.id)}
              disabled={deactivateAccount.isPending}
            >
              Deactivate
            </button>
          )}
        </>
      )}
      {account.account_type === 'investment' && <HoldingsSection accountId={account.id} />}
    </li>
  )
}

export function AccountsPage() {
  const [showInactive, setShowInactive] = useState(false)
  const { data: accounts, isLoading } = useAccounts({ active: !showInactive })

  return (
    <main>
      <h1>Accounts</h1>
      <CreateAccountForm />
      <label>
        <input
          type="checkbox"
          checked={showInactive}
          onChange={(e) => setShowInactive(e.target.checked)}
        />
        Show deactivated accounts only
      </label>
      {isLoading || !accounts ? (
        <p>Loading accounts…</p>
      ) : (
        <ul>
          {accounts.map((account) => (
            <AccountRow key={account.id} account={account} />
          ))}
        </ul>
      )}
    </main>
  )
}
