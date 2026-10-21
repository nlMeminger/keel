import {
  Badge,
  Button,
  Checkbox,
  Group,
  NativeSelect,
  Paper,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../lib/api-client'
import { ACCOUNT_TYPES, DETAIL_FIELDS, type AccountType } from './account-types'
import {
  type Account,
  type AccountCreateInput,
  useAccounts,
  useCreateAccount,
  useDeactivateAccount,
  useUpdateAccount,
} from './api'
import { HoldingsSection } from './HoldingsSection'

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
    <Paper withBorder p="lg" radius="md" component="form" onSubmit={handleSubmit}>
      <Stack>
        <Title order={2} size="h4">
          Add account
        </Title>
        <TextInput label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
        <NativeSelect
          label="Type"
          value={accountType}
          onChange={(e) => {
            setAccountType(e.target.value as AccountType)
            setDetail({})
          }}
          data={ACCOUNT_TYPES.map((type) => ({ value: type, label: type }))}
        />
        <TextInput
          label="Balance"
          type="number"
          step="0.01"
          value={balance}
          onChange={(e) => setBalance(e.target.value)}
          required
        />
        {DETAIL_FIELDS[accountType].map((field) => (
          <TextInput
            key={field.key}
            label={field.label}
            value={detail[field.key] ?? ''}
            onChange={(e) => handleDetailChange(field.key, e.target.value)}
            required={field.required}
          />
        ))}
        {createAccount.isError && (
          <Text role="alert" c="red" size="sm">
            {createAccount.error instanceof ApiError
              ? createAccount.error.message
              : 'Failed to create account.'}
          </Text>
        )}
        <Button type="submit" loading={createAccount.isPending}>
          Add account
        </Button>
      </Stack>
    </Paper>
  )
}

export function AccountRow({ account }: { account: Account }) {
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
    <Paper component="li" withBorder p="md" radius="md" style={{ listStyle: 'none' }}>
      {editing ? (
        <Group>
          <TextInput value={name} onChange={(e) => setName(e.target.value)} />
          <TextInput
            type="number"
            step="0.01"
            value={balance}
            onChange={(e) => setBalance(e.target.value)}
          />
          <Button size="sm" onClick={handleSave} loading={updateAccount.isPending}>
            Save
          </Button>
          <Button size="sm" variant="subtle" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </Group>
      ) : (
        <Group justify="space-between">
          <Group gap="xs">
            <Text component={Link} to={`/accounts/${account.id}`} fw={500}>
              {account.name}
            </Text>
            <Badge variant="light">{account.account_type}</Badge>
            <Text c="dimmed">{account.balance}</Text>
            {!account.is_active && (
              <Badge color="gray" variant="light">
                deactivated
              </Badge>
            )}
          </Group>
          <Group gap="xs">
            <Button size="sm" variant="subtle" onClick={() => setEditing(true)}>
              Edit
            </Button>
            {account.is_active && (
              <Button
                size="sm"
                variant="subtle"
                color="red"
                onClick={() => deactivateAccount.mutate(account.id)}
                loading={deactivateAccount.isPending}
              >
                Deactivate
              </Button>
            )}
          </Group>
        </Group>
      )}
      {account.account_type === 'investment' && <HoldingsSection accountId={account.id} />}
    </Paper>
  )
}

export function AccountsPage() {
  const [showInactive, setShowInactive] = useState(false)
  const { data: accounts, isLoading } = useAccounts({ active: !showInactive })

  return (
    <Stack>
      <Title order={1}>Accounts</Title>
      <CreateAccountForm />
      <Checkbox
        label="Show deactivated accounts only"
        checked={showInactive}
        onChange={(e) => setShowInactive(e.target.checked)}
      />
      {isLoading || !accounts ? (
        <Text>Loading accounts…</Text>
      ) : (
        <Stack gap="sm" component="ul" style={{ padding: 0 }}>
          {accounts.map((account) => (
            <AccountRow key={account.id} account={account} />
          ))}
        </Stack>
      )}
    </Stack>
  )
}
