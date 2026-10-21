import { Badge, Button, Group, Paper, Stack, Text, Title } from '@mantine/core'
import { Link } from 'react-router-dom'
import { type Bank, type BankHealth, useBankSync, useBanks, useUnlinkBank } from './api'

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

function BankRow({ bank }: { bank: Bank }) {
  const { sync, isSyncing, syncError } = useBankSync(bank.id)
  const unlinkBank = useUnlinkBank()

  return (
    <Paper component="li" withBorder p="md" radius="md" style={{ listStyle: 'none' }}>
      <Group justify="space-between">
        <Stack gap={2}>
          <Text component={Link} to={`/banks/${bank.id}`} fw={500}>
            {bank.institution_name}
          </Text>
          <Text size="sm" c="dimmed">
            {bank.account_count} account{bank.account_count === 1 ? '' : 's'} ·{' '}
            {bank.last_synced_at ? `last synced ${bank.last_synced_at}` : 'never synced'}
          </Text>
          {syncError && (
            <Text role="alert" c="red" size="sm">
              {syncError}
            </Text>
          )}
        </Stack>
        <Group gap="xs">
          <Badge color={HEALTH_COLOR[bank.health]} variant="light">
            {HEALTH_LABEL[bank.health]}
          </Badge>
          <Button size="xs" variant="subtle" onClick={sync} loading={isSyncing}>
            Sync now
          </Button>
          <Button
            size="xs"
            variant="subtle"
            color="red"
            onClick={() => unlinkBank.mutate(bank.id)}
            loading={unlinkBank.isPending}
          >
            Unlink
          </Button>
        </Group>
      </Group>
    </Paper>
  )
}

export function BanksPage() {
  const { data: banks, isLoading, isError } = useBanks()

  return (
    <Stack>
      <Title order={1}>Banks</Title>
      {isLoading ? (
        <Text>Loading banks…</Text>
      ) : isError ? (
        <Text role="alert" c="red">
          Failed to load banks.
        </Text>
      ) : banks && banks.length > 0 ? (
        <Stack gap="sm" component="ul" style={{ padding: 0 }}>
          {banks.map((bank) => (
            <BankRow key={bank.id} bank={bank} />
          ))}
        </Stack>
      ) : (
        <Text c="dimmed">No banks linked yet.</Text>
      )}
    </Stack>
  )
}
