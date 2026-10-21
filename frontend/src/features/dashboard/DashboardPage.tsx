import { Group, Paper, Progress, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core'
import { useDashboardSummary } from './api'

function StatCard({
  label,
  value,
  valueColor,
}: {
  label: string
  value: string
  valueColor?: string
}) {
  return (
    <Paper withBorder p="lg" radius="md">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text size="xl" fw={700} c={valueColor}>
        {value}
      </Text>
    </Paper>
  )
}

export function DashboardPage() {
  const { data: summary, isLoading } = useDashboardSummary()

  if (isLoading || !summary) {
    return (
      <Stack>
        <Title order={1}>Dashboard</Title>
        <Text>Loading dashboard…</Text>
      </Stack>
    )
  }

  const delta = Number(summary.net_worth_delta)

  return (
    <Stack>
      <Title order={1}>Dashboard</Title>

      <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }}>
        <StatCard
          label="Net worth"
          value={summary.net_worth}
          valueColor={delta === 0 ? undefined : delta > 0 ? 'teal' : 'red'}
        />
        <StatCard
          label="Net worth change (since last month)"
          value={`${delta >= 0 ? '+' : ''}${summary.net_worth_delta}`}
        />
        <StatCard label="This month inflow" value={summary.this_month_inflow} valueColor="teal" />
        <StatCard label="This month outflow" value={summary.this_month_outflow} valueColor="red" />
      </SimpleGrid>

      {summary.latest_credit_score && (
        <Paper withBorder p="lg" radius="md">
          <Text size="sm" c="dimmed">
            Latest credit score
          </Text>
          <Group gap="xs">
            <Text size="xl" fw={700}>
              {summary.latest_credit_score.value}
            </Text>
            {summary.latest_credit_score.trend && (
              <Text size="sm" c="dimmed">
                ({summary.latest_credit_score.trend})
              </Text>
            )}
          </Group>
        </Paper>
      )}

      <Title order={2} size="h3">
        Budgets
      </Title>
      {summary.budgets.length === 0 ? (
        <Text c="dimmed">No budgets yet.</Text>
      ) : (
        <Stack gap="sm" component="ul" style={{ padding: 0 }}>
          {summary.budgets.map((budget) => {
            const limit = Number(budget.amount_limit)
            const spent = Number(budget.spend_so_far)
            const percent = limit > 0 ? Math.min(100, Math.round((spent / limit) * 100)) : 0
            return (
              <Paper
                key={budget.id}
                component="li"
                withBorder
                p="md"
                radius="md"
                style={{ listStyle: 'none' }}
              >
                <Stack gap="xs">
                  <Text size="sm" c="dimmed">
                    {budget.spend_so_far} of {budget.amount_limit} spent ({percent}%)
                  </Text>
                  <Progress value={percent} color={percent >= 100 ? 'red' : 'teal'} />
                </Stack>
              </Paper>
            )
          })}
        </Stack>
      )}

      <Title order={2} size="h3">
        Recent transactions
      </Title>
      {summary.recent_transactions.length === 0 ? (
        <Text c="dimmed">No transactions yet.</Text>
      ) : (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Date</Table.Th>
              <Table.Th>Description</Table.Th>
              <Table.Th>Amount</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {summary.recent_transactions.map((txn) => (
              <Table.Tr key={txn.id}>
                <Table.Td>{txn.date}</Table.Td>
                <Table.Td>{txn.description}</Table.Td>
                <Table.Td c={Number(txn.amount) < 0 ? 'red' : 'teal'}>{txn.amount}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  )
}
