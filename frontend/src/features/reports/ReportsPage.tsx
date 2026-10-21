import { Paper, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core'
import {
  useCashFlow,
  useCreditHealth,
  useInvestments,
  useNetWorthHistory,
  useSpendingByCategory,
} from './api'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Stack gap="sm">
      <Title order={2} size="h3">
        {title}
      </Title>
      {children}
    </Stack>
  )
}

function NetWorthHistorySection() {
  const { data, isLoading } = useNetWorthHistory()
  if (isLoading || !data) return <Text c="dimmed">Loading…</Text>
  if (data.length === 0) return <Text c="dimmed">No history yet.</Text>
  return (
    <Table>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Month</Table.Th>
          <Table.Th>Net worth</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {data.map((point) => (
          <Table.Tr key={point.date}>
            <Table.Td>{point.date}</Table.Td>
            <Table.Td>{point.net_worth}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  )
}

function CashFlowSection() {
  const { data, isLoading } = useCashFlow()
  if (isLoading || !data) return <Text c="dimmed">Loading…</Text>
  if (data.length === 0) return <Text c="dimmed">No activity yet.</Text>
  return (
    <Table>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Period</Table.Th>
          <Table.Th>Inflow</Table.Th>
          <Table.Th>Outflow</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {data.map((point) => (
          <Table.Tr key={point.period_start}>
            <Table.Td>
              {point.period_start} – {point.period_end}
            </Table.Td>
            <Table.Td c="teal">{point.inflow}</Table.Td>
            <Table.Td c="red">{point.outflow}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  )
}

function SpendingByCategorySection() {
  const { data, isLoading } = useSpendingByCategory()
  if (isLoading || !data) return <Text c="dimmed">Loading…</Text>
  if (data.length === 0) return <Text c="dimmed">No spending this month yet.</Text>
  return (
    <Table>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Category</Table.Th>
          <Table.Th>Total</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {data.map((row) => (
          <Table.Tr key={row.category_id ?? 'uncategorized'}>
            <Table.Td>{row.category_name ?? 'Uncategorized'}</Table.Td>
            <Table.Td>{row.total}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  )
}

function CreditHealthSection() {
  const { data, isLoading } = useCreditHealth()
  if (isLoading || !data) return <Text c="dimmed">Loading…</Text>
  return (
    <Stack gap="md">
      {data.accounts.length === 0 ? (
        <Text c="dimmed">No credit card accounts yet.</Text>
      ) : (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Account</Table.Th>
              <Table.Th>Balance</Table.Th>
              <Table.Th>Limit</Table.Th>
              <Table.Th>Utilization</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.accounts.map((row) => (
              <Table.Tr key={row.account_id}>
                <Table.Td>{row.name}</Table.Td>
                <Table.Td>{row.balance}</Table.Td>
                <Table.Td>{row.credit_limit}</Table.Td>
                <Table.Td>{Math.round(Number(row.utilization) * 100)}%</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {data.overall_utilization !== null && (
        <Text size="sm" c="dimmed">
          Overall utilization: {Math.round(Number(data.overall_utilization) * 100)}%
        </Text>
      )}
      {data.credit_score_history.length === 0 ? (
        <Text c="dimmed">No credit score history yet.</Text>
      ) : (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Date</Table.Th>
              <Table.Th>Score</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.credit_score_history.map((point) => (
              <Table.Tr key={point.date}>
                <Table.Td>{point.date}</Table.Td>
                <Table.Td>{point.value}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  )
}

function InvestmentsSection() {
  const { data, isLoading } = useInvestments()
  if (isLoading || !data) return <Text c="dimmed">Loading…</Text>
  if (data.length === 0) return <Text c="dimmed">No holdings yet.</Text>
  return (
    <Table>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Symbol</Table.Th>
          <Table.Th>Quantity</Table.Th>
          <Table.Th>Cost basis</Table.Th>
          <Table.Th>Current value</Table.Th>
          <Table.Th>Gain/loss</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {data.map((holding) => (
          <Table.Tr key={holding.id}>
            <Table.Td>{holding.symbol}</Table.Td>
            <Table.Td>{holding.quantity}</Table.Td>
            <Table.Td>{holding.cost_basis}</Table.Td>
            <Table.Td>{holding.current_value ?? '—'}</Table.Td>
            <Table.Td
              c={
                holding.gain_loss == null
                  ? undefined
                  : Number(holding.gain_loss) < 0
                    ? 'red'
                    : 'teal'
              }
            >
              {holding.gain_loss ?? '—'}
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  )
}

export function ReportsPage() {
  return (
    <Stack>
      <Title order={1}>Reports</Title>
      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        <Paper withBorder p="lg" radius="md">
          <Section title="Net worth history">
            <NetWorthHistorySection />
          </Section>
        </Paper>
        <Paper withBorder p="lg" radius="md">
          <Section title="Cash flow">
            <CashFlowSection />
          </Section>
        </Paper>
        <Paper withBorder p="lg" radius="md">
          <Section title="Spending by category (this month)">
            <SpendingByCategorySection />
          </Section>
        </Paper>
        <Paper withBorder p="lg" radius="md">
          <Section title="Credit health">
            <CreditHealthSection />
          </Section>
        </Paper>
      </SimpleGrid>
      <Paper withBorder p="lg" radius="md">
        <Section title="Investments">
          <InvestmentsSection />
        </Section>
      </Paper>
    </Stack>
  )
}
