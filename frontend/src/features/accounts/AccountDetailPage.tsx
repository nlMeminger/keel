import { Badge, Button, Group, Paper, Stack, Text, Title } from '@mantine/core'
import { Link, useParams } from 'react-router-dom'
import { DETAIL_FIELDS, type AccountType } from './account-types'
import { useAccount } from './api'
import { HoldingsSection } from './HoldingsSection'

export function AccountDetailPage() {
  const { accountId = '' } = useParams<{ accountId: string }>()
  const { data: account, isLoading, isError } = useAccount(accountId)

  if (isLoading) return <Text>Loading account…</Text>
  if (isError || !account) {
    return (
      <Text role="alert" c="red">
        Account not found.
      </Text>
    )
  }

  const detailFields = DETAIL_FIELDS[account.account_type as AccountType] ?? []
  const detail = account.detail as Record<string, unknown>

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={1}>{account.name}</Title>
        <Button component={Link} to={`/transactions?account_id=${account.id}`} variant="light">
          View transactions
        </Button>
      </Group>
      <Paper withBorder p="lg" radius="md">
        <Stack gap="xs">
          <Group gap="xs">
            <Badge variant="light">{account.account_type}</Badge>
            {!account.is_active && (
              <Badge color="gray" variant="light">
                deactivated
              </Badge>
            )}
            {account.is_plaid_linked && account.bank_id && (
              <Badge component={Link} to={`/banks/${account.bank_id}`} color="teal" variant="light">
                bank-linked
              </Badge>
            )}
            {account.is_plaid_linked && !account.bank_id && (
              <Badge color="teal" variant="light">
                bank-linked
              </Badge>
            )}
          </Group>
          <Text size="xl" fw={600}>
            {account.balance}
          </Text>
          {detailFields.map((field) => {
            const value = detail[field.key]
            if (value === undefined || value === null || value === '') return null
            return (
              <Text key={field.key} size="sm">
                {field.label}: {String(value)}
              </Text>
            )
          })}
        </Stack>
      </Paper>
      {account.account_type === 'investment' && <HoldingsSection accountId={account.id} />}
    </Stack>
  )
}
