import { Badge, Button, Group, Stack, Text, Title } from '@mantine/core'
import { useNavigate, useParams } from 'react-router-dom'
import { AccountRow } from '../accounts/AccountsPage'
import { useAccounts } from '../accounts/api'
import { type BankHealth, useBank, useBankSync, useUnlinkBank } from './api'

const HEALTH_COLOR: Record<BankHealth, string> = {
  healthy: 'teal',
  needs_reauth: 'yellow',
  error: 'red',
}

const HEALTH_LABEL: Record<BankHealth, string> = {
  healthy: 'Healthy',
  needs_reauth: 'Needs reauth',
  error: 'Error',
}

export function BankDetailPage() {
  const { bankId = '' } = useParams<{ bankId: string }>()
  const navigate = useNavigate()
  const { data: bank, isLoading, isError } = useBank(bankId)
  const { data: accounts, isLoading: accountsLoading } = useAccounts({ bank_id: bankId })
  const { sync, isSyncing, syncError } = useBankSync(bankId)
  const unlinkBank = useUnlinkBank()

  if (isLoading) return <Text>Loading bank…</Text>
  if (isError || !bank) {
    return (
      <Text role="alert" c="red">
        Bank not found.
      </Text>
    )
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={1}>{bank.institution_name}</Title>
        <Badge color={HEALTH_COLOR[bank.health]} variant="light">
          {HEALTH_LABEL[bank.health]}
        </Badge>
      </Group>
      <Text size="sm" c="dimmed">
        {bank.last_synced_at ? `Last synced ${bank.last_synced_at}` : 'Never synced'}
      </Text>
      <Group>
        <Button size="sm" onClick={sync} loading={isSyncing}>
          Sync now
        </Button>
        <Button
          size="sm"
          variant="subtle"
          color="red"
          onClick={() => unlinkBank.mutate(bankId, { onSuccess: () => navigate('/banks') })}
          loading={unlinkBank.isPending}
        >
          Unlink
        </Button>
      </Group>
      {syncError && (
        <Text role="alert" c="red" size="sm">
          {syncError}
        </Text>
      )}

      <Title order={2} size="h4">
        Accounts
      </Title>
      {accountsLoading || !accounts ? (
        <Text>Loading accounts…</Text>
      ) : accounts.length === 0 ? (
        <Text c="dimmed">No accounts pulled for this bank yet.</Text>
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
